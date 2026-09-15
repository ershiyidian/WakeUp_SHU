"""Deterministic Android resource-table and binary XML transformations."""
from pathlib import Path
import struct,sys,zipfile,json
from resources import Resources,chunks
from axml import pool,parse
U32=0xffffffff

def string_pool(strings):
 def ln(n):return bytes([n]) if n<128 else bytes([0x80|(n>>8),n&255])
 data=bytearray();offs=[]
 for text in strings:
  b=text.encode('utf-8');offs.append(len(data));data+=ln(len(text.encode('utf-16-le'))//2)+ln(len(b))+b+b'\0'
 while len(data)%4:data.append(0)
 start=28+4*len(strings)
 return struct.pack('<HHI5I',1,28,start+len(data),len(strings),0,0x100,start,0)+struct.pack('<'+'I'*len(offs),*offs)+data

def attrs_from_apk(z):
 out={}
 for n in ['AndroidManifest.xml']+[n for n in z.namelist() if n.startswith('res/') and n.endswith('.xml')]:
  b=z.read(n)
  if b[:2]!=b'\x03\0':continue
  ss=None
  for p,t,h,s in chunks(b,8,len(b)):
   if t==1:ss,_,_=pool(b,p)
   if t==0x180:
    for i in range((s-h)//4):
     val=struct.unpack_from('<I',b,p+h+4*i)[0]
     if val and val>>24==1:out[ss[i]]=val
 return out

def binary_xml(root,attr_ids):
 # root=(tag,[(attribute,type,value)],children), Android namespace for each attribute.
 ns='http://schemas.android.com/apk/res/android';ss=[]
 def idx(s):
  if s not in ss:ss.append(s)
  return ss.index(s)
 idx('android');idx(ns)
 def collect(n):
  tag,attrs,children=n;idx(tag)
  for key,t,v in attrs:idx(key);idx(v) if t==3 else None
  for c in children:collect(c)
 collect(root)
 rm=[attr_ids.get(s,0) for s in ss]
 out=bytearray(string_pool(ss));out+=struct.pack('<HHI',0x180,8,8+4*len(rm))+struct.pack('<'+'I'*len(rm),*rm)
 def node(t,body):return struct.pack('<HHIII',t,16,16+len(body),1,U32)+body
 out+=node(0x100,struct.pack('<II',idx('android'),idx(ns)))
 def emit(n):
  tag,attrs,children=n;attrs=sorted(attrs,key=lambda x:attr_ids.get(x[0],0))
  raw=bytearray(struct.pack('<IIHHHHHH',U32,idx(tag),20,20,len(attrs),0,0,0))
  for key,t,v in attrs:
   val=idx(v) if t==3 else v;raw+=struct.pack('<IIIHBBI',idx(ns),idx(key),val if t==3 else U32,8,0,t,val&U32)
  out.extend(node(0x102,raw))
  for c in children:emit(c)
  out.extend(node(0x103,struct.pack('<II',U32,idx(tag))))
 emit(root);out+=node(0x101,struct.pack('<II',idx('android'),idx(ns)))
 b=struct.pack('<HHI',3,8,8+len(out))+out;parse(b);return b

def dim(n):return (n<<8)|1

def patch_table(data,new_drawables,string_updates):
 r=Resources(data);global_strings=list(r.strings)
 # Change selected resource values through new pool items, leaving shared old values alone.
 def stridx(s):
  if s not in global_strings:global_strings.append(s)
  return global_strings.index(s)
 replacements={e['off']:stridx(string_updates[e['name']]) for e in r.entries if e['name'] in string_updates}
 package=next((p,t,h,n) for p,t,h,n in chunks(data,12,len(data)) if t==0x200);p,t,h,n=package
 po=data[p:p+n];keyoff=struct.unpack_from('<I',po,276)[0];keys,_,_=pool(po,keyoff);keys=list(keys)
 def keyidx(s):
  if s not in keys:keys.append(s)
  return keys.index(s)
 # New resources get explicit stable IDs shared by the Java helpers.
 max_draw=max([int(e['id'])&65535 for e in r.entries if e['id']>>16&255==8]+[x['id']&65535 for x in new_drawables]);draw_count=max_draw+1
 new_rows=[]
 for x in new_drawables:
  new_rows.append(dict(x,key=keyidx(x['name']),value=stridx(x['path'])))
 splash={16844332:(0x1c,0xfff8f9fc),16844333:(1,0x7f080300),16844335:(1,0x7f080301),16842836:(1,0x7f080302)}
 def rebuild_type(raw,q):
  tid,flags,zero,count,start=struct.unpack_from('<BBHII',raw,8);hs=struct.unpack_from('<H',raw,2)[0]
  offsets=[];body=bytearray();newcount=draw_count if tid==8 else count
  for i in range(count):
   off=struct.unpack_from('<I',raw,hs+4*i)[0]
   if off==U32:offsets.append(U32);continue
   ep=start+off;sz,fl,k=struct.unpack_from('<HHI',raw,ep)
   if fl&1:
    parent,cn=struct.unpack_from('<II',raw,ep+8);end=ep+sz+12*cn;b=raw[ep:end]
    if tid==19 and i==0x1a7:
     maps={struct.unpack_from('<I',b,sz+12*j)[0]:struct.unpack_from('<HBBI',b,sz+12*j+4)[2:] for j in range(cn)};maps.update(splash)
     b=struct.pack('<HHIII',16,fl,k,parent,len(maps))+b''.join(struct.pack('<IHBBI',key,8,0,typ,val) for key,(typ,val) in sorted(maps.items()))
   else:
    end=ep+sz+8;b=bytearray(raw[ep:end]);absolute=p+q+ep
    if absolute in replacements:struct.pack_into('<HBBI',b,sz,8,0,3,replacements[absolute])
   offsets.append(len(body));body+=b
  offsets.extend([U32]*(newcount-count));header=bytearray(raw[:hs]);ns=hs+newcount*4;struct.pack_into('<I',header,4,ns+len(body));struct.pack_into('<II',header,12,newcount,ns)
  return header+struct.pack('<'+'I'*len(offsets),*offsets)+body
 children=[];positions={}
 for q,ct,ch,cn in chunks(po,h,len(po)):
  raw=po[q:q+cn];positions[q]=h+sum(len(x) for x in children)
  if ct==1 and q==keyoff:raw=string_pool(keys)
  elif ct==0x201:raw=rebuild_type(raw,q)
  elif ct==0x202 and raw[8]==8:
   cnt=struct.unpack_from('<I',raw,12)[0];raw=bytearray(raw)+bytes(4*(draw_count-cnt));struct.pack_into('<I',raw,4,len(raw));struct.pack_into('<I',raw,12,draw_count)
   for x in new_rows:struct.pack_into('<I',raw,16+4*(x['id']&65535),0x40000200) # public, night variability
  children.append(raw)
 def new_type(config,rows,tid=8,count=draw_count):
  hs=20+len(config);body=bytearray();offs=[U32]*count
  for x in sorted(rows,key=lambda x:x['id']):
   offs[x['id']&65535]=len(body);body+=struct.pack('<HHIHBBI',8,0,x['key'],8,0,3,x['value'])
  start=hs+4*count;return struct.pack('<HHIBBHII',0x201,hs,start+len(body),tid,0,0,count,start)+config+struct.pack('<'+'I'*count,*offs)+body
 groups={}
 for x in new_rows:groups.setdefault(x['config'],[]).append(x)
 for conf,rows in groups.items():children.append(new_type(bytes.fromhex(conf),rows))
 # Night variant of the splash theme, using the inherited style and all explicit branding attrs.
 config=bytearray(64);struct.pack_into('<I',config,0,64);config[29]=0x20
 count=next(struct.unpack_from('<I',po,q+12)[0] for q,ct,ch,cn in chunks(po,h,len(po)) if ct==0x202 and po[q+8]==19)
 key=next(struct.unpack_from('<I',data,e['off']+4)[0] for e in r.entries if e['id']==0x7f1301a7)
 maps=dict(splash);maps[16844332]=(0x1c,0xff10171b);maps[16844166]=(16,1)
 body=struct.pack('<HHIII',16,1,key,0x7f130128,len(maps))+b''.join(struct.pack('<IHBBI',k,8,0,t,v) for k,(t,v) in sorted(maps.items()))
 offs=[U32]*count;offs[0x1a7]=0;hs=84;start=hs+4*count
 children.append(struct.pack('<HHIBBHII',0x201,hs,start+len(body),19,0,0,count,start)+config+struct.pack('<'+'I'*count,*offs)+body)
 header=bytearray(po[:h]);struct.pack_into('<I',header,4,h+sum(len(x) for x in children));struct.pack_into('<I',header,268,positions[struct.unpack_from('<I',po,268)[0]]);struct.pack_into('<I',header,276,positions[keyoff])
 newpkg=header+b''.join(children);glob=string_pool(global_strings);b=bytearray(data[:12])+glob+newpkg;struct.pack_into('<I',b,4,len(b));rr=Resources(b)
 assert all(any(e['id']==x['id'] and e.get('text')==x['path'] for e in rr.entries) for x in new_rows)
 return bytes(b)
