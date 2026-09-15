#!/usr/bin/env python3
"""Run the source project's host-side build, instruction, migration and parser checks."""
from pathlib import Path
import sys,json,zipfile,struct,subprocess,hashlib,shutil
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'tools'))
from dexutil import Dex
from flowcheck import analyze
from fix_orphan_classdata import describe
from android_resources import decode_chunk,encode
from resources import Resources
from axml import parse

def run(cmd):
 p=subprocess.run([str(x)for x in cmd],check=True,cwd=R,capture_output=True,text=True);print(p.stdout,end='');return p.stdout.strip()
def main():
 apk=Path(sys.argv[1]).resolve();z=zipfile.ZipFile(apk);out=R/'build/tests';out.mkdir(parents=True,exist_ok=True);report={'environment':'JVM and Python host tests','apk_sha256':hashlib.sha256(apk.read_bytes()).hexdigest()}
 assert z.testzip()is None and len(z.namelist())==len(set(z.namelist()))
 source_files=[p.relative_to(R).as_posix() for p in R.rglob('*') if p.is_file() and p.relative_to(R).parts[0] not in {'build','dist','.git'} and '__pycache__' not in p.relative_to(R).parts]
 assert len(source_files)==len(set(p.casefold()for p in source_files))
 report['case_insensitive_source_paths']='PASS'
 ds={n:Dex(z.read(n))for n in sorted(z.namelist())if n.endswith('.dex')};classes={};flows=[]
 selected=set(json.loads((R/'config/flow_methods.json').read_text()))
 for n,d in ds.items():
  for name in d.classes:assert name not in classes;classes[name]=n
  assert describe(d.d)['ownership_check']=='PASS'
  report[n]=d.validate()
  for m in d.defs.values():
   if m['code']and(n!='classes.dex'or m['name']in selected):
    a,_=analyze(d,m);flows.append(a);assert a['status']=='PASS',a
 report['class_count']=len(classes);report['flow_methods']=len(flows)
 (out/'flow.json').write_text(json.dumps(flows,ensure_ascii=False,indent=2))
 report['linkage']=json.loads(run([sys.executable,R/'tests/check_linkage.py',apk]))
 resources=Resources(z.read('resources.arsc'));refs={e.get('text')for e in resources.entries if e.get('text','').startswith('res/')};assert refs.issubset(set(z.namelist()));report['resource_file_references']=len(refs)
 count=0
 for n in z.namelist():
  b=z.read(n)
  if n=='resources.arsc'or(n.endswith('.xml')and b[:2]==b'\x03\x00'):assert encode(decode_chunk(b))==b,n;count+=1
 report['resource_roundtrips']=count
 _,nodes=parse(z.read('AndroidManifest.xml'));manifest=nodes[0];assert manifest['attrs']['android:versionCode']=='267';assert manifest['attrs']['package']=='com.suda.yzune.wakeupschedule'
 splash=[e for e in resources.entries if e['id']==0x7f1301a7]
 for e in splash:
  maps={v['key']:v['data']for v in e['maps']};assert maps[16844333]==0x7f080300 and maps[16844335]==0x7f080301
 report['splash_style_variants']=len(splash)
 d=ds['classes.dex'];name='Lcom/suda/yzune/wakeupschedule/dao/OooO0O0;->OooO0o0(Lcom/suda/yzune/wakeupschedule/dao/o0Oo0oo;Lcom/suda/yzune/wakeupschedule/bean/TimeTableBean;Lkotlin/coroutines/jvm/internal/ContinuationImpl;)Ljava/lang/Object;'
 ins={i['pc']:i for i in d.insns(d.defs[d.methods.index(name)])};pcs=[(0x65,0x67),(0x6e,0x72),(0x7d,0x79),(0x88,0x84),(0x93,0x8f),(0x9e,0x9a),(0xa9,0xa5),(0xb4,0xb0),(0xbf,0xbb),(0xca,0xc6),(0xd7,0xd5),(0xe4,0xe2)]
 spec=json.loads((R/'config/shu.json').read_text())
 for row,(a,b)in zip(spec['periods'],pcs):assert(d.strings[ins[a]['ref']],d.strings[ins[b]['ref']])==(row['start'],row['end'])
 report['default_periods']=len(pcs)
 path=out/'classes3.dex';path.write_bytes(z.read('classes3.dex'))
 java=out/'java';java.mkdir(exist_ok=True)
 sources=[*sorted((R/'tests/host').rglob('*.java')),R/'tests/Course.java',R/'tests/DexHostVM.java',R/'tests/ParserCases.java',R/'tests/VerifyApk.java',R/'app/src/main/java/shu/wakeup/ShuImporter.java',R/'app/src/main/java/shu/wakeup/ShuTimes.java',R/'app/src/main/java/shu/wakeup/ShuMigration.java']
 run(['javac','-encoding','UTF-8','-d',java,*sources])
 fixture=R/'tests/fixtures/shu_grid.html'
 report['parser_java']=run(['java','-cp',java,'ParserCases',fixture,out/'parser-java.txt'])
 run([sys.executable,R/'tests/export_parser.py',path,out/'parser-model.bin'])
 report['parser_dex']=run(['java','-cp',java,'DexHostVM',out/'parser-model.bin',fixture,out/'parser-dex.txt'])
 assert(out/'parser-java.txt').read_bytes()==(out/'parser-dex.txt').read_bytes()
 report['migration_java']=run(['java','-cp',java,'MigrationCases'])
 run([sys.executable,R/'tests/export_parser.py',path,out/'migration-model.bin','Lshu/wakeup/ShuMigration;','Lshu/wakeup/ShuTimes;'])
 report['migration_dex']=run(['java','-cp',java,'MigrationDexCases',out/'migration-model.bin'])
 if 'META-INF/SHU.RSA'in z.namelist():
  report['signature_java']=run(['java','-cp',java,'VerifyApk',apk])
  from apk_signature import verify_v2
  report['signature_python']=verify_v2(apk)
  raw=bytearray(apk.read_bytes());item=z.getinfo('classes3.dex');a=item.header_offset;nl,el=struct.unpack_from('<HH',raw,a+26);raw[a+30+nl+el+100]^=1;bad=out/'mutated.apk';bad.write_bytes(raw)
  try:verify_v2(bad)
  except (AssertionError,ValueError):report['signature_mutation']='PASS'
  else:raise AssertionError('Mutation verification expectation')
  finally:bad.unlink()
 # A source edit that adds a NOP exercises method resizing and DEX pointer relocation.
 from core_source import build
 import tempfile
 with tempfile.TemporaryDirectory()as temp:
  folder=Path(temp)/'core';shutil.copytree(R/'core/dex2',folder);layout=json.loads((folder/'metadata/layout.json').read_text());file=folder/layout['classes'][0];obj=json.loads(file.read_text());method=next(m for m in obj['methods']if'instructions'in m);method['instructions'].insert(0,{'label':'Lsource_edit','op':'nop'});file.write_text(json.dumps(obj));edited=Dex(build(folder));edited.validate();assert describe(edited.d)['ownership_check']=='PASS'
 report['source_method_resize']='PASS';report['status']='PASS';(out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
