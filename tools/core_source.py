"""Export and assemble the inherited DEX core as editable per-class instruction sources.

Instruction mnemonics, registers, literals, references, branches, payloads and exception
handlers are the build inputs. Layout metadata preserves the inherited pools and annotations.
New application features are compiled from Java in the extension module.
"""
from pathlib import Path
import struct,json,sys,hashlib
from dexutil import Dex,OP,signed,uleb,sleb,enc_uleb
from dex_edit import map_items,code_end,relocate_code

def write_json(path,obj):
 path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(obj,ensure_ascii=True,indent=1)+'\n')
def enc_sleb(n):
 out=bytearray()
 while True:
  b=n&127;n>>=7;done=(n==0 and not b&64)or(n==-1 and b&64);out.append(b if done else b|128)
  if done:return bytes(out)
def label(pc):return 'L%04x'%pc

def decode_code(d,off):
 r,ins,outs,nt,debug,n=struct.unpack_from('<HHHHII',d.d,off)
 items=list(d.insns({'name':'source','code':off}));bases={i['target']:i['pc'] for i in items if i['op'] in (0x2b,0x2c)}
 code=[]
 for i in items:
  x={'label':label(i['pc']),'op':i['name']};v=i['units'];f=i['fmt'];o=i['op']
  if i['regs']:x['registers']=i['regs']
  if i['ref'] is not None:
   pool={'string':d.strings,'type':d.types,'field':d.fields,'method':d.methods,'proto':d.protos}.get(i['refkind'])
   x[i['refkind']]=pool[i['ref']] if pool is not None else i['ref']
  if i['target'] is not None:x['target']=label(i['target'])
  if f=='11n':x['literal']=signed(v[0]>>12,4)
  elif f in ('21s','21h','22s'):x['literal']=signed(v[1],16)
  elif f=='31i':x['literal']=signed(v[1]|v[2]<<16,32)
  elif f=='51l':x['literal']=sum(w<<(16*j)for j,w in enumerate(v[1:]))
  elif f=='22b':x['literal']=signed(v[1]>>8,8)
  if f in ('45cc','4rcc'):x['prototype']=d.protos[v[3]]
  if i['payload']:
   if v[0] in (0x100,0x200):
    count=v[1];base=bases.get(i['pc'])
    if v[0]==0x100:
     x['first_key']=signed(v[2]|v[3]<<16,32);start=4
    else:
     x['keys']=[signed(v[2+2*j]|v[3+2*j]<<16,32) for j in range(count)];start=2+2*count
    rel=[signed(v[start+2*j]|v[start+2*j+1]<<16,32) for j in range(count)]
    if base is None:x['relative_targets']=rel
    else:x.update(switch=label(base),targets=[label(base+a)for a in rel])
   elif v[0]==0x300:
    width=v[1];count=v[2]|v[3]<<16;raw=struct.pack('<'+'H'*(len(v)-4),*v[4:]);x['element_width']=width;x['elements']=[int.from_bytes(raw[j*width:(j+1)*width],'little')for j in range(count)]
    if count*width&1:x['padding']=raw[-1]
  # Reserved operand bits are explicit for round-trip preservation.
  if f in ('10x','20t','30t','32x') and v[0]>>8:x['reserved']=v[0]>>8
  code.append(x)
 tail=off+16+2*n;tries=[];handlers=[]
 if nt:
  if n&1:tail+=2
  hstart=tail+8*nt;count,p=uleb(d.d,hstart)
  for j in range(count):
   ho=p-hstart;s,p=sleb(d.d,p);pairs=[]
   for k in range(abs(s)):
    t,p=uleb(d.d,p);a,p=uleb(d.d,p);pairs.append({'type':d.types[t],'target':label(a)})
   h={'id':'H%x'%ho,'catches':pairs}
   if s<=0:a,p=uleb(d.d,p);h['all']=label(a)
   handlers.append(h)
  for j in range(nt):
   a,count,ho=struct.unpack_from('<IHH',d.d,tail+8*j);tries.append({'start':label(a),'end':label(a+count),'handler':'H%x'%ho})
 return {'offset':off,'registers':r,'inputs':ins,'outputs':outs,'debug_offset':debug,'end':label(n),'instructions':code,'tries':tries,'handlers':handlers}

