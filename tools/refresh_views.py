#!/usr/bin/env python3
"""Regenerate readable XML views and a symbolic resource index from typed sources."""
from pathlib import Path
import sys,json,struct
from xml.sax.saxutils import escape
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'tools'))
from android_resources import encode
from resources import Resources

def xml_view(source,names):
 pool=next(c['strings']for c in source['chunks']if c['kind']=='strings');prefix={};out=[];depth=0;ns_attrs={};root=True
 def text(v,key=''):
  t=v['type'];n=v['data']
  if t==3:return pool[n]
  if t in (1,2):return ('@'if t==1 else'?')+(names[n]if n in names else'0x%08x'%n)
  if t==4:return format(struct.unpack('<f',struct.pack('<I',n))[0],'.8g')
  if t in (5,6):
   value=(n&0xffffff00);value=value-(1<<32)if value&0x80000000 else value;value*= [1/256,1/32768,1/8388608,1/2147483648][(n>>4)&3]
   return format(value*(100 if t==6 else 1),'.8g')+(['px','dp','sp','pt','in','mm'][n&15]if t==5 else['%','%p'][n&15])
  if t==0x12:return'true'if n else'false'
  if 0x1c<=t<=0x1f:return'#%08x'%n
  if t==0x10:
   n=n-(1<<32)if n&0x80000000 else n
   if key in ('layout_width','layout_height')and n in (-1,-2):return'match_parent'if n==-1 else'wrap_content'
   return str(n)
  return'0x%08x'%n
 for c in source['chunks']:
  k=c['kind']
  if k=='namespace-start':p=pool[c['prefix']];uri=pool[c['uri']];prefix[c['uri']]=p;ns_attrs['xmlns:'+p]=uri
  elif k=='element-start':
   attrs=dict(ns_attrs)if root else{};root=False
   for a in c['attributes']:
    name=pool[a['name']];full=(prefix.get(a['namespace'],'ns')+':'if a['namespace']!=0xffffffff else'')+name;attrs[full]=text(a['value'],name)
   a=''.join(' '+k+'="'+escape(v,{'"':'&quot;'})+'"'for k,v in attrs.items());out.append('  '*depth+'<'+pool[c['name']]+a+'>');depth+=1
  elif k=='element-end':depth-=1;out.append('  '*depth+'</'+pool[c['name']]+'>')
  elif k=='text':out.append('  '*depth+escape(pool[c['text']]))
 return '<?xml version="1.0" encoding="utf-8"?>\n'+'\n'.join(out)+'\n'

def main():
 table=json.loads((R/'app/src/main/resources/table.json').read_text());res=Resources(encode(table));config=json.loads((R/'config/package.json').read_text())
 for row in config['resource_views']:
  source=json.loads((R/row['source']).read_text());p=R/row['view'];p.parent.mkdir(parents=True,exist_ok=True);p.write_text(xml_view(source,res.names),encoding='utf8',errors='backslashreplace')
 entries=[]
 for e in res.entries:
  item={'id':'0x%08x'%e['id'],'name':e['name'],'configuration':e['config']}
  if 'text'in e:item['text']=e['text']
  entries.append(item)
 (R/'config/resource-index.json').write_text(json.dumps(entries,ensure_ascii=False,indent=1)+'\n',encoding='utf8')
 print('XML views:',len(config['resource_views']),'resource variants:',len(entries))
if __name__=='__main__':main()
