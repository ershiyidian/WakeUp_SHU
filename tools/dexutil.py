import struct, hashlib, zlib, json, sys
from pathlib import Path

def uleb(d,p):
 r=s=0; start=p
 while True:
  b=d[p];p+=1;r|=(b&127)<<s;s+=7
  if b<128: return r,p
  if p-start>=5: raise ValueError('bad uleb')

def sleb(d,p):
 r=s=0
 while True:
  b=d[p];p+=1;r|=(b&127)<<s;s+=7
  if b<128:
   if b&64:r-=1<<s
   return r,p

def enc_uleb(n):
 b=bytearray()
 while n>127:b.append((n&127)|128);n>>=7
 return bytes(b+bytes([n]))

OP={}
def ops(start,names,fmt):
 for i,name in enumerate(names.split()): OP[start+i]=(name,fmt)
ops(0x00,'nop','10x');ops(0x01,'move','12x');ops(0x02,'move/from16','22x');ops(0x03,'move/16','32x')
ops(0x04,'move-wide','12x');ops(0x05,'move-wide/from16','22x');ops(0x06,'move-wide/16','32x')
ops(0x07,'move-object','12x');ops(0x08,'move-object/from16','22x');ops(0x09,'move-object/16','32x')
ops(0x0a,'move-result move-result-wide move-result-object move-exception','11x');ops(0x0e,'return-void','10x');ops(0x0f,'return return-wide return-object','11x')
ops(0x12,'const/4','11n');ops(0x13,'const/16','21s');ops(0x14,'const','31i');ops(0x15,'const/high16','21h')
ops(0x16,'const-wide/16','21s');ops(0x17,'const-wide/32','31i');ops(0x18,'const-wide','51l');ops(0x19,'const-wide/high16','21h')
ops(0x1a,'const-string','21c');ops(0x1b,'const-string/jumbo','31c');ops(0x1c,'const-class','21c');ops(0x1d,'monitor-enter monitor-exit','11x');ops(0x1f,'check-cast','21c');ops(0x20,'instance-of','22c');ops(0x21,'array-length','12x');ops(0x22,'new-instance','21c');ops(0x23,'new-array','22c');ops(0x24,'filled-new-array','35c');ops(0x25,'filled-new-array/range','3rc');ops(0x26,'fill-array-data','31t');ops(0x27,'throw','11x');ops(0x28,'goto','10t');ops(0x29,'goto/16','20t');ops(0x2a,'goto/32','30t');ops(0x2b,'packed-switch sparse-switch','31t');ops(0x2d,'cmpl-float cmpg-float cmpl-double cmpg-double cmp-long','23x');ops(0x32,'if-eq if-ne if-lt if-ge if-gt if-le','22t');ops(0x38,'if-eqz if-nez if-ltz if-gez if-gtz if-lez','21t');ops(0x44,'aget aget-wide aget-object aget-boolean aget-byte aget-char aget-short aput aput-wide aput-object aput-boolean aput-byte aput-char aput-short','23x');ops(0x52,'iget iget-wide iget-object iget-boolean iget-byte iget-char iget-short iput iput-wide iput-object iput-boolean iput-byte iput-char iput-short','22c');ops(0x60,'sget sget-wide sget-object sget-boolean sget-byte sget-char sget-short sput sput-wide sput-object sput-boolean sput-byte sput-char sput-short','21c');ops(0x6e,'invoke-virtual invoke-super invoke-direct invoke-static invoke-interface','35c');ops(0x74,'invoke-virtual/range invoke-super/range invoke-direct/range invoke-static/range invoke-interface/range','3rc');ops(0x7b,'neg-int not-int neg-long not-long neg-float neg-double int-to-long int-to-float int-to-double long-to-int long-to-float long-to-double float-to-int float-to-long float-to-double double-to-int double-to-long double-to-float int-to-byte int-to-char int-to-short','12x');ops(0x90,'add-int sub-int mul-int div-int rem-int and-int or-int xor-int shl-int shr-int ushr-int add-long sub-long mul-long div-long rem-long and-long or-long xor-long shl-long shr-long ushr-long add-float sub-float mul-float div-float rem-float add-double sub-double mul-double div-double rem-double','23x');ops(0xb0,'add-int/2addr sub-int/2addr mul-int/2addr div-int/2addr rem-int/2addr and-int/2addr or-int/2addr xor-int/2addr shl-int/2addr shr-int/2addr ushr-int/2addr add-long/2addr sub-long/2addr mul-long/2addr div-long/2addr rem-long/2addr and-long/2addr or-long/2addr xor-long/2addr shl-long/2addr shr-long/2addr ushr-long/2addr add-float/2addr sub-float/2addr mul-float/2addr div-float/2addr rem-float/2addr add-double/2addr sub-double/2addr mul-double/2addr div-double/2addr rem-double/2addr','12x');ops(0xd0,'add-int/lit16 rsub-int mul-int/lit16 div-int/lit16 rem-int/lit16 and-int/lit16 or-int/lit16 xor-int/lit16','22s');ops(0xd8,'add-int/lit8 rsub-int/lit8 mul-int/lit8 div-int/lit8 rem-int/lit8 and-int/lit8 or-int/lit8 xor-int/lit8 shl-int/lit8 shr-int/lit8 ushr-int/lit8','22b');ops(0xfa,'invoke-polymorphic','45cc');ops(0xfb,'invoke-polymorphic/range','4rcc');ops(0xfc,'invoke-custom','35c');ops(0xfd,'invoke-custom/range','3rc');ops(0xfe,'const-method-handle const-method-type','21c')