def assemble_code(m,d):
 names={name:(op,fmt)for op,(name,fmt)in OP.items()}
 if not hasattr(d,'source_indices'):d.source_indices={k:{s.encode('utf-16-le','surrogatepass').decode('utf-16-le','surrogatepass'):i for i,s in enumerate(v)}for k,v in [('string',d.strings),('type',d.types),('field',d.fields),('method',d.methods),('proto',d.protos)]}
 indices=d.source_indices
 code=m['instructions'];pcs={};pc=0
 for x in code:
  pcs[x['label']]=pc
  if x['op']=='packed-switch-payload':length=4+2*len(x.get('targets',x.get('relative_targets',[])))
  elif x['op']=='sparse-switch-payload':length=2+4*len(x['keys'])
  elif x['op']=='array-data-payload':length=4+(x['element_width']*len(x['elements'])+1)//2
  else:length=int(names[x['op']][1][0])
  pc+=length
 pcs[m['end']]=pc;n=pc;units=[]
 def ref(x):
  for k in ('string','type','field','method','proto','method-handle','callsite'):
   if k in x:return indices[k][x[k]] if k in indices else x[k]
  raise ValueError(x)
 for x in code:
  name=x['op'];pos=pcs[x['label']]
  if name.endswith('-payload'):
   if name in ('packed-switch-payload','sparse-switch-payload'):
    targets=[pcs[a]-pcs[x['switch']]for a in x['targets']] if 'targets'in x else x['relative_targets'];v=[0x100 if name.startswith('packed')else 0x200,len(targets)]
    keys=[x['first_key']]if name.startswith('packed')else x['keys']
    for q in keys+targets:v.extend([q&65535,(q>>16)&65535])
   else:
    width=x['element_width'];count=len(x['elements']);raw=b''.join(q.to_bytes(width,'little')for q in x['elements']);raw+=bytes([x.get('padding',0)])if len(raw)&1 else b'';v=[0x300,width,count&65535,count>>16,*struct.unpack('<'+'H'*(len(raw)//2),raw)]
   units.extend(v);continue
  op,f=names[name];r=x.get('registers',[]);lit=x.get('literal',0);delta=pcs[x['target']]-pos if 'target'in x else 0;v=[op|x.get('reserved',0)<<8]
  if f=='10x':pass
  elif f=='12x':v=[op|r[0]<<8|r[1]<<12]
  elif f=='11x':v=[op|r[0]<<8]
  elif f=='11n':v=[op|r[0]<<8|(lit&15)<<12]
  elif f=='22x':v=[op|r[0]<<8,r[1]]
  elif f=='32x':v+=[r[0],r[1]]
  elif f in ('21s','21h'):v=[op|r[0]<<8,lit&65535]
  elif f=='31i':v=[op|r[0]<<8,lit&65535,(lit>>16)&65535]
  elif f=='51l':v=[op|r[0]<<8]+[(lit>>(16*j))&65535 for j in range(4)]
  elif f=='21c':v=[op|r[0]<<8,ref(x)]
  elif f=='22c':v=[op|r[0]<<8|r[1]<<12,ref(x)]
  elif f=='31c':q=ref(x);v=[op|r[0]<<8,q&65535,q>>16]
  elif f in ('35c','45cc'):
   rr=r+[0]*(5-len(r));v=[op|len(r)<<12|rr[4]<<8,ref(x),sum(rr[j]<<(4*j)for j in range(4))]
   if f=='45cc':v.append(indices['proto'][x['prototype']])
  elif f in ('3rc','4rcc'):
   if r!=list(range(r[0],r[0]+len(r)))if r else False:raise ValueError('Contiguous invoke range required')
   v=[op|len(r)<<8,ref(x),r[0]if r else 0]
   if f=='4rcc':v.append(indices['proto'][x['prototype']])
  elif f=='23x':v=[op|r[0]<<8,r[1]|r[2]<<8]
  elif f=='22s':v=[op|r[0]<<8|r[1]<<12,lit&65535]
  elif f=='22b':v=[op|r[0]<<8,r[1]|(lit&255)<<8]
  elif f=='10t':assert -128<=delta<128;v=[op|(delta&255)<<8]
  elif f=='20t':assert -32768<=delta<32768;v+=[delta&65535]
  elif f in ('30t','31t'):v=[op|(r[0]<<8 if r else x.get('reserved',0)<<8),delta&65535,(delta>>16)&65535]
  elif f=='21t':assert -32768<=delta<32768;v=[op|r[0]<<8,delta&65535]
  elif f=='22t':assert -32768<=delta<32768;v=[op|r[0]<<8|r[1]<<12,delta&65535]
  else:raise ValueError(f)
  units.extend(v)
 assert len(units)==n
 tries=m['tries'];out=bytearray(struct.pack('<HHHHII',m['registers'],m['inputs'],m['outputs'],len(tries),m['debug_offset'],n)+struct.pack('<'+'H'*n,*units))
 if tries:
  if n&1:out+=b'\0\0'
  handlers=bytearray(enc_uleb(len(m['handlers'])));offsets={}
  for h in m['handlers']:
   offsets[h['id']]=len(handlers);c=h['catches'];handlers+=enc_sleb(-len(c)if 'all'in h else len(c))
   for v in c:handlers+=enc_uleb(indices['type'][v['type']])+enc_uleb(pcs[v['target']])
   if 'all'in h:handlers+=enc_uleb(pcs[h['all']])
  for t in tries:out+=struct.pack('<IHH',pcs[t['start']],pcs[t['end']]-pcs[t['start']],offsets[t['handler']])
  out+=handlers
 return bytes(out)

def export(data,dest):
 dest=Path(dest);dest.mkdir(parents=True,exist_ok=True);d=Dex(data);maps=map_items(data);entry=next(e for e in maps if e[0]==0x2001);p=entry[3];start=p;allcodes={}
 for j in range(entry[2]):
  p=(p+3)&~3;end=code_end(data,p);allcodes[p]=decode_code(d,p);p=end
 code_end_offset=p
 used=set();paths=[]
 for number,(desc,c) in enumerate(d.classes.items()):
  obj={'class':desc,'super':c['super'],'access':c['flags'],'fields':[{'name':d.fields[i],'access':f}for i,f in c['fields']],'methods':[]}
  for m in c['methods']:
   x={'name':m['name'],'access':m['flags']}
   if m['code']:x.update(allcodes[m['code']]);used.add(m['code'])
   obj['methods'].append(x)
  # Exact descriptor encoded through UTF-8; Android identifiers are valid path components here.
  group='app'if desc.startswith(('Lcom/suda/','Lshu/'))else'androidx'if desc.startswith('Landroidx/')else'kotlin'if desc.startswith('Lkotlin/')else'libraries'
  path=Path('classes')/group/(f'{number:05d}_'+desc[1:-1].replace('/','.')[-140:]+'.dexasm.json');write_json(dest/path,obj);paths.append(str(path))
 unused=[v for k,v in allcodes.items()if k not in used]
 write_json(dest/'metadata/retained-code.dexasm.json',{'methods':unused})
 # Segments hold compiler metadata only; the entire executable code section is assembled above.
 segs=[]
 for a,b in [(0,start),(code_end_offset,len(data))]:
  segs.append({'offset':a,'length':b-a,'hex':data[a:b].hex()})
 write_json(dest/'metadata/layout.json',{'format':'WakeUp-SHU DEX source layout v1','file_size':len(data),'code_start':start,'code_end':code_end_offset,'segments':segs,'classes':paths,'code_records':[{k:m[k] for k in ['offset','registers','inputs','outputs','debug_offset','end','tries','handlers']} for m in allcodes.values()]})
 write_json(dest/'metadata/pools.json',{'strings':d.strings,'types':d.types,'prototypes':d.protos,'fields':d.fields,'methods':d.methods,'map':[list(x)for x in maps]})
 return {'classes':len(paths),'methods_with_code':len(used),'retained_code_items':len(unused),'code_bytes':code_end_offset-start}

def build(src):
 src=Path(src);layout=json.loads((src/'metadata/layout.json').read_text());data=bytearray(layout['file_size'])
 for s in layout['segments']:
  b=bytes.fromhex(s['hex']);assert len(b)==s['length'];data[s['offset']:s['offset']+len(b)]=b
 # Pools and class metadata can be read while method bodies are still zero-filled.
 d=Dex(data);allm=[]
 for path in layout['classes']:allm.extend(m for m in json.loads((src/path).read_text())['methods']if 'offset'in m)
 allm.extend(json.loads((src/'metadata/retained-code.dexasm.json').read_text())['methods'])
 # Reconstruct compiler-layout placeholders, then relocate complete assembled methods.
 # Placeholder words are NOPs; all executable instructions come from class source files.
 for m in layout['code_records']:
  n=int(m['end'][1:],16);nt=len(m['tries']);b=bytearray(struct.pack('<HHHHII',m['registers'],m['inputs'],m['outputs'],nt,m['debug_offset'],n)+bytes(2*n))
  if nt:
   if n&1:b+=bytes(2)
   hs=bytearray(enc_uleb(len(m['handlers'])));hids={}
   for h in m['handlers']:
    hids[h['id']]=len(hs);c=h['catches'];hs+=enc_sleb(-len(c)if 'all'in h else len(c))
    for t in c:hs+=enc_uleb(d.types.index(t['type']))+enc_uleb(int(t['target'][1:],16))
    if 'all'in h:hs+=enc_uleb(int(h['all'][1:],16))
   for t in m['tries']:
    a=int(t['start'][1:],16);end=int(t['end'][1:],16);b+=struct.pack('<IHH',a,end-a,hids[t['handler']])
   b+=hs
  off=m['offset'];data[off:off+len(b)]=b
 replacements={m['offset']:assemble_code(m,d)for m in allm}
 result,_=relocate_code(Dex(data).fix(),replacements)
 return result

if __name__=='__main__':
 cmd,source,dest=sys.argv[1:4]
 if cmd=='export':print(export(Path(source).read_bytes(),dest))
 elif cmd=='build':Path(dest).write_bytes(build(source))
 else:raise ValueError(cmd)
