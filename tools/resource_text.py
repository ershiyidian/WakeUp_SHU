#!/usr/bin/env python3
"""Read or update a named Android string resource in all its configurations."""
from pathlib import Path
import argparse,json
R=Path(__file__).resolve().parents[1]
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('name');ap.add_argument('text',nargs='?');args=ap.parse_args();path=R/'app/src/main/resources/table.json';root=json.loads(path.read_text());strings=next(x['strings']for x in root['chunks']if x['kind']=='strings');matches=[]
 for package in root['chunks']:
  if package['kind']!='package':continue
  pools=[c['strings']for c in package['chunks']if c['kind']=='strings'];types,keys=pools[:2]
  for c in package['chunks']:
   if c['kind']!='type'or types[c['id']-1]!='string':continue
   for e in c['entries']:
    if keys[e['key']]==args.name:matches.append(e)
 if not matches:raise SystemExit('Choose a string name from config/resource-index.json')
 if args.text is None:
  for e in matches:print(strings[e['value']['data']])
 else:
  if args.text not in strings:strings.append(args.text)
  index=strings.index(args.text)
  for e in matches:e['value']['type']=3;e['value']['data']=index
  path.write_text(json.dumps(root,ensure_ascii=False,indent=1)+'\n',encoding='utf8');print('Updated resource configurations:',len(matches))
if __name__=='__main__':main()
