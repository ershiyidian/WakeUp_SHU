import java.util.*;import java.io.*;import java.lang.reflect.*;import java.nio.file.*;import java.nio.charset.StandardCharsets;
import com.suda.yzune.wakeupschedule.schedule_parser.bean.base.Course;
/** Host interpreter for the supplied extension DEX instructions.
 * Execution uses Java APIs and explicit Android test doubles.
 */
public final class DexHostVM {
 static final class M{int registers,inputs;int[] code;List<Handler>handlers=new ArrayList<>();}
 static final class Handler{int start,end,target;String type;}
 static final class NewObject{String type;Object value;NewObject(String t){type=t;}}
 final String[]strings,types,fields,methods;final Map<Integer,M>own=new HashMap<>();final Map<Integer,Object>statics=new HashMap<>();
 static String str(DataInputStream in)throws Exception{return new String(in.readNBytes(in.readInt()),StandardCharsets.UTF_8);}
 static String[] table(DataInputStream in)throws Exception{String[]s=new String[in.readInt()];for(int i=0;i<s.length;i++)s[i]=str(in);return s;}
 DexHostVM(Path model)throws Throwable{
  try(DataInputStream in=new DataInputStream(Files.newInputStream(model))){strings=table(in);types=table(in);fields=table(in);methods=table(in);int n=in.readInt();for(int j=0;j<n;j++){int id=in.readInt();M m=new M();m.registers=in.readInt();m.inputs=in.readInt();m.code=new int[in.readInt()];for(int i=0;i<m.code.length;i++)m.code[i]=in.readInt();int tries=in.readInt();for(int i=0;i<tries;i++){int start=in.readInt(),end=in.readInt(),num=in.readInt();for(int k=0;k<num;k++){Handler h=new Handler();h.start=start;h.end=end;h.type=str(in);h.target=in.readInt();m.handlers.add(h);}}own.put(id,m);}}
  for(Integer id:new TreeSet<>(own.keySet()))if(methods[id].endsWith("-><clinit>()V"))call(id,new Object[0]);
 }
 int index(String s){for(int i=0;i<methods.length;i++)if(methods[i].equals(s))return i;throw new IllegalArgumentException(s);}
 static Object obj(Object o){return o instanceof NewObject?((NewObject)o).value:o;}
 static int num(Object o){o=obj(o);return o==null?0:o instanceof Boolean?((Boolean)o?1:0):o instanceof Character?(Character)o:((Number)o).intValue();}
 static boolean zero(Object o){o=obj(o);return o==null||(o instanceof Number&&((Number)o).intValue()==0)||(o instanceof Boolean&&!((Boolean)o));}
 static boolean eq(Object a,Object b){a=obj(a);b=obj(b);if(zero(a)&&zero(b))return true;if(a instanceof Number&&b instanceof Number)return num(a)==num(b);return a==b;}
 static Class<?>cls(String t)throws Exception{return switch(t){case "V"->void.class;case "Z"->boolean.class;case "B"->byte.class;case "S"->short.class;case "C"->char.class;case "I"->int.class;case "J"->long.class;case "F"->float.class;case "D"->double.class;default->Class.forName(t.startsWith("[")?t.replace('/','.'):t.substring(1,t.length()-1).replace('/','.'));};}
 static List<String>params(String m){int i=m.indexOf('(')+1,end=m.indexOf(')');List<String>p=new ArrayList<>();while(i<end){int start=i;while(m.charAt(i)=='[')i++;if(m.charAt(i)=='L')i=m.indexOf(';',i)+1;else i++;p.add(m.substring(start,i));}return p;}
 static Object convert(Object o,Class<?>t){o=obj(o);if(!t.isPrimitive())return zero(o)?null:o;if(t==boolean.class)return !zero(o);if(t==char.class)return (char)num(o);if(t==float.class)return o instanceof Float?o:Float.intBitsToFloat(num(o));if(t==double.class)return ((Number)o).doubleValue();if(t==long.class)return ((Number)o).longValue();if(t==byte.class)return(byte)num(o);if(t==short.class)return(short)num(o);return num(o);}
 Object invoke(int id,Object[]args,boolean isStatic)throws Throwable{
  if(own.containsKey(id))return call(id,args);
  String full=methods[id];int arrow=full.indexOf("->");String owner=full.substring(0,arrow),name=full.substring(arrow+2,full.indexOf('('));
  if(owner.equals("[I")&&name.equals("clone"))return ((int[])obj(args[0])).clone();
  Class<?>c=cls(owner);List<String>ps=params(full);Class<?>[]pts=new Class<?>[ps.size()];Object[]av=new Object[ps.size()];for(int i=0;i<ps.size();i++){pts[i]=cls(ps.get(i));av[i]=convert(args[i+(isStatic?0:1)],pts[i]);}
  try{
   if(name.equals("<init>")){NewObject no=(NewObject)args[0];no.value=c.getConstructor(pts).newInstance(av);return null;}
   return c.getMethod(name,pts).invoke(isStatic?null:obj(args[0]),av);
  }catch(InvocationTargetException e){throw e.getCause();}
 }
 Object call(int id,Object[]args)throws Throwable{
  M m=own.get(id);if(m==null)throw new AssertionError("missing VM method "+methods[id]);Object[]r=new Object[m.registers];Arrays.fill(r,0);checkArgs(args.length==m.inputs,methods[id]);System.arraycopy(args,0,r,r.length-m.inputs,args.length);int[]c=m.code;int pc=0,steps=0;Object result=null,exception=null;
  while(pc<c.length){if(++steps>20000000)throw new AssertionError("step budget exceeded");int at=pc,u=c[pc],op=u&255,a=u>>>8,b=u>>>12,v=(u>>>8)&15;
   try{
    switch(op){
    case 0x01:case 0x07:r[v]=r[b];pc++;break;
    case 0x02:case 0x08:r[a]=r[c[pc+1]];pc+=2;break;
    case 0x0a:case 0x0c:r[a]=result;pc++;break;
    case 0x0d:r[a]=exception;pc++;break;
    case 0x0e:return null;
    case 0x0f:return num(r[a]);
    case 0x11:return zero(r[a]) ? null : obj(r[a]);
    case 0x12:r[v]=(b>=8?b-16:b);pc++;break;
    case 0x13:r[a]=(int)(short)c[pc+1];pc+=2;break;
    case 0x14:r[a]=c[pc+1]|(c[pc+2]<<16);pc+=3;break;
    case 0x1a:r[a]=strings[c[pc+1]];pc+=2;break;
    case 0x1f:if(!zero(r[a])&&!cls(types[c[pc+1]]).isInstance(obj(r[a])))throw new ClassCastException(types[c[pc+1]]);pc+=2;break;
    case 0x22:r[a]=new NewObject(types[c[pc+1]]);pc+=2;break;
    case 0x23:r[v]=Array.newInstance(cls(types[c[pc+1]].substring(1)),num(r[b]));pc+=2;break;
    case 0x27:throw(Throwable)obj(r[a]);
    case 0x2a:pc+=c[pc+1]|(c[pc+2]<<16);break;
    case 0x32:case 0x33:case 0x34:case 0x35:case 0x36:case 0x37:{boolean cond=switch(op){case 0x32->eq(r[v],r[b]);case 0x33->!eq(r[v],r[b]);case 0x34->num(r[v])<num(r[b]);case 0x35->num(r[v])>=num(r[b]);case 0x36->num(r[v])>num(r[b]);default->num(r[v])<=num(r[b]);};pc+=cond?(short)c[pc+1]:2;break;}
    case 0x38:case 0x39:case 0x3a:case 0x3b:{boolean cond=switch(op){case 0x38->zero(r[a]);case 0x39->!zero(r[a]);case 0x3a->num(r[a])<0;default->num(r[a])>=0;};pc+=cond?(short)c[pc+1]:2;break;}
    case 0x46:r[a]=Array.get(obj(r[c[pc+1]&255]),num(r[c[pc+1]>>>8]));pc+=2;break;
    case 0x4d:Array.set(obj(r[c[pc+1]&255]),num(r[c[pc+1]>>>8]),obj(r[a]));pc+=2;break;
    case 0x91:r[a]=num(r[c[pc+1]&255])-num(r[c[pc+1]>>>8]);pc+=2;break;
    case 0x44:r[a]=Array.getInt(obj(r[c[pc+1]&255]),num(r[c[pc+1]>>>8]));pc+=2;break;
    case 0x4b:Array.setInt(obj(r[c[pc+1]&255]),num(r[c[pc+1]>>>8]),num(r[a]));pc+=2;break;
    case 0x62:r[a]=statics.getOrDefault(c[pc+1],0);pc+=2;break;
    case 0x69:statics.put(c[pc+1],obj(r[a]));pc+=2;break;
    case 0x74:case 0x76:case 0x77:case 0x78:{Object[]av=Arrays.copyOfRange(r,c[pc+2],c[pc+2]+a);result=invoke(c[pc+1],av,op==0x77);pc+=3;break;}
    case 0x90:r[a]=num(r[c[pc+1]&255])+num(r[c[pc+1]>>>8]);pc+=2;break;
    case 0x94:r[a]=num(r[c[pc+1]&255])%num(r[c[pc+1]>>>8]);pc+=2;break;
    case 0xd8:r[a]=num(r[c[pc+1]&255])+(byte)(c[pc+1]>>>8);pc+=2;break;
    default:throw new AssertionError("unsupported op "+Integer.toHexString(op)+" at "+pc+" in "+methods[id]);
    }
   }catch(Throwable t){Handler found=null;for(Handler h:m.handlers)if(at>=h.start&&at<h.end&&cls(h.type).isInstance(t)){found=h;break;}if(found==null)throw t;exception=t;pc=found.target;}
  }
  throw new AssertionError("fell off method "+methods[id]);
 }
 static void checkArgs(boolean ok,String m){if(!ok)throw new AssertionError("argument/register count "+m);}
 @SuppressWarnings("unchecked") List<Course>parse(String s)throws Throwable{return(List<Course>)call(index("Lshu/wakeup/ShuImporter;->parseIfSupported(Ljava/lang/String;)Ljava/util/List;"),new Object[]{s});}
 public static void main(String[]args)throws Throwable{
  DexHostVM vm=new DexHostVM(Path.of(args[0]));String real=Files.readString(Path.of(args[1]),StandardCharsets.UTF_8);List<Course>courses=ParserCases.run(vm::parse,real);List<String>lines=new ArrayList<>();for(Course c:courses)lines.add(c.toString());Collections.sort(lines);Files.write(Path.of(args[2]),lines,StandardCharsets.UTF_8);System.out.println("exact_dex_instruction_execution=PASS (host interpreter with Java APIs)");
 }
}
