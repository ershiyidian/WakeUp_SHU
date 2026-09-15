import sys,struct,pathlib
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'tools'));from dexutil import Dex,uleb,sleb
d=Dex(pathlib.Path(sys.argv[1]).read_bytes());out=bytearray()
def w(n):out.extend(struct.pack('>i',n))
def s(t):b=t.encode('utf8','surrogatepass');w(len(b));out.extend(b)
def table(ss):w(len(ss));[s(x) for x in ss]
table(d.strings);table(d.types);table(d.fields);table(d.methods)
names=sys.argv[3:] or ['Lshu/wakeup/ShuImporter;'];ms=[m for name in names for m in d.classes[name]['methods'] if m['code']];w(len(ms))
for m in ms:
 off=m['code'];regs,ins,outs,tries,debug,n=struct.unpack_from('<HHHHII',d.d,off);w(m['idx']);w(regs);w(ins);w(n)
 for word in struct.unpack_from('<'+'H'*n,d.d,off+16):w(word)
 w(tries)
 if tries:
  tryp=off+16+2*n+(2 if n%2 else 0);base=tryp+8*tries
  for j in range(tries):
   start,count,h=struct.unpack_from('<IHH',d.d,tryp+8*j);w(start);w(start+count);p0=base+h;size,p0=sleb(d.d,p0);w(abs(size)+(1 if size<=0 else 0))
   for k in range(abs(size)):typ,p0=uleb(d.d,p0);target,p0=uleb(d.d,p0);s(d.types[typ]);w(target)
   if size<=0:target,p0=uleb(d.d,p0);s('Ljava/lang/Throwable;');w(target)
pathlib.Path(sys.argv[2]).write_bytes(out)
