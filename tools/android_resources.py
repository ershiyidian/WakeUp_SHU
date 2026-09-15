"""Lossless Android resource-table and binary-XML source codec.

JSON source retains Android's typed values, resource identifiers and configuration bytes.
The companion XML views display the same values using their symbolic resource names.
"""
from pathlib import Path
import struct,json,sys
from axml import pool

def chunks(data,start=0,end=None):
 end=len(data)if end is None else end
 while start<end:
  t,h,n=struct.unpack_from('<HHI',data,start)
  if n<h or h<8 or start+n>end:raise ValueError('Invalid resource chunk boundary')
  yield start,t,h,n;start+=n
 if start!=end:raise ValueError('Resource chunk alignment')
def u32s(b):return list(struct.unpack('<'+'I'*(len(b)//4),b))
def pack32(a):return struct.pack('<'+'I'*len(a),*a)
def typed(d,p):
 size,res,typ,val=struct.unpack_from('<HBBI',d,p);return {'size':size,'reserved':res,'type':typ,'data':val}
def value(x):return struct.pack('<HBBI',x['size'],x['reserved'],x['type'],x['data'])
def wrap(t,h,b):return struct.pack('<HHI',t,h,len(b)+8)+b

def decode_chunk(d):
 t,h,n=struct.unpack_from('<HHI',d,0)
 if t==1:
  strings,positions,_=pool(d,0);count,styles,flags,start,styles_start=struct.unpack_from('<5I',d,8)
  cesu=[]
  if flags&0x100:
   for i,(_,p,nbytes) in enumerate(positions):
    text=d[p:p+nbytes].decode('utf8','surrogatepass')
    if any(0xd800<=ord(c)<=0xdfff for c in text):cesu.append(i)
    strings[i]=text.encode('utf-16-le','surrogatepass').decode('utf-16-le','surrogatepass')
  if styles:raise ValueError('Styled string pool requires style support')
  return {'kind':'strings','flags':flags,'strings':strings,'cesu8_entries':cesu}
 if t in (3,2):return {'kind':'xml'if t==3 else 'table','header':d[8:h].hex(),'chunks':[decode_chunk(d[p:p+n])for p,_,_,n in chunks(d,h)]}
 if t==0x200:
  head=bytearray(d[8:h]);pid=struct.unpack_from('<I',d,8)[0];name=d[12:268].decode('utf-16-le').rstrip('\0')
  return {'kind':'package','id':pid,'name':name,'header':head.hex(),'chunks':[decode_chunk(d[p:p+n])for p,_,_,n in chunks(d,h)]}
 if t==0x180:return {'kind':'resource-map','ids':u32s(d[h:])}
 if t==0x202:
  tid,res,res2,count=struct.unpack_from('<BBHI',d,8)
  return {'kind':'type-spec','id':tid,'reserved':[res,res2],'masks':u32s(d[h:])}
 if t==0x201:
  tid,flags,res,cnt,start=struct.unpack_from('<BBHII',d,8);assert flags==0
  offsets=u32s(d[h:h+4*cnt]);items=[]
  for idx,off in enumerate(offsets):
   if off==0xffffffff:continue
   p=start+off;size,fl,key=struct.unpack_from('<HHI',d,p);x={'index':idx,'key':key,'flags':fl,'size':size}
   if fl&1:
    parent,count=struct.unpack_from('<II',d,p+8);x['parent']=parent;x['values']=[{'name':struct.unpack_from('<I',d,p+size+12*j)[0],'value':typed(d,p+size+12*j+4)}for j in range(count)]
   else:x['value']=typed(d,p+size)
   items.append(x)
  return {'kind':'type','id':tid,'flags':flags,'reserved':res,'entry_count':cnt,'config':d[20:h].hex(),'entries':items}
 if t in (0x100,0x101,0x103,0x104,0x102):
  line,comment=struct.unpack_from('<II',d,8);x={'kind':{0x100:'namespace-start',0x101:'namespace-end',0x102:'element-start',0x103:'element-end',0x104:'text'}[t],'line':line,'comment':comment}
  if t in (0x100,0x101):x['prefix'],x['uri']=struct.unpack_from('<II',d,16)
  elif t==0x103:x['namespace'],x['name']=struct.unpack_from('<II',d,16)
  elif t==0x104:x['text']=struct.unpack_from('<I',d,16)[0];x['value']=typed(d,20)
  else:
   ns,name,start,size,count,i,cl,style=struct.unpack_from('<II6H',d,16);assert start==20 and size==20
   x.update(namespace=ns,name=name,id_attribute=i,class_attribute=cl,style_attribute=style,attributes=[])
   for j in range(count):
    p=16+start+size*j;ns,name,raw=struct.unpack_from('<III',d,p);x['attributes'].append({'namespace':ns,'name':name,'raw':raw,'value':typed(d,p+12)})
  return x
 return {'kind':'metadata','type':t,'header_size':h,'body':d[8:].hex()}

def encode(x):
 k=x['kind']
 if k=='strings':
  # Android accepts UTF-8 pools in tables and XML; the project sources use this encoding.
  if x['flags']&0x100:
   offsets=[];data=bytearray();cesu=set(x.get('cesu8_entries',[]))
   def length(n):return bytes([n])if n<128 else bytes([(n>>8)|128,n&255])
   for i,s in enumerate(x['strings']):
    offsets.append(len(data));u=s.encode('utf-16-le','surrogatepass')
    b=b''.join(chr(q).encode('utf8','surrogatepass')for q in struct.unpack('<'+'H'*(len(u)//2),u))if i in cesu else s.encode('utf8')
    data+=length(len(u)//2)+length(len(b))+b+b'\0'
   data+=b'\0'*((-len(data))%4)
   return wrap(1,28,struct.pack('<5I',len(offsets),0,x['flags'],28+4*len(offsets),0)+pack32(offsets)+data)
  data=bytearray();offsets=[]
  for s in x['strings']:
   offsets.append(len(data));b=s.encode('utf-16-le');n=len(b)//2
   data+=struct.pack('<H',n)if n<0x8000 else struct.pack('<HH',(n>>16)|0x8000,n&65535);data+=b+b'\0\0'
  data+=b'\0'*((-len(data))%4);head=struct.pack('<5I',len(offsets),0,x['flags'],28+4*len(offsets),0)
  return wrap(1,28,head+pack32(offsets)+data)
 if k in ('xml','table'):head=bytes.fromhex(x['header']);return wrap(3 if k=='xml'else 2,8+len(head),head+b''.join(encode(c)for c in x['chunks']))
 if k=='package':
  head=bytearray.fromhex(x['header']);parts=[];offset=8+len(head);poolcount=0
  for c in x['chunks']:
   if c['kind']=='strings':
    if poolcount==0:struct.pack_into('<I',head,260,offset)
    elif poolcount==1:struct.pack_into('<I',head,268,offset)
    poolcount+=1
   b=encode(c);parts.append(b);offset+=len(b)
  return wrap(0x200,8+len(head),head+b''.join(parts))
 if k=='resource-map':return wrap(0x180,8,pack32(x['ids']))
 if k=='type-spec':return wrap(0x202,16,struct.pack('<BBHI',x['id'],*x['reserved'],len(x['masks']))+pack32(x['masks']))
 if k=='type':
  entries=bytearray();offsets=[0xffffffff]*x['entry_count']
  for e in x['entries']:
   offsets[e['index']]=len(entries);b=struct.pack('<HHI',e['size'],e['flags'],e['key'])
   if e['flags']&1:b+=struct.pack('<II',e['parent'],len(e['values']));b+=b'\0'*(e['size']-len(b));b+=b''.join(struct.pack('<I',v['name'])+value(v['value'])for v in e['values'])
   else:b+=b'\0'*(e['size']-len(b));b+=value(e['value'])
   entries+=b
  config=bytes.fromhex(x['config']);h=20+len(config);start=h+4*len(offsets)
  return wrap(0x201,h,struct.pack('<BBHII',x['id'],x['flags'],x['reserved'],len(offsets),start)+config+pack32(offsets)+entries)
 if k in ('namespace-start','namespace-end','element-start','element-end','text'):
  typ={'namespace-start':0x100,'namespace-end':0x101,'element-start':0x102,'element-end':0x103,'text':0x104}[k];b=struct.pack('<II',x['line'],x['comment'])
  if k.startswith('namespace'):b+=struct.pack('<II',x['prefix'],x['uri'])
  elif k=='element-end':b+=struct.pack('<II',x['namespace'],x['name'])
  elif k=='text':b+=struct.pack('<I',x['text'])+value(x['value'])
  else:
   a=x['attributes'];b+=struct.pack('<II6H',x['namespace'],x['name'],20,20,len(a),x['id_attribute'],x['class_attribute'],x['style_attribute'])
   b+=b''.join(struct.pack('<III',a['namespace'],a['name'],a['raw'])+value(a['value'])for a in a)
  return wrap(typ,16,b)
 return wrap(x['type'],x['header_size'],bytes.fromhex(x['body']))

def write(path,obj):Path(path).parent.mkdir(parents=True,exist_ok=True);Path(path).write_text(json.dumps(obj,ensure_ascii=False,indent=1)+'\n',encoding='utf8')
if __name__=='__main__':
 cmd,src,dst=sys.argv[1:4]
 if cmd=='export':write(dst,decode_chunk(Path(src).read_bytes()))
 elif cmd=='build':Path(dst).write_bytes(encode(json.loads(Path(src).read_text())))
