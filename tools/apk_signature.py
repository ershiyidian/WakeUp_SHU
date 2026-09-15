"""Offline APK v1/v2 signing and ZIP data alignment, following the AOSP v2 format.
Produces and verifies the APK signing envelope in the host build environment.
"""
from pathlib import Path
import zipfile,struct,zlib,hashlib,base64,datetime,os,json,secrets
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import rsa,padding,ec
from cryptography.hazmat.primitives.serialization import pkcs7,pkcs12


def lp(b):return struct.pack('<I',len(b))+b

def eocd(data):
 p=data.rfind(b'PK\x05\x06',max(0,len(data)-65557));assert p>=0
 assert p+22+struct.unpack_from('<H',data,p+20)[0]==len(data)
 assert struct.unpack_from('<HH',data,p+4)==(0,0)
 size,off=struct.unpack_from('<II',data,p+12);assert off+size==p
 return p,off

def apk_digest(data,start,central,end):
 tail=bytearray(data[end:]);struct.pack_into('<I',tail,16,start)
 digests=[]
 for part in [data[:start],data[central:end],tail]:
  for p in range(0,len(part),1<<20):
   chunk=part[p:p+(1<<20)];digests.append(hashlib.sha256(b'\xa5'+struct.pack('<I',len(chunk))+chunk).digest())
 return hashlib.sha256(b'\x5a'+struct.pack('<I',len(digests))+b''.join(digests)).digest()

def parse_lp(d,p=0):
 n=struct.unpack_from('<I',d,p)[0];assert p+4+n<=len(d);return d[p+4:p+4+n],p+4+n

def lp_sequence(d):
 p=0;out=[]
 while p<len(d):b,p=parse_lp(d,p);out.append(b)
 assert p==len(d);return out

def verify_v2(path):
 data=Path(path).read_bytes();end,central=eocd(data);assert data[central-16:central]==b'APK Sig Block 42'
 size=struct.unpack_from('<Q',data,central-24)[0];start=central-size-8;assert start>=0 and struct.unpack_from('<Q',data,start)[0]==size
 p=start+8;v2=None
 while p<central-24:
  n=struct.unpack_from('<Q',data,p)[0];assert n>=4 and p+8+n<=central-24
  kind=struct.unpack_from('<I',data,p+8)[0]
  if kind==0x7109871a:v2=data[p+12:p+8+n]
  p+=8+n
 assert p==central-24 and v2 is not None
 signers,q=parse_lp(v2);assert q==len(v2);certs=[]
 for signer in lp_sequence(signers):
  signed,p=parse_lp(signer);sigs,p=parse_lp(signer,p);public,p=parse_lp(signer,p);assert p==len(signer)
  digestseq,p=parse_lp(signed);certseq,p=parse_lp(signed,p);attrs,p=parse_lp(signed,p);assert p<=len(signed)  # Android ignores signed trailing extension bytes
  ds={};ss={}
  for rec in lp_sequence(digestseq):
   alg=struct.unpack_from('<I',rec)[0];dg,q=parse_lp(rec,4);assert q==len(rec);ds[alg]=dg
  for rec in lp_sequence(sigs):
   alg=struct.unpack_from('<I',rec)[0];sig,q=parse_lp(rec,4);assert q==len(rec);ss[alg]=sig
  assert list(ds)==list(ss)
  cert=x509.load_der_x509_certificate(lp_sequence(certseq)[0]);key=cert.public_key()
  assert key.public_bytes(serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo)==public
  if 0x0103 in ss:alg=0x0103;key.verify(ss[alg],signed,padding.PKCS1v15(),hashes.SHA256())
  elif 0x0101 in ss:alg=0x0101;key.verify(ss[alg],signed,padding.PSS(mgf=padding.MGF1(hashes.SHA256()),salt_length=32),hashes.SHA256())
  elif 0x0201 in ss:alg=0x0201;key.verify(ss[alg],signed,ec.ECDSA(hashes.SHA256()))
  else:raise ValueError('unsupported verifier algorithm')
  assert ds[alg]==apk_digest(data,start,central,end),'APK content digest mismatch'
  certs.append({'subject':cert.subject.rfc4514_string(),'sha256':cert.fingerprint(hashes.SHA256()).hex(),'algorithm':hex(alg)})
 assert certs
 return {'scheme_v2':True,'signers':certs,'signing_block_start':start,'central_directory':central}

def attr(name,value):
 raw=(name+': '+value).encode('utf8');lines=[]
 while len(raw)>70:lines.append(raw[:70]+b'\r\n');raw=b' '+raw[70:]
 return b''.join(lines)+raw+b'\r\n'
def b64sha(b):return base64.b64encode(hashlib.sha256(b).digest()).decode()
