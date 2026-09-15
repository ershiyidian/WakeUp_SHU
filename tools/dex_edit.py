"""Small existing-reference DEX assembler and code-section relocator.

No ID is inserted/deleted/reordered. When code sizes change, relocate every
absolute pointer to the shifted data sections, including encoded code_offs.
Method-relative exception/debug programs are preserved for unmodified methods.
"""
import struct
from dexutil import Dex,uleb,sleb,enc_uleb

class Asm:
 def __init__(self,d,base=0): self.d=d;self.u=[];self.labels={};self.fixups=[];self.base=base
 @property
 def pc(self): return self.base+len(self.u)
 def emit(self,*units):
  assert all(0<=x<=0xffff for x in units);self.u.extend(units)
 def raw(self,b): self.u.extend(struct.unpack('<'+'H'*(len(b)//2),b))
 def mark(self,s): self.labels[s]=self.pc
 def const(self,r,v):
  if r<16 and -8<=v<=7: self.emit(0x12|r<<8|(v&15)<<12)
  elif -32768<=v<=32767: self.emit(0x13|r<<8,v&65535)
  else: self.emit(0x14|r<<8,v&65535,(v>>16)&65535)
 def string(self,r,s): self.emit(0x1a|r<<8,self.d.strings.index(s))
 def mov(self,dst,src,obj=False):
  if max(dst,src)<16:self.emit((0x07 if obj else 0x01)|dst<<8|src<<12)
  else:self.emit((0x08 if obj else 0x02)|dst<<8,src)
 def result(self,r,obj=False):self.emit((0x0c if obj else 0x0a)|r<<8)
 def iget(self,a,b,f,op=0x54):self.emit(op|a<<8|b<<12,self.d.fields.index(f))
 def sget(self,a,f,op=0x60):self.emit(op|a<<8,self.d.fields.index(f))
 def invoke(self,s,rs,op=0x6e):
  assert len(rs)<=5 and all(0<=x<16 for x in rs),(s,rs)
  z=list(rs)+[0]*(5-len(rs));self.emit(op|len(rs)<<12|z[4]<<8,self.d.methods.index(s),sum(z[i]<<(4*i) for i in range(4)))
 def invoke_range(self,s,start,count,op=0x74):self.emit(op|count<<8,self.d.methods.index(s),start)
 def typeop(self,op,a,b,t):self.emit(op|a<<8|(0 if b is None else b<<12),self.d.types.index(t))
 def ifz(self,r,target,op=0x38):self.fixups.append((len(self.u),self.pc,target));self.emit(op|r<<8,0)
 def ifcmp(self,a,b,target,op=0x32):self.fixups.append((len(self.u),self.pc,target));self.emit(op|a<<8|b<<12,0)
 def go(self,target):self.fixups.append((len(self.u),self.pc,target));self.emit(0x29,0)
 def lit8(self,op,a,b,v):self.emit(op|a<<8,b|(v&255)<<8)
 def ret(self,r=None,obj=False):self.emit(0x0e if r is None else (0x11 if obj else 0x0f)|r<<8)
 def build(self):
  u=self.u.copy()
  for off,pc,t in self.fixups:
   delta=(self.labels[t] if isinstance(t,str) else t)-pc
   assert -32768<=delta<=32767 and delta!=0,(pc,t)
   u[off+1]=delta&65535
  return struct.pack('<'+'H'*len(u),*u)

def map_items(data):
 p=struct.unpack_from('<I',data,52)[0];n=struct.unpack_from('<I',data,p)[0]
 return [struct.unpack_from('<HHII',data,p+4+12*i) for i in range(n)]

def code_end(data,p):
 regs,ins,outs,nt,dbg,n=struct.unpack_from('<HHHHII',data,p);q=p+16+2*n
 if nt:
  q=(q+3)&~3;q+=nt*8
  nh,q=uleb(data,q)
  for _ in range(nh):
   count,q=sleb(data,q)
   for _ in range(abs(count)): _,q=uleb(data,q);_,q=uleb(data,q)
   if count<=0: _,q=uleb(data,q)
 return q

def standalone_code(original_header,instructions,regs=None,outs=None):
 r,i,o,t,dbg,n=struct.unpack('<HHHHII',original_header)
 assert t==0
 return struct.pack('<HHHHII',r if regs is None else regs,i,o if outs is None else outs,0,0,len(instructions)//2)+instructions

def relocate_code(data,replacements):
 """replacements maps old code offset to full valid code_item bytes."""
 maps=map_items(data);item=next(v for v in maps if v[0]==0x2001);start=item[3];count=item[2]
 end=min(v[3] for v in maps if v[3]>start);pos=start;chunks=[];new=bytearray();offsets={}
 for _ in range(count):
  aligned=(pos+3)&~3;assert not any(data[pos:aligned]);pos=aligned
  while (start+len(new))%4:new.append(0)
  offsets[pos]=start+len(new);q=code_end(data,pos)
  assert q<=end
  raw=replacements.get(pos,bytes(data[pos:q]));assert code_end(raw,0)==len(raw)
  new.extend(raw);chunks.append((pos,q,offsets[pos],len(raw)));pos=q
 assert not any(data[pos:end]);new.extend(data[pos:end])
 while (len(new)-(end-start))%4:new.append(0)
 delta=len(new)-(end-start)
 out=bytearray(data[:start])+new+data[end:]
 def shifted(x):
  if not x:return 0
  assert x<start or x>=end,('Unexpected pointer to code',hex(x))
  return x+delta if x>=end else x
 def put32(p,x):struct.pack_into('<I',out,p,x)
 def shift_ptr(oldp):
  x=struct.unpack_from('<I',data,oldp)[0];put32(oldp+delta if oldp>=end else oldp,shifted(x))
 # header/file/map/data size
 put32(32,len(out));shift_ptr(52);put32(104,struct.unpack_from('<I',data,104)[0]+delta)
 # String pointers, proto parameter pointers, class definition absolute data pointers.
 sn,so=struct.unpack_from('<II',data,56)
 for i in range(sn):shift_ptr(so+i*4)
 pn,po=struct.unpack_from('<II',data,72)
 for i in range(pn):shift_ptr(po+i*12+8)
 cn,co=struct.unpack_from('<II',data,96)
 for i in range(cn):
  for rel in [12,20,24,28]:shift_ptr(co+i*32+rel)
 # Unmodified debug_info bytecode is only referenced by its relocated absolute start.
 for old,q,now,n in chunks:
  debug=struct.unpack_from('<I',out,now+8)[0]
  put32(now+8,shifted(debug))
 # Every class_data encoded method points to its newly positioned code_item.
 cd=next(v for v in maps if v[0]==0x2000);p=cd[3];changed_code_refs=0
 for _ in range(cd[2]):
  counts=[]
  for _ in range(4):n,p=uleb(data,p);counts.append(n)
  for _ in range(sum(counts[:2])):_,p=uleb(data,p);_,p=uleb(data,p)
  for _ in range(sum(counts[2:])):
   _,p=uleb(data,p);_,p=uleb(data,p);oldp=p;code,p=uleb(data,p)
   value=offsets[code] if code else 0;enc=enc_uleb(value)
   assert len(enc)==p-oldp,('ULEB length change requires full class_data rebuild',code,value)
   out[oldp+delta:p+delta]=enc
   changed_code_refs+=code!=value
 # Annotation offsets embedded in sets, ref lists and directories.
 for typ,_,cnt,off in maps:
  p=off
  if typ in (0x1002,0x1003):
   for _ in range(cnt):
    p=(p+3)&~3;n=struct.unpack_from('<I',data,p)[0]
    for i in range(n):shift_ptr(p+4+4*i)
    p+=4+4*n
  elif typ==0x2006:
   for _ in range(cnt):
    p=(p+3)&~3;_,nf,nm,np=struct.unpack_from('<IIII',data,p)
    shift_ptr(p)
    for i in range(nf+nm+np):shift_ptr(p+16+i*8+4)
    p+=16+8*(nf+nm+np)
 oldmap=struct.unpack_from('<I',data,52)[0];newmap=oldmap+delta
 for i,(_,_,_,off) in enumerate(maps):put32(newmap+4+12*i+8,shifted(off) if off!=start else start)
 assert len(out)==len(data)+delta
 fixed=Dex(out).fix();dd=Dex(fixed)
 # ID indexes and class identities MUST be exactly retained.
 orig=Dex(data)
 assert (orig.strings,orig.types,orig.protos,orig.fields,orig.methods)==(dd.strings,dd.types,dd.protos,dd.fields,dd.methods)
 assert orig.classes.keys()==dd.classes.keys() and orig.defs.keys()==dd.defs.keys()
 for name,cl in orig.classes.items():
  nc=dd.classes[name]
  assert (cl['flags'],cl['super'],cl['fields'])==(nc['flags'],nc['super'],nc['fields'])
  for m,nm in zip(cl['methods'],nc['methods']):
   assert (m['name'],m['flags'])==(nm['name'],nm['flags'])
   if m['code']:assert nm['code']==offsets[m['code']]
 for old,q,now,n in chunks:
  expected=bytearray(replacements.get(old,data[old:q]));db=struct.unpack_from('<I',expected,8)[0]
  struct.pack_into('<I',expected,8,shifted(db))
  assert fixed[now:now+n]==expected,('method relocation drift',old)
 report={'code_items':count,'delta_bytes':delta,'replaced_code_items':len(replacements),'changed_encoded_code_offsets':changed_code_refs,
         'id_tables_unchanged':True,'class_fields_methods_preserved':True,'unmodified_code_items_semantically_identical':True}
 return fixed,report
