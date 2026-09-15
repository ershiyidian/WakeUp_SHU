import struct,sys,zipfile,json
from pathlib import Path
from axml import pool,parse,xml

def chunks(d,start,end):
 p=start
 while p<end:
  t,h,n=struct.unpack_from('<HHI',d,p)
  assert n>=h>0,(p,t,h,n)
  yield p,t,h,n
  p+=n
 assert p==end
class Resources:
 def __init__(self,data):
  self.d=data;self.entries=[];self.names={};self.values={};self.globalpool=None
  for p,t,h,n in chunks(data,struct.unpack_from('<H',data,2)[0],len(data)):
   if t==1:self.strings,_,_=pool(data,p);self.globalpool=p
   elif t==0x200:
    pid=struct.unpack_from('<I',data,p+8)[0];to=struct.unpack_from('<I',data,p+268)[0];ko=struct.unpack_from('<I',data,p+276)[0]
    ts,_,_=pool(data,p+to);ks,_,_=pool(data,p+ko)
    for q,tt,hh,nn in chunks(data,p+h,p+n):
     if tt!=0x201:continue
     tid,flags,zero,cnt,st=struct.unpack_from('<BBHII',data,q+8);cs=struct.unpack_from('<I',data,q+20)[0];config=bytes(data[q+20:q+20+cs])
     assert flags==0,(tid,flags)
     for j in range(cnt):
      off=struct.unpack_from('<I',data,q+hh+4*j)[0]
      if off==0xffffffff:continue
      r=q+st+off;sz,fl,kid=struct.unpack_from('<HHI',data,r);rid=(pid<<24)|(tid<<16)|j
      name=ts[tid-1]+'/'+ks[kid];self.names[rid]=name
      item={'id':rid,'name':name,'config':config.hex(),'off':r,'flags':fl,'size':sz,'value_off':r+sz}
      if fl&1:
       parent,count=struct.unpack_from('<II',data,r+8);item['parent']=parent;item['maps']=[]
       for x in range(count):
        v=r+sz+12*x;key=struct.unpack_from('<I',data,v)[0];size,res,vt,val=struct.unpack_from('<HBBI',data,v+4);item['maps'].append({'key':key,'type':vt,'data':val,'off':v+4})
      else:
       size,res,vt,val=struct.unpack_from('<HBBI',data,r+sz);item.update(type=vt,data=val)
       if vt==3:item['text']=self.strings[val];self.values.setdefault(rid,[]).append(item['text'])
      self.entries.append(item)
 def save(self,path):
  Path(path).write_text(json.dumps(self.entries,ensure_ascii=False,indent=1),errors='backslashreplace')
