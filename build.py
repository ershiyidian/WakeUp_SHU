#!/usr/bin/env python3
"""Build WakeUp_SHU from its Java, DEX assembly, and typed resource sources."""
from pathlib import Path
import argparse,subprocess,sys,json,zipfile,struct,shutil,os,base64,gzip,hashlib
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools'))
from core_source import build as assemble_core
from android_resources import encode as compile_resource
from jvm2dex import read_class,build as compile_dex
from dexutil import Dex

def run(cmd):
 subprocess.run([str(v)for v in cmd],check=True,cwd=ROOT)

def catalog_bytes(raw,dex):
 from cryptography.hazmat.primitives.ciphers import Cipher,algorithms,modes
 from cryptography.hazmat.primitives.padding import PKCS7
 d=Dex(dex);m=d.defs[d.methods.index('Lcom/suda/yzune/wakeupschedule/utils/OooO0o;->OooO0o0(Ljava/lang/String;)Ljava/lang/String;')]
 v=next(x['units']for x in d.insns(m)if x['name']=='array-data-payload');key=struct.pack('<'+'H'*(len(v)-4),*v[4:])[:16]
 b=base64.b64encode(gzip.compress(raw,mtime=0));p=PKCS7(128).padder();b=p.update(b)+p.finalize();e=Cipher(algorithms.AES(key),modes.CBC(key)).encryptor()
 return base64.b64encode(e.update(b)+e.finalize()).decode()[::-1].encode()

def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--keystore',type=Path,help='PKCS#12 signing identity')
 ap.add_argument('--password-file',type=Path,help='Local UTF-8 password file')
 ap.add_argument('--password-env',default='WAKEUP_KEYSTORE_PASSWORD')
 ap.add_argument('--output',type=Path)
 ap.add_argument('--test',action='store_true',help='Run host regression tests after building')
 args=ap.parse_args();work=ROOT/'build';stage=work/'apk';stage.mkdir(parents=True,exist_ok=True)
 print('1/4 Assemble inherited code')
 for number in (1,2):
  name='classes.dex'if number==1 else'classes2.dex';b=assemble_core(ROOT/f'core/dex{number}');(stage/name).write_bytes(b);print(name,Dex(b).validate())
 print('2/4 Compile Java extension')
 stubs=work/'api';classes=work/'java'
 for p in(stubs,classes):
  if p.exists():shutil.rmtree(p)
  p.mkdir(parents=True)
 stubfiles=sorted((ROOT/'tools/api-stubs').rglob('*.java'));sources=sorted((ROOT/'app/src/main/java').rglob('*.java'))
 run(['javac','--release','8','-g:source','-encoding','UTF-8','-d',stubs,*stubfiles])
 run(['javac','--release','8','-g:source','-encoding','UTF-8','-cp',stubs,'-d',classes,*sources])
 b,report=compile_dex([read_class(p)for p in sorted(classes.rglob('*.class'))]);(stage/'classes3.dex').write_bytes(b)
 print('classes3.dex',Dex(b).validate())
 print('3/4 Compile resources and assemble package entries')
 config=json.loads((ROOT/'config/package.json').read_text());catalog=json.loads((ROOT/'config/schools.json').read_text());raw=json.dumps(catalog,ensure_ascii=False,separators=(',',':')).encode();school=catalog_bytes(raw,(stage/'classes.dex').read_bytes());entries=[]
 for item in config['entries']:
  n=item['apk_path'];k=item['kind'];src=ROOT/item['source']
  if k=='dex':data=(stage/n).read_bytes()
  elif k=='typed-resource':data=compile_resource(json.loads(src.read_text()))
  elif n=='assets/school_info_android.txt':data=school
  else:data=src.read_bytes()
  path=stage/n;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
  entries.append((n,data,item['compression']))
 output=args.output or ROOT/'dist'/('WakeUp_6.0.23_SHU_r5.apk'if args.keystore else'WakeUp_SHU-unsigned.apk');output=output.resolve();output.parent.mkdir(parents=True,exist_ok=True)
 print('4/4 Package',output.name)
 if args.keystore:
  from cryptography.hazmat.primitives.serialization import pkcs12
  from sign_release import pack
  password=args.password_file.read_text().strip()if args.password_file else os.environ[args.password_env]
  key,cert,_=pkcs12.load_key_and_certificates(args.keystore.read_bytes(),password.encode());result=pack(entries,output,key,cert)
 else:
  with zipfile.ZipFile(output,'w',allowZip64=False,compresslevel=6)as z:
   for name,data,mode in entries:
    info=zipfile.ZipInfo(name,(2026,9,15,0,0,0));info.compress_type=mode;info.external_attr=0o100644<<16
    if mode==0:
     align=16384 if name.endswith('.dex')else 4;base=z.fp.tell()+30+len(name.encode())
     if base%align:pad=(-(base+4))%align;info.extra=struct.pack('<HH',0xcafe,pad)+bytes(pad)
    z.writestr(info,data)
  result={'signing':'unsigned'}
 result.update(bytes=output.stat().st_size,sha256=hashlib.sha256(output.read_bytes()).hexdigest(),output=str(output));(work/'build-report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False,indent=2))
 if args.test:run([sys.executable,ROOT/'tests/run.py',output])
if __name__=='__main__':main()
