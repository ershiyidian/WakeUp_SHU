"""Aligned APK packaging and v1/v2 signing with an existing PKCS#12 identity."""
from pathlib import Path
import sys,zipfile,struct,json,hashlib
from apk_signature import attr,b64sha,lp,apk_digest,eocd,verify_v2
from cryptography.hazmat.primitives import serialization,hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import pkcs7,pkcs12

def pack(entries,output,key,cert):
 sections=[];manifest=attr('Manifest-Version','1.0')+attr('Created-By','WakeUp_SHU reproducible build')+b'\r\n'
 for n,data,mode in entries:
  sec=attr('Name',n)+attr('SHA-256-Digest',b64sha(data))+b'\r\n';sections.append((n,sec));manifest+=sec
 sf=attr('Signature-Version','1.0')+attr('Created-By','WakeUp_SHU reproducible build')+attr('X-Android-APK-Signed','2')+attr('SHA-256-Digest-Manifest',b64sha(manifest))+b'\r\n'
 for n,sec in sections:sf+=attr('Name',n)+attr('SHA-256-Digest',b64sha(sec))+b'\r\n'
 cms=pkcs7.PKCS7SignatureBuilder().set_data(sf).add_signer(cert,key,hashes.SHA256()).sign(serialization.Encoding.DER,[pkcs7.PKCS7Options.DetachedSignature,pkcs7.PKCS7Options.Binary,pkcs7.PKCS7Options.NoAttributes])
 entries=[('META-INF/MANIFEST.MF',manifest,8),('META-INF/SHU.SF',sf,8),('META-INF/SHU.RSA',cms,8)]+entries
 output=Path(output);stage=output.with_suffix('.aligned.apk')
 with zipfile.ZipFile(stage,'w',allowZip64=False,compresslevel=6) as z:
  for n,b,mode in entries:
   i=zipfile.ZipInfo(n,(2026,9,15,0,0,0));i.compress_type=mode;i.external_attr=0o100644<<16
   if mode==0:
    align=16384 if n.endswith('.dex') else 4;base=z.fp.tell()+30+len(n.encode())
    if base%align:
     pad=(-(base+4))%align;i.extra=struct.pack('<HH',0xcafe,pad)+bytes(pad)
   z.writestr(i,b)
 data=stage.read_bytes();end,central=eocd(data);digest=apk_digest(data,central,central,end);der=cert.public_bytes(serialization.Encoding.DER);public=key.public_key().public_bytes(serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo);alg=struct.pack('<I',0x0103)
 signed=lp(lp(alg+lp(digest)))+lp(lp(der))+lp(b'');sig=key.sign(signed,padding.PKCS1v15(),hashes.SHA256());signer=lp(signed)+lp(lp(alg+lp(sig)))+lp(public);value=lp(lp(signer));pair=struct.pack('<QI',4+len(value),0x7109871a)+value;size=len(pair)+24;block=struct.pack('<Q',size)+pair+struct.pack('<Q',size)+b'APK Sig Block 42';tail=bytearray(data[end:]);struct.pack_into('<I',tail,16,central+len(block));output.write_bytes(data[:central]+block+data[central:end]+tail);stage.unlink();return verify_v2(output)
