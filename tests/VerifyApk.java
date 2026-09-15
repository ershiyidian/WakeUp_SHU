import java.nio.*;import java.nio.file.*;import java.security.*;import java.security.cert.*;import java.util.*;import java.util.jar.*;import java.io.*;
/** Independent JCA/JarFile verifier for this build's v1 and RSA-SHA256 v2 signatures. */
public final class VerifyApk {
 static ByteBuffer bb(byte[]b){return ByteBuffer.wrap(b).order(ByteOrder.LITTLE_ENDIAN);}
 static byte[] take(ByteBuffer b){int n=b.getInt();if(n<0||n>b.remaining())throw new IllegalArgumentException("bad length");byte[]v=new byte[n];b.get(v);return v;}
 static void check(boolean ok,String message){if(!ok)throw new AssertionError(message);}
 static byte[] hash(byte[]b)throws Exception{return MessageDigest.getInstance("SHA-256").digest(b);}
 static byte[] little(int n){return bb(new byte[4]).putInt(n).array();}
 static String hex(byte[]b){return HexFormat.of().formatHex(b);}
 static Map<Integer,byte[]> records(byte[]b){ByteBuffer p=bb(b);Map<Integer,byte[]>m=new LinkedHashMap<>();while(p.hasRemaining()){ByteBuffer r=bb(take(p));int alg=r.getInt();byte[]v=take(r);check(!r.hasRemaining(),"trailing record bytes");m.put(alg,v);}return m;}
 static byte[] verifyV2(Path path)throws Exception {
  byte[]d=Files.readAllBytes(path);ByteBuffer b=bb(d);int end=-1;
  for(int i=d.length-22;i>=Math.max(0,d.length-65557);i--)if(b.getInt(i)==0x06054b50&&(b.getShort(i+20)&65535)+i+22==d.length){end=i;break;}
  check(end>=0,"EOCD missing");int cd=b.getInt(end+16);check(cd+b.getInt(end+12)==end,"ZIP central directory bounds");
  check(new String(Arrays.copyOfRange(d,cd-16,cd),java.nio.charset.StandardCharsets.US_ASCII).equals("APK Sig Block 42"),"signing block magic");
  long sz=b.getLong(cd-24);check(sz>=24&&sz<cd,"signing block size");int start=cd-(int)sz-8;check(b.getLong(start)==sz,"two signing block sizes");
  byte[]v2=null;for(int p=start+8;p<cd-24;){long n=b.getLong(p);check(n>=4&&n<cd-p,"pair bounds");if(b.getInt(p+8)==0x7109871a)v2=Arrays.copyOfRange(d,p+12,p+8+(int)n);p+=8+(int)n;}
  check(v2!=null,"v2 block absent");ByteBuffer vs=bb(v2);ByteBuffer signers=bb(take(vs));check(!vs.hasRemaining(),"v2 outer bytes");check(signers.hasRemaining(),"no signers");byte[]leaf=null;int signerCount=0;
  while(signers.hasRemaining()){
   ByteBuffer signer=bb(take(signers));byte[]sd=take(signer),sigdata=take(signer),pub=take(signer);check(!signer.hasRemaining(),"signer bytes");
   ByteBuffer sb=bb(sd);Map<Integer,byte[]>digests=records(take(sb)),sigs=records(sigdata);byte[]certs=take(sb);take(sb);
   check(digests.keySet().equals(sigs.keySet()),"algorithm lists");check(sigs.containsKey(0x0103),"RSA SHA256 scheme");
   leaf=take(bb(certs));X509Certificate cert=(X509Certificate)CertificateFactory.getInstance("X.509").generateCertificate(new ByteArrayInputStream(leaf));check(Arrays.equals(pub,cert.getPublicKey().getEncoded()),"public key match");
   Signature s=Signature.getInstance("SHA256withRSA");s.initVerify(cert.getPublicKey());s.update(sd);check(s.verify(sigs.get(0x0103)),"RSA signature");
   byte[]tail=Arrays.copyOfRange(d,end,d.length);bb(tail).putInt(16,start);byte[][]parts={Arrays.copyOfRange(d,0,start),Arrays.copyOfRange(d,cd,end),tail};
   ByteArrayOutputStream chunks=new ByteArrayOutputStream();int count=0;
   for(byte[]part:parts)for(int p=0;p<part.length;p+=1048576){int n=Math.min(1048576,part.length-p);MessageDigest h=MessageDigest.getInstance("SHA-256");h.update((byte)0xa5);h.update(little(n));h.update(part,p,n);chunks.write(h.digest());count++;}
   MessageDigest h=MessageDigest.getInstance("SHA-256");h.update((byte)0x5a);h.update(little(count));h.update(chunks.toByteArray());check(Arrays.equals(h.digest(),digests.get(0x0103)),"signed APK content digest");signerCount++;
  }
  check(signerCount==1,"expected single signer");return leaf;
 }
 public static void main(String[]args)throws Exception{
  Path path=Path.of(args[0]);byte[]cert=verifyV2(path);System.out.println("v2=PASS certificate_sha256="+hex(hash(cert)));
  if(args.length>1&&args[1].equals("v2only"))return;
  int count=0;
  try(JarFile jar=new JarFile(path.toFile(),true)){
   Enumeration<JarEntry>items=jar.entries();while(items.hasMoreElements()){
    JarEntry e=items.nextElement();if(e.isDirectory())continue;
    try(InputStream in=jar.getInputStream(e)){in.transferTo(OutputStream.nullOutputStream());}
    String n=e.getName().toUpperCase(Locale.ROOT);if(n.equals("META-INF/MANIFEST.MF")||n.equals("META-INF/SHU.SF")||n.equals("META-INF/SHU.RSA"))continue;
    java.security.cert.Certificate[]cs=e.getCertificates();check(cs!=null&&cs.length==1,"unsigned/multisigned entry "+e.getName());check(Arrays.equals(cert,cs[0].getEncoded()),"v1/v2 signer mismatch");count++;
   }
   byte[]sf=jar.getInputStream(jar.getJarEntry("META-INF/SHU.SF")).readAllBytes();check(new String(sf,java.nio.charset.StandardCharsets.UTF_8).contains("X-Android-APK-Signed: 2"),"anti-stripping attribute");
  }
  System.out.println("v1=PASS signed_entries="+count+" same_signer_as_v2=true");
 }
}
