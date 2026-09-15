"""JDK 8 class-file to DEX compiler for the project's small Java extension.

The compiler retains JVM local/operand-stack slots as DEX registers. It emits
standard DEX 035, named references, explicit exception tables and sorted ID pools.
The build only feeds extension classes; Android/API signatures are compile stubs.
"""
import struct, re, hashlib, zlib, collections, json
from pathlib import Path

class Reader:
 def __init__(self,b):self.b=b;self.p=0
 def raw(self,n):v=self.b[self.p:self.p+n];self.p+=n;return v
 def u1(self):return self.raw(1)[0]
 def u2(self):return struct.unpack('>H',self.raw(2))[0]
 def u4(self):return struct.unpack('>I',self.raw(4))[0]

def descriptor(s):return s if s.startswith('[') else 'L'+s+';'
def params(s):return re.findall(r'\[*[BCDFIJSZV]|\[*L[^;]+;',s)
def cat(t):return 'R' if t[0] in 'L[' else ('I' if t in 'BCISZ' else t)
def width(t):return 2 if t in ('J','D') else 1

def read_class(path):
 r=Reader(Path(path).read_bytes());assert r.u4()==0xcafebabe;r.u2();version=r.u2();assert version<=52
 cp=[None];count=r.u2()
 while len(cp)<count:
  t=r.u1()
  if t==1:
   b=r.raw(r.u2()).replace(b'\xc0\x80',b'\0');v=b.decode('utf-8','surrogatepass')
  elif t in (7,8,16):v=r.u2()
  elif t in (9,10,11,12,18):v=(r.u2(),r.u2())
  elif t in (3,4):v=r.u4()
  elif t in (5,6):v=struct.unpack('>Q',r.raw(8))[0]
  elif t==15:v=(r.u1(),r.u2())
  else:raise ValueError(('constant pool tag',t))
  cp.append((t,v))
  if t in (5,6):cp.append(None)
 def utf(i):return cp[i][1]
 def cls(i):return descriptor(utf(cp[i][1]))
 def ref(i):
  t,(c,nt)=cp[i];n,d=cp[nt][1];return cls(c),utf(n),utf(d)
 def attrs(rr):return {utf(rr.u2()):rr.raw(rr.u4()) for _ in range(rr.u2())}
 flags=r.u2();name=cls(r.u2());sup=cls(r.u2());interfaces=[cls(r.u2()) for _ in range(r.u2())]
 fields=[]
 for _ in range(r.u2()):
  f,n,t=r.u2(),utf(r.u2()),utf(r.u2());a=attrs(r);cv=cp[struct.unpack('>H',a['ConstantValue'])[0]] if 'ConstantValue' in a else None
  fields.append(dict(flags=f,name=n,type=t,value=cv))
 methods=[]
 for _ in range(r.u2()):
  f,n,d=r.u2(),utf(r.u2()),utf(r.u2());a=attrs(r);m=dict(flags=f,name=n,desc=d)
  if 'Code' in a:
   cr=Reader(a['Code']);m['stack']=cr.u2();m['locals']=cr.u2();m['code']=cr.raw(cr.u4());m['catch']=[(cr.u2(),cr.u2(),cr.u2(),cr.u2()) for _ in range(cr.u2())];attrs(cr)
  methods.append(m)
 a=attrs(r);assert r.p==len(r.b)
 return dict(name=name,super=sup,flags=flags&~0x20,interfaces=interfaces,fields=fields,methods=methods,cp=cp,utf=utf,cls=cls,ref=ref,source=utf(struct.unpack('>H',a['SourceFile'])[0]) if 'SourceFile' in a else 'Extensions.java')