def signed(v,bits): return v-(1<<bits) if v&(1<<(bits-1)) else v

class Dex:
 def __init__(self,data):
  self.d=bytearray(data);d=self.d
  assert d[:4]==b'dex\n'
  self.version=d[4:7].decode();assert struct.unpack_from('<I',d,32)[0]==len(d)
  self.strings=[];self.string_offsets=[]
  sn,so=struct.unpack_from('<II',d,56)
  for i in range(sn):
   p=struct.unpack_from('<I',d,so+4*i)[0];n,q=uleb(d,p);r=d.index(0,q)
   raw=bytes(d[q:r]).replace(b'\xc0\x80',b'\0')
   self.strings.append(raw.decode('utf-8','surrogatepass'));self.string_offsets.append((p,q,r,n))
  tn,to=struct.unpack_from('<II',d,64);self.types=[self.strings[struct.unpack_from('<I',d,to+4*i)[0]] for i in range(tn)]
  pn,po=struct.unpack_from('<II',d,72);self.protos=[]
  for i in range(pn):
   short,ret,off=struct.unpack_from('<III',d,po+i*12)
   n=struct.unpack_from('<I',d,off)[0] if off else 0
   params=[self.types[x] for x in struct.unpack_from('<'+'H'*n,d,off+4)] if n else []
   self.protos.append('('+''.join(params)+')'+self.types[ret])
  fn,fo=struct.unpack_from('<II',d,80);self.fields=[]
  for i in range(fn):
   c,t,n=struct.unpack_from('<HHI',d,fo+i*8);self.fields.append(self.types[c]+'->'+self.strings[n]+':'+self.types[t])
  mn,mo=struct.unpack_from('<II',d,88);self.methods=[]
  for i in range(mn):
   c,p,n=struct.unpack_from('<HHI',d,mo+i*8);self.methods.append(self.types[c]+'->'+self.strings[n]+self.protos[p])
  cn,co=struct.unpack_from('<II',d,96);self.classes={};self.defs={}
  for i in range(cn):
   c,flags,sup,interfaces,src,anno,off,static=struct.unpack_from('<8I',d,co+i*32)
   cl={'name':self.types[c],'flags':flags,'super':self.types[sup] if sup!=0xffffffff else None,'data_off':off,'methods':[], 'fields':[], 'def_off':co+i*32};self.classes[cl['name']]=cl
   if off:
    counts=[];p=off
    for j in range(4): n,p=uleb(d,p);counts.append(n)
    for cnt in counts[:2]:
     idx=0
     for j in range(cnt):delta,p=uleb(d,p);flags,p=uleb(d,p);idx+=delta;cl['fields'].append((idx,flags))
    for cnt in counts[2:]:
     idx=0
     for j in range(cnt):
      delta,p=uleb(d,p);flags,p=uleb(d,p);q=p;code,p=uleb(d,p);idx+=delta
      m={'idx':idx,'name':self.methods[idx],'flags':flags,'code':code,'encoded_off':q,'encoded_len':p-q};self.defs[idx]=m;cl['methods'].append(m)
 def insns(self,m):
  if isinstance(m,int):m=self.defs[m]
  off=m['code']
  if not off:return
  regs,ins,outs,tries,debug,n=struct.unpack_from('<HHHHII',self.d,off)
  code=struct.unpack_from('<'+'H'*n,self.d,off+16);pc=0
  while pc<n:
   u=code[pc];op=u&255;payload=False
   if op==0 and u!=0:
    payload=True
    if u==0x100: ln=4+2*code[pc+1];name='packed-switch-payload'
    elif u==0x200:ln=2+4*code[pc+1];name='sparse-switch-payload'
    elif u==0x300:ln=4+(code[pc+1]*(code[pc+2]+(code[pc+3]<<16))+1)//2;name='array-data-payload'
    else:raise ValueError(f'bad payload {u:x} at {m["name"]} {pc}')
    fmt='payload'
   else:
    if op not in OP: raise ValueError(f'unknown op {op:x} {m["name"]} {pc}')
    name,fmt=OP[op];ln=int(fmt[0])
   v=code[pc:pc+ln]
   assert len(v)==ln,(m['name'],pc,n,ln)
   ref=None;refkind=None;target=None;rs=[];text=''
   a=u>>8;b=(u>>12)&15;c=(u>>8)&15
   if fmt=='12x':rs=[c,b];text=f'v{c}, v{b}'
   elif fmt in ('11x',):rs=[a];text=f'v{a}'
   elif fmt=='11n':rs=[c];text=f'v{c}, #{signed(b,4)}'
   elif fmt=='22x':rs=[a,v[1]];text=f'v{a}, v{v[1]}'
   elif fmt=='32x':rs=[v[1],v[2]];text=f'v{v[1]}, v{v[2]}'
   elif fmt in ('21s','21h'):rs=[a];text=f'v{a}, #{signed(v[1],16)}'
   elif fmt=='31i':rs=[a];text=f'v{a}, #{signed(v[1]|v[2]<<16,32)}'
   elif fmt=='51l':rs=[a];text=f'v{a}, #{sum(x<<(16*j) for j,x in enumerate(v[1:]))}'
   elif fmt in ('21c','22c','31c'):
    ref=v[1] if fmt!='31c' else v[1]|v[2]<<16
    rs=[c,b] if fmt=='22c' else [a]
    if op in (0x1a,0x1b):refkind='string'
    elif op in (0x1c,0x1f,0x20,0x22,0x23):refkind='type'
    elif 0x52<=op<=0x6d:refkind='field'
    elif op==0xfe:refkind='method-handle'
    elif op==0xff:refkind='proto'
    text=', '.join('v'+str(x) for x in rs)
   elif fmt in ('35c','45cc'):
    count=b;rs=[v[2]&15,(v[2]>>4)&15,(v[2]>>8)&15,(v[2]>>12)&15,c][:count];ref=v[1];refkind='type' if op==0x24 else ('callsite' if op==0xfc else 'method');text='{'+','.join('v'+str(x) for x in rs)+'}'
   elif fmt in ('3rc','4rcc'):
    rs=list(range(v[2],v[2]+a));ref=v[1];refkind='type' if op==0x25 else ('callsite' if op==0xfd else 'method');text='{'+','.join('v'+str(x) for x in rs)+'}'
   elif fmt=='23x':rs=[a,v[1]&255,v[1]>>8];text=', '.join('v'+str(x) for x in rs)
   elif fmt=='22s':rs=[c,b];text=f'v{c},v{b},#{signed(v[1],16)}'
   elif fmt=='22b':rs=[a,v[1]&255];text=f'v{a},v{v[1]&255},#{signed(v[1]>>8,8)}'
   elif fmt=='10t':target=pc+signed(a,8)
   elif fmt=='20t':target=pc+signed(v[1],16)
   elif fmt in ('30t','31t'):target=pc+signed(v[1]|v[2]<<16,32);rs=[a] if fmt=='31t' else [];text=f'v{a}' if rs else ''
   elif fmt=='21t':target=pc+signed(v[1],16);rs=[a];text=f'v{a}'
   elif fmt=='22t':target=pc+signed(v[1],16);rs=[c,b];text=f'v{c},v{b}'
   if target is not None:text+=' -> '+hex(target)
   if ref is not None:
    arr={'string':self.strings,'type':self.types,'field':self.fields,'method':self.methods,'proto':self.protos}.get(refkind)
    reftext=arr[ref] if arr is not None else str(ref)
    text+=', '+repr(reftext)
   yield {'pc':pc,'off':off+16+pc*2,'op':op,'name':name,'fmt':fmt,'length':ln,'units':v,'regs':rs,'ref':ref,'refkind':refkind,'target':target,'text':text,'payload':payload}
   pc+=ln
 def dump(self,m):
  if isinstance(m,str):m=self.defs[self.methods.index(m)]
  if isinstance(m,int):m=self.defs[m]
  print(f'\n{m["name"]} flags={m["flags"]:x} code={m["code"]:x}')
  if m['code']:
   print('regs,ins,outs,tries,debug,units=',struct.unpack_from('<HHHHII',self.d,m['code']))
   for x in self.insns(m):print(f'{x["pc"]:04x}: {x["name"]:24s} {x["text"]}')
 def fix(self):
  self.d[12:32]=hashlib.sha1(self.d[32:]).digest();struct.pack_into('<I',self.d,8,zlib.adler32(self.d[12:])&0xffffffff)
  return bytes(self.d)
 def validate(self):
  assert bytes(self.d[12:32])==hashlib.sha1(self.d[32:]).digest()
  assert struct.unpack_from('<I',self.d,8)[0]==zlib.adler32(self.d[12:])&0xffffffff
  count=0
  for m in self.defs.values():
   if not m['code']:continue
   ins=list(self.insns(m));valid={i['pc'] for i in ins};n=struct.unpack_from('<I',self.d,m['code']+12)[0]
   for i in ins:
    if i['target'] is not None:assert i['target'] in valid,(m['name'],i)
   count+=1
  return {'version':self.version,'classes':len(self.classes),'methods':len(self.methods),'code_items':count}

if __name__=='__main__':
 d=Dex(Path(sys.argv[1]).read_bytes());print(d.validate())
 if len(sys.argv)>2:
  for m in d.defs.values():
   if sys.argv[2] in m['name']:d.dump(m)
