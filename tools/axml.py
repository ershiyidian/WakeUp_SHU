import struct,json
from xml.sax.saxutils import escape

def pool(d,off=0):
 typ,hs,size=struct.unpack_from('<HHI',d,off);assert typ==1
 n,ns,flags,start,styles=struct.unpack_from('<5I',d,off+8);utf8=flags&0x100
 def length(p,unit):
  if unit==1:
   x=d[p];p+=1
   if x&0x80:x=((x&0x7f)<<8)|d[p];p+=1
  else:
   x=struct.unpack_from('<H',d,p)[0];p+=2
   if x&0x8000:x=((x&0x7fff)<<16)|struct.unpack_from('<H',d,p)[0];p+=2
  return x,p
 out=[];positions=[]
 for i in range(n):
  p=off+start+struct.unpack_from('<I',d,off+hs+4*i)[0];original=p
  if utf8:
   chars,p=length(p,1);ln,p=length(p,1);s=bytes(d[p:p+ln]).decode('utf8','replace')
  else:
   ln,p=length(p,2);s=bytes(d[p:p+ln*2]).decode('utf16','replace')
  out.append(s);positions.append((original,p,ln))
 return out,positions,size

def parse(d):
 assert struct.unpack_from('<H',d,0)[0]==3
 p=8;strings=None;nodes=[];stack=[]
 while p<len(d):
  typ,hs,n=struct.unpack_from('<HHI',d,p);assert n>=8
  if typ==1:strings,positions,_=pool(d,p)
  elif typ==0x102:
   ns,name,astart,asz,acount,ididx,clidx,styidx=struct.unpack_from('<IIHHHHHH',d,p+16);attrs={};records=[]
   for i in range(acount):
    q=p+16+astart+i*asz;ans,an,raw,vs,res,dt,val=struct.unpack_from('<IIIHBBI',d,q)
    s=strings[val] if dt==3 else (('@%08x'%val) if dt==1 else ('true' if val else 'false') if dt==0x12 else str(val))
    key=('android:' if ans!=0xffffffff and strings[ans].endswith('/android') else '')+strings[an]
    attrs[key]=s;records.append({'name':key,'type':dt,'value':val,'offset':q,'raw':raw})
   node={'name':strings[name],'attrs':attrs,'start':p,'size':n,'depth':len(stack),'records':records};nodes.append(node);stack.append(node)
  elif typ==0x103:stack.pop()['end']=p+n
  p+=n
 assert p==len(d) and not stack
 return strings,nodes

def xml(d):
 _,nodes=parse(d);events=[]
 for x in nodes:
  attrs=' '.join(k+'="'+escape(v,{'"':'&quot;'})+'"' for k,v in x['attrs'].items())
  events.append((x['start'],'  '*x['depth']+'<'+x['name']+(' '+attrs if attrs else '')+'>'))
  events.append((x['end']-1,'  '*x['depth']+'</'+x['name']+'>'))
 return '\n'.join(s for _,s in sorted(events))