# JVM instruction decoding, including switch alignment and wide locals.
ONE={16,18,21,22,23,24,25,54,55,56,57,58,169,188}
TWO=set(range(153,169))|{17,19,20,132,178,179,180,181,182,183,184,187,189,192,193,198,199}
def decode(code):
 out=[];p=0
 while p<len(code):
  st=p;op=code[p];p+=1;v=[]
  if op in ONE:v=[code[p]];p+=1
  elif op in TWO:v=[int.from_bytes(code[p:p+2],'big')];p+=2
  elif op in (185,186):v=[int.from_bytes(code[p:p+2],'big'),code[p+2],code[p+3]];p+=4
  elif op==197:v=[int.from_bytes(code[p:p+2],'big'),code[p+2]];p+=3
  elif op in (200,201):v=[int.from_bytes(code[p:p+4],'big',signed=True)];p+=4
  elif op==196:
   op=code[p];p+=1;v=[int.from_bytes(code[p:p+2],'big')];p+=2
   if op==132:v.append(int.from_bytes(code[p:p+2],'big',signed=True));p+=2
  elif op in (170,171):
   p=(p+3)&~3;default=int.from_bytes(code[p:p+4],'big',signed=True);p+=4
   if op==170:
    low,high=struct.unpack_from('>ii',code,p);p+=8;cases=[]
    for k in range(low,high+1):cases.append((k,st+int.from_bytes(code[p:p+4],'big',signed=True)));p+=4
   else:
    n=int.from_bytes(code[p:p+4],'big');p+=4;cases=[]
    for i in range(n):k,off=struct.unpack_from('>ii',code,p);p+=8;cases.append((k,st+off))
   v=[st+default,cases]
  out.append((st,op,v,p))
 return out

def uleb(n):
 out=[]
 while n>=128:out.append((n&127)|128);n>>=7
 return bytes(out+[n])
def sleb(n):
 out=[]
 while True:
  b=n&127;n>>=7;done=(n==0 and not b&64) or (n==-1 and b&64)
  out.append(b if done else b|128)
  if done:return bytes(out)

def signature(c,n,p):return c+'->'+n+p
def shorty(p):return ''.join(('L' if x[0] in 'L[' else x) for x in [p[p.index(')')+1:]]+params(p[1:p.index(')')]))

class Pools:
 def __init__(self,classes):
  ts=set();ss=set();ms=set();fs=set();ps=set()
  def typ(t):ts.add(t);ss.add(t)
  def method(c,n,p):typ(c);ss.add(n);ps.add(p);ms.add((c,n,p))
  def field(c,n,t):typ(c);typ(t);ss.add(n);fs.add((c,n,t))
  for cl in classes:
   typ(cl['name']);typ(cl['super']);ss.add(cl['source'])
   for i in cl['interfaces']:typ(i)
   for f in cl['fields']:field(cl['name'],f['name'],f['type'])
   for m in cl['methods']:method(cl['name'],m['name'],m['desc'])
   for i,c in enumerate(cl['cp']):
    if c is None:continue
    tag,v=c
    if tag==7:typ(cl['cls'](i))
    elif tag==8:ss.add(cl['utf'](v))
    elif tag in (9,10,11):
     c,n,t=cl['ref'](i)
     (field if tag==9 else method)(c,n,t)
   # Type descriptors generated for primitive and reference arrays.
   for m in cl['methods']:
    if 'code' in m:
     for pc,op,v,nxt in decode(m['code']):
      if op==188:typ('['+{4:'Z',5:'C',6:'F',7:'D',8:'B',9:'S',10:'I',11:'J'}[v[0]])
      elif op==189:typ('['+cl['cls'](v[0]))
      for lo,hi,handler,ci in m['catch']:
       if ci:typ(cl['cls'](ci))
  for p in ps:
   ss.add(shorty(p))
   for t in params(p):typ(t)
  self.strings=sorted(ss,key=lambda x:x.encode('utf-16-be','surrogatepass'));self.si={s:i for i,s in enumerate(self.strings)}
  self.types=sorted(ts,key=self.si.get);self.ti={s:i for i,s in enumerate(self.types)}
  def pk(p):return (self.ti[p[p.index(')')+1:]],tuple(self.ti[t] for t in params(p[1:p.index(')')])))
  self.protos=sorted(ps,key=pk);self.pi={p:i for i,p in enumerate(self.protos)}
  self.fields=sorted(fs,key=lambda x:(self.ti[x[0]],self.si[x[1]],self.ti[x[2]]));self.fi={v:i for i,v in enumerate(self.fields)}
  self.methods=sorted(ms,key=lambda x:(self.ti[x[0]],self.si[x[1]],self.pi[x[2]]));self.mi={v:i for i,v in enumerate(self.methods)}

