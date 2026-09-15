from pathlib import Path
import sys,zipfile,json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from dexutil import Dex
apk=Path(sys.argv[1]);z=zipfile.ZipFile(apk)
ds=[Dex(z.read(n)) for n in sorted(z.namelist()) if n.endswith('.dex')]
classes={c:(d,x) for d in ds for c,x in d.classes.items()}
def resolve(owner,sig,kind):
 seen=set()
 while owner in classes and owner not in seen:
  seen.add(owner);d,c=classes[owner]
  if kind=='method':
   for m in c['methods']:
    if m['name'].split('->',1)[1]==sig:return owner,m['flags']
  else:
   for idx,flags in c['fields']:
    if d.fields[idx].split('->',1)[1]==sig:return owner,flags
  owner=c['super']
 return None if owner is None else ('external',0)
errors=[];checks=0
for c in ds[-1].classes.values():
 for m in c['methods']:
  sig=m['name'].split('->',1)[1]
  if not sig.startswith('<') and not m['flags']&0xa:
   r=resolve(c['super'],sig,'method');checks+=1
   if r and r[0]!='external' and r[1]&0x10:errors.append(('final override',m['name'],r))
  for i in ds[-1].insns(m):
   if i['refkind'] not in ('method','field'):continue
   arr=ds[-1].methods if i['refkind']=='method' else ds[-1].fields
   name=arr[i['ref']];owner,sig=name.split('->',1)
   if owner not in classes:continue
   checks+=1;r=resolve(owner,sig,i['refkind'])
   if r is None:errors.append(('member missing',m['name'],i['pc'],name))
   elif r[0]!='external':
    is_static=i['name'].startswith(('invoke-static','sget','sput'))
    if is_static!=bool(r[1]&8):errors.append(('static mismatch',name,i['name'],r))
    if r[1]&2 and r[0]!=c['name']:errors.append(('private access',m['name'],name,r))
report={'checks':checks,'errors':errors,'status':'PASS' if not errors else 'FAIL'}
print(json.dumps(report,ensure_ascii=False,indent=2));assert not errors