class Emitter:
 def __init__(self):self.u=[];self.labels={};self.fix=[];self.payloads=[]
 def emit(self,*u):self.u.extend(i&65535 for i in u)
 def mark(self,l):self.labels[l]=len(self.u)
 def move(self,d,s,t='I'):
  op=7 if t=='R' else (4 if t in ('J','D') else 1)
  if d==s:return
  if max(d,s)<16:self.emit(op|d<<8|s<<12)
  else:self.emit((op+1)|d<<8,s)
 def const(self,d,v,t='I'):
  if t in ('J','D'):
   self.emit(0x18|d<<8,*[(v>>(16*i))&65535 for i in range(4)])
  else:self.emit(0x14|d<<8,v&65535,(v>>16)&65535)
 def branch(self,op,r,target,r2=None):
  pc=len(self.u)
  if op==0x2a:self.emit(op,0,0);self.fix.append((pc+1,pc,target,32))
  elif r2 is None:self.emit(op|r<<8,0);self.fix.append((pc+1,pc,target,16))
  else:self.emit(op|r<<8|r2<<12,0);self.fix.append((pc+1,pc,target,16))
 def finish(self):
  for pc,reg,default,cases in self.payloads:
   if len(self.u)%2:self.emit(0)
   off=len(self.u)-pc;self.u[pc+1]=off&65535;self.u[pc+2]=(off>>16)&65535
   self.emit(0x200,len(cases))
   for k,t in cases:self.emit(k&65535,(k>>16)&65535)
   for k,t in cases:
    delta=self.labels[t]-pc;self.emit(delta&65535,(delta>>16)&65535)
  for at,pc,t,bits in self.fix:
   delta=self.labels[t]-pc;assert -(1<<(bits-1))<=delta<1<<(bits-1),(pc,t,delta)
   self.u[at]=delta&65535
   if bits==32:self.u[at+1]=(delta>>16)&65535
  return struct.pack('<'+'H'*len(self.u),*self.u)

def transfer(cl,m,ins,stack):
 """Returns outgoing abstract operand stack and successor JVM offsets."""
 pc,op,v,nxt=ins;s=list(stack);jump=[];terminal=False
 def pop(n=1):
  assert len(s)>=n,(m['name'],pc,op,s,n)
  out=s[-n:] if n else []
  if n:del s[-n:]
  return out
 def push(t):s.append(t)
 if op==0:pass
 elif op==1:push('R')
 elif 2<=op<=8 or op in (16,17):push('I')
 elif op in (9,10):push('J')
 elif op in (11,12,13):push('F')
 elif op in (14,15):push('D')
 elif op in (18,19,20):push({3:'I',4:'F',5:'J',6:'D',7:'R',8:'R'}[cl['cp'][v[0]][0]])
 elif 21<=op<=25:push(['I','J','F','D','R'][op-21])
 elif 26<=op<=45:push(['I','J','F','D','R'][(op-26)//4])
 elif 46<=op<=53:pop(2);push(['I','J','F','D','R','I','I','I'][op-46])
 elif 54<=op<=78:pop()
 elif 79<=op<=86:pop(3)
 elif op==87:pop()
 elif op==88:
  x=pop()[0]
  if width(x)==1:pop()
 elif op==89:push(s[-1])
 elif op==90:
  a,b=pop(2);s.extend([b,a,b])
 elif op==91:
  if width(s[-2])==2:a,b=pop(2);s.extend([b,a,b])
  else:a,b,c=pop(3);s.extend([c,a,b,c])
 elif op==92:
  if width(s[-1])==2:push(s[-1])
  else:s.extend(s[-2:])
 elif op==95:a,b=pop(2);s.extend([b,a])
 elif 96<=op<=115:pop(2);push(['I','J','F','D'][(op-96)%4])
 elif 116<=op<=119:pop();push(['I','J','F','D'][op-116])
 elif 120<=op<=131:pop(2);push('I' if op%2==0 else 'J')
 elif op==132:pass
 elif 133<=op<=147:
  pop();push({133:'J',134:'F',135:'D',136:'I',137:'F',138:'D',139:'I',140:'J',141:'D',142:'I',143:'J',144:'F',145:'I',146:'I',147:'I'}[op])
 elif 148<=op<=152:pop(2);push('I')
 elif 153<=op<=158 or op in (198,199):pop();jump=[pc+struct.unpack('>h',struct.pack('>H',v[0]))[0]]
 elif 159<=op<=166:pop(2);jump=[pc+struct.unpack('>h',struct.pack('>H',v[0]))[0]]
 elif op in (167,200):jump=[pc+(v[0] if op==200 else struct.unpack('>h',struct.pack('>H',v[0]))[0])];terminal=True
 elif op in (170,171):pop();jump=[v[0]]+[t for k,t in v[1]];terminal=True
 elif 172<=op<=177:
  if op!=177:pop()
  terminal=True
 elif 178<=op<=181:
  c,n,t=cl['ref'](v[0]);t=cat(t)
  if op==178:push(t)
  elif op==179:pop()
  elif op==180:pop();push(t)
  else:pop(2)
 elif 182<=op<=185:
  c,n,p=cl['ref'](v[0]);pt=params(p[1:p.index(')')]);pop(len(pt)+(op!=184));t=p[p.index(')')+1:]
  if t!='V':push(cat(t))
 elif op==187:push('R')
 elif op in (188,189):pop();push('R')
 elif op==190:pop();push('I')
 elif op==191:pop();terminal=True
 elif op==192:pass
 elif op==193:pop();push('I')
 elif op in (194,195):pop()
 else:raise ValueError(('JVM instruction',hex(op),cl['name'],m['name'],pc))
 return tuple(s),jump+([] if terminal else [nxt])

def compile_method(cl,m,p):
 ops=decode(m['code']);by_pc={x[0]:x for x in ops};incoming={0:()};queue=collections.deque([0]);handlerpcs={c[2] for c in m['catch']}
 for hp in handlerpcs:incoming[hp]=('R',);queue.append(hp)
 while queue:
  pc=queue.popleft();out,succ=transfer(cl,m,by_pc[pc],incoming[pc])
  for target in succ:
   assert target in by_pc,(m['name'],pc,target)
   if target in incoming:assert incoming[target]==out,(m['name'],pc,target,incoming[target],out)
   else:incoming[target]=out;queue.append(target)
 e=Emitter();localbase=8;stackbase=localbase+m['locals'];argtypes=([] if m['flags']&8 else ['R'])+[cat(t) for t in params(m['desc'][1:m['desc'].index(')')])]
 inscount=sum(width(t) for t in argtypes);regcount=stackbase+m['stack']+inscount;assert regcount<256
 pos=0
 for t in argtypes:e.move(localbase+pos,regcount-inscount+pos,t);pos+=width(t)
 maxouts=0
 for ins in ops:
  pc,op,v,nxt=ins;e.mark(pc)
  if pc not in incoming:continue
  ss=list(incoming[pc]);sr=[];top=stackbase
  for t in ss:sr.append(top);top+=width(t)
  if pc in handlerpcs:e.emit(0x0d|stackbase<<8)
  def loadidx():return v[0] if 21<=op<=25 else (op-26)%4
  def fieldop(tag,t):return tag+({'J':1,'D':1,'R':2,'Z':3,'B':4,'C':5,'S':6}.get(t,0))
  if op==0:pass
  elif op==1:e.const(top,0)
  elif 2<=op<=8:e.const(top,op-3)
  elif op in (9,10):e.const(top,op-9,'J')
  elif op in (11,12,13):e.const(top,struct.unpack('<I',struct.pack('<f',op-11))[0])
  elif op in (14,15):e.const(top,struct.unpack('<Q',struct.pack('<d',op-14))[0],'D')
  elif op==16:e.const(top,v[0]-256 if v[0]&128 else v[0])
  elif op==17:e.const(top,v[0]-65536 if v[0]&32768 else v[0])
  elif op in (18,19,20):
   tag,val=cl['cp'][v[0]]
   if tag in (3,4,5,6):e.const(top,val,'J' if tag in (5,6) else 'I')
   elif tag==8:e.emit(0x1a|top<<8,p.si[cl['utf'](val)])
   elif tag==7:e.emit(0x1c|top<<8,p.ti[cl['cls'](v[0])])
  elif 21<=op<=45:
   t=['I','J','F','D','R'][op-21 if op<=25 else (op-26)//4];e.move(top,localbase+loadidx(),t)
  elif 46<=op<=53:e.emit([0x44,0x45,0x44,0x45,0x46,0x48,0x49,0x4a][op-46]|sr[-2]<<8,sr[-2]|sr[-1]<<8)
  elif 54<=op<=78:
   idx=v[0] if op<=58 else (op-59)%4;t=['I','J','F','D','R'][op-54 if op<=58 else (op-59)//4];e.move(localbase+idx,sr[-1],t)
  elif 79<=op<=86:e.emit([0x4b,0x4c,0x4b,0x4c,0x4d,0x4f,0x50,0x51][op-79]|sr[-1]<<8,sr[-3]|sr[-2]<<8)
  elif op in (87,88):pass
  elif op in (89,90,91,92,95):
   # Save affected stack values in low scratch registers, then permute copies.
   if op==89:ids=[len(ss)-1,len(ss)-1];start=len(ss)-1
   elif op==90:ids=[len(ss)-1,len(ss)-2,len(ss)-1];start=len(ss)-2
   elif op==91:
    n=2 if width(ss[-2])==2 else 3;start=len(ss)-n;ids=[len(ss)-1]+list(range(start,len(ss)-1))+[len(ss)-1]
   elif op==92:
    n=1 if width(ss[-1])==2 else 2;start=len(ss)-n;ids=list(range(start,len(ss)))*2
   else:start=len(ss)-2;ids=[len(ss)-1,len(ss)-2]
   tmp={};q=0
   for i in range(start,len(ss)):tmp[i]=q;e.move(q,sr[i],ss[i]);q+=width(ss[i])
   dst=sr[start]
   for i in ids:e.move(dst,tmp[i],ss[i]);dst+=width(ss[i])
  elif 96<=op<=115:
   fam=(op-96)//4;t=(op-96)%4;dop=[0x90,0x9b,0xa6,0xab][t]+fam;e.emit(dop|sr[-2]<<8,sr[-2]|sr[-1]<<8)
  elif 116<=op<=119:
   e.move(0,sr[-1],ss[-1]);dop=[0x7b,0x7d,0x7f,0x80][op-116];e.emit(dop);e.move(sr[-1],0,ss[-1])
  elif 120<=op<=131:
   dop={120:0x98,121:0xa3,122:0x99,123:0xa4,124:0x9a,125:0xa5,126:0x95,127:0xa0,128:0x96,129:0xa1,130:0x97,131:0xa2}[op];e.emit(dop|sr[-2]<<8,sr[-2]|sr[-1]<<8)
  elif op==132:
   if len(v)==2:idx,amount=v
   else:idx=v[0]>>8;amount=v[0]&255;amount=amount-256 if amount&128 else amount
   if -128<=amount<=127:e.emit(0xd8|(localbase+idx)<<8,(localbase+idx)|((amount&255)<<8))
   else:e.move(0,localbase+idx);e.emit(0xd0,amount&65535);e.move(localbase+idx,0)
  elif 133<=op<=147:
   dop={133:0x81,134:0x82,135:0x83,136:0x84,137:0x85,138:0x86,139:0x87,140:0x88,141:0x89,142:0x8a,143:0x8b,144:0x8c,145:0x8d,146:0x8e,147:0x8f}[op]
   t=transfer(cl,m,ins,ss)[0][-1];e.move(0,sr[-1],ss[-1]);e.emit(dop);e.move(sr[-1],0,t)
  elif 148<=op<=152:e.emit({148:0x31,149:0x2d,150:0x2e,151:0x2f,152:0x30}[op]|sr[-2]<<8,sr[-2]|sr[-1]<<8)
  elif 153<=op<=158 or op in (198,199):
   target=pc+(v[0]-65536 if v[0]&32768 else v[0]);dop=0x38+(op-153 if op<=158 else op-198);e.branch(dop,sr[-1],target)
  elif 159<=op<=166:
   target=pc+(v[0]-65536 if v[0]&32768 else v[0]);e.move(0,sr[-2],ss[-2]);e.move(2,sr[-1],ss[-1]);dop=0x32+(op-159 if op<=164 else op-165);e.branch(dop,0,target,2)
  elif op in (167,200):e.branch(0x2a,0,pc+(v[0] if op==200 else v[0]-65536 if v[0]&32768 else v[0]))
  elif op in (170,171):
   at=len(e.u);e.emit(0x2c|sr[-1]<<8,0,0);e.payloads.append((at,sr[-1],v[0],v[1]));e.branch(0x2a,0,v[0])
  elif 172<=op<=177:
   if op==177:e.emit(0x0e)
   else:e.emit([0x0f,0x10,0x0f,0x10,0x11][op-172]|sr[-1]<<8)
  elif 178<=op<=181:
   c,n,t=cl['ref'](v[0]);fi=p.fi[(c,n,t)];ct=cat(t);ft=t if t in 'ZBCS' else ct
   if op==178:e.emit(fieldop(0x60,ft)|top<<8,fi)
   elif op==179:e.emit(fieldop(0x67,ft)|sr[-1]<<8,fi)
   elif op==180:
    e.move(2,sr[-1],'R');e.emit(fieldop(0x52,ft)|2<<12,fi);e.move(sr[-1],0,ct)
   else:
    e.move(2,sr[-2],'R');e.move(0,sr[-1],ct);e.emit(fieldop(0x59,ft)|2<<12,fi)
  elif 182<=op<=185:
   c,n,desc=cl['ref'](v[0]);pt=params(desc[1:desc.index(')')]);nvals=len(pt)+(op!=184);start=sr[-nvals] if nvals else top;cnt=sum(width(t) for t in pt)+(op!=184);maxouts=max(maxouts,cnt)
   if op==184:dop=0x77
   elif op==185:dop=0x78
   elif op==183:dop=0x76 if n=='<init>' or c==cl['name'] else 0x75
   else:dop=0x74
   e.emit(dop|cnt<<8,p.mi[(c,n,desc)],start)
   rt=desc[desc.index(')')+1:]
   if rt!='V':e.emit((0x0c if cat(rt)=='R' else 0x0b if width(rt)==2 else 0x0a)|start<<8)
  elif op==187:e.emit(0x22|top<<8,p.ti[cl['cls'](v[0])])
  elif op in (188,189):
   t='['+({4:'Z',5:'C',6:'F',7:'D',8:'B',9:'S',10:'I',11:'J'}[v[0]] if op==188 else cl['cls'](v[0]));e.move(1,sr[-1]);e.emit(0x23|1<<12,p.ti[t]);e.move(sr[-1],0,'R')
  elif op==190:e.move(1,sr[-1],'R');e.emit(0x21|1<<12);e.move(sr[-1],0)
  elif op==191:e.emit(0x27|sr[-1]<<8)
  elif op==192:e.emit(0x1f|sr[-1]<<8,p.ti[cl['cls'](v[0])])
  elif op==193:e.move(1,sr[-1],'R');e.emit(0x20|1<<12,p.ti[cl['cls'](v[0])]);e.move(sr[-1],0)
  elif op in (194,195):e.emit((0x1d if op==194 else 0x1e)|sr[-1]<<8)
  else:raise ValueError(('emit',op))
 e.mark(len(m['code']));body=e.finish();tries=[]
 boundaries=sorted({n for lo,hi,h,ci in m['catch'] for n in (lo,hi)})
 for lo,hi in zip(boundaries,boundaries[1:]):
  catches=[(p.ti[cl['cls'](ci)] if ci else None,e.labels[h]) for l,r,h,ci in m['catch'] if l<=lo and hi<=r]
  if not catches:continue
  unique=[]
  for t,h in catches:
   if all(t!=x[0] for x in unique):unique.append((t,h))
   if t is None:break
  st=e.labels[lo];en=e.labels[hi];assert en-st<=65535
  if tries and tries[-1][0]+tries[-1][1]==st and tries[-1][2]==unique:tries[-1]=(tries[-1][0],en-tries[-1][0],unique)
  else:tries.append((st,en-st,unique))
 handlers=[]
 for _,_,cs in tries:
  if cs not in handlers:handlers.append(cs)
 hb=bytearray(uleb(len(handlers)));hoff=[]
 for cs in handlers:
  hoff.append(len(hb));hasall=cs[-1][0] is None;num=len(cs)-hasall;hb+=sleb(-num if hasall else num)
  for typ,addr in cs:
   if typ is not None:hb+=uleb(typ)
   hb+=uleb(addr)
 header=struct.pack('<HHHHII',regcount,inscount,maxouts,len(tries),0,len(body)//2)
 if tries:
  padding=b'\0\0' if len(body)%4 else b''
  tb=b''.join(struct.pack('<IHH',st,cnt,hoff[handlers.index(cs)]) for st,cnt,cs in tries)
  result=header+body+padding+tb+hb
 else:result=header+body
 return result,{'class':cl['name'],'method':m['name']+m['desc'],'jvm_instructions':len(ops),'dex_units':len(body)//2,'registers':regcount,'try_ranges':len(tries)}

def build(classes):
 p=Pools(classes);coff={};reports=[];compiled={}
 for cl in classes:
  for m in cl['methods']:
   if 'code' in m:compiled[(cl['name'],m['name'],m['desc'])],rr=compile_method(cl,m,p);reports.append(rr)
 # ID sections have fixed-size records.
 hdr=112;so=hdr;to=so+4*len(p.strings);po=to+4*len(p.types);fo=po+12*len(p.protos);mo=fo+8*len(p.fields);cdo=mo+8*len(p.methods);dataoff=cdo+32*len(classes)
 b=bytearray(dataoff);maps=[]
 def section(t,c,o):
  if c:maps.append((t,0,c,o))
 def align():
  while len(b)%4:b.append(0)
 def push(raw,aligned=False):
  if aligned:align()
  at=len(b);b.extend(raw);return at
 def encstr(s):
  raw=s.encode('utf-16-be','surrogatepass');units=[int.from_bytes(raw[i:i+2],'big') for i in range(0,len(raw),2)];out=bytearray()
  for c in units:
   if c==0:out+=b'\xc0\x80'
   elif c<128:out.append(c)
   elif c<2048:out+=bytes([0xc0|(c>>6),0x80|(c&63)])
   else:out+=bytes([0xe0|(c>>12),0x80|((c>>6)&63),0x80|(c&63)])
  return uleb(len(units))+out+b'\0'
 section(0x2002,len(p.strings),len(b))
 for i,s in enumerate(p.strings):struct.pack_into('<I',b,so+4*i,push(encstr(s)))
 for i,t in enumerate(p.types):struct.pack_into('<I',b,to+4*i,p.si[t])
 tls={}
 for desc in p.protos:
  ts=tuple(p.ti[t] for t in params(desc[1:desc.index(')')]))
  if ts:tls[ts]=0
 for cl in classes:
  if cl['interfaces']:tls[tuple(sorted(p.ti[t] for t in cl['interfaces']))]=0
 align();section(0x1001,len(tls),len(b))
 for ts in tls:tls[ts]=push(struct.pack('<I',len(ts))+struct.pack('<'+'H'*len(ts),*ts),True)
 for i,desc in enumerate(p.protos):
  ts=tuple(p.ti[t] for t in params(desc[1:desc.index(')')]))
  struct.pack_into('<III',b,po+i*12,p.si[shorty(desc)],p.ti[desc[desc.index(')')+1:]],tls.get(ts,0))
 for i,(c,n,t) in enumerate(p.fields):struct.pack_into('<HHI',b,fo+8*i,p.ti[c],p.ti[t],p.si[n])
 for i,(c,n,d) in enumerate(p.methods):struct.pack_into('<HHI',b,mo+8*i,p.ti[c],p.pi[d],p.si[n])
 align();section(0x2001,len(compiled),len(b))
 for key,code in compiled.items():coff[key]=push(code,True)
 section(0x2000,len(classes),len(b));classoffs={}
 for cl in sorted(classes,key=lambda c:p.ti[c['name']]):
  sf=sorted([f for f in cl['fields'] if f['flags']&8],key=lambda f:p.fi[(cl['name'],f['name'],f['type'])]);inf=sorted([f for f in cl['fields'] if not f['flags']&8],key=lambda f:p.fi[(cl['name'],f['name'],f['type'])])
  dm=sorted([m for m in cl['methods'] if m['flags']&10 or m['name'].startswith('<')],key=lambda m:p.mi[(cl['name'],m['name'],m['desc'])]);vm=sorted([m for m in cl['methods'] if m not in dm],key=lambda m:p.mi[(cl['name'],m['name'],m['desc'])])
  enc=bytearray(b''.join(uleb(len(a)) for a in [sf,inf,dm,vm]))
  for group in (sf,inf):
   last=0
   for f in group:
    idx=p.fi[(cl['name'],f['name'],f['type'])];enc+=uleb(idx-last)+uleb(f['flags']);last=idx
  for group in (dm,vm):
   last=0
   for m in group:
    key=(cl['name'],m['name'],m['desc']);idx=p.mi[key];fl=m['flags']
    if m['name'].startswith('<'):fl|=0x10000
    if fl&0x20:fl=(fl&~0x20)|0x20000
    enc+=uleb(idx-last)+uleb(fl)+uleb(coff.get(key,0));last=idx
  classoffs[cl['name']]=push(enc)
 # ConstantValue for static final fields; zero defaults are explicit up to last initialized value.
 statoffs={};arrays=[]
 for cl in classes:
  fs=sorted([f for f in cl['fields'] if f['flags']&8],key=lambda f:p.fi[(cl['name'],f['name'],f['type'])]);last=max([i for i,f in enumerate(fs) if f['value'] is not None],default=-1)
  if last>=0:
   ar=bytearray(uleb(last+1))
   for f in fs[:last+1]:
    t=f['type'];v=f['value'];tag=cat(t)
    if v is None:
     if tag=='R':ar.append(0x1e)
     elif t=='Z':ar.append(0x1f)
     else:ar+=b'\x04\0'
    elif t=='Z':ar.append(0x1f|(bool(v[1])<<5))
    elif tag=='R':
     assert v[0]==8;idx=p.si[cl['utf'](v[1])];ar+=bytes([0x17|3<<5])+struct.pack('<I',idx)
    else:
     typ={'I':0x04,'F':0x10,'J':0x06,'D':0x11}[tag];size=8 if width(tag)==2 else 4;ar+=bytes([typ|(size-1)<<5])+int(v[1]).to_bytes(size,'little')
   arrays.append((cl['name'],ar))
 section(0x2005,len(arrays),len(b))
 for c,a in arrays:statoffs[c]=push(a)
 for i,cl in enumerate(sorted(classes,key=lambda c:p.ti[c['name']])):
  inter=tuple(sorted(p.ti[t] for t in cl['interfaces']));struct.pack_into('<8I',b,cdo+32*i,p.ti[cl['name']],cl['flags'] & ~0x20,p.ti[cl['super']],tls.get(inter,0),p.si[cl['source']],0,classoffs[cl['name']],statoffs.get(cl['name'],0))
 for t,c,o in [(0,1,0),(1,len(p.strings),so),(2,len(p.types),to),(3,len(p.protos),po),(4,len(p.fields),fo),(5,len(p.methods),mo),(6,len(classes),cdo)]:section(t,c,o)
 align();mapoff=len(b);section(0x1000,1,mapoff);maps.sort(key=lambda x:x[3]);push(struct.pack('<I',len(maps))+b''.join(struct.pack('<HHII',*x) for x in maps))
 b[:8]=b'dex\n035\0';struct.pack_into('<20I',b,32,len(b),112,0x12345678,0,0,mapoff,len(p.strings),so,len(p.types),to,len(p.protos),po,len(p.fields),fo if p.fields else 0,len(p.methods),mo,len(classes),cdo,len(b)-dataoff,dataoff)
 b[12:32]=hashlib.sha1(b[32:]).digest();struct.pack_into('<I',b,8,zlib.adler32(b[12:])&0xffffffff)
 return bytes(b),reports

if __name__=='__main__':
 import argparse
 ap=argparse.ArgumentParser();ap.add_argument('classes');ap.add_argument('output');args=ap.parse_args()
 cls=[read_class(x) for x in sorted(Path(args.classes).rglob('*.class'))];dex,report=build(cls);Path(args.output).write_bytes(dex);Path(args.output+'.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print('compiled',len(cls),'classes',len(report),'methods',len(dex),'bytes')
