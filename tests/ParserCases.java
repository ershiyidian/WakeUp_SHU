import java.util.*;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import com.suda.yzune.wakeupschedule.schedule_parser.bean.base.Course;
public final class ParserCases {
 @FunctionalInterface public interface Parser { List<Course> parse(String html) throws Throwable; }
 static int assertions=0;
 static void check(boolean p,String message){assertions++;if(!p)throw new AssertionError(message);}
 static String block(String name,String time){return "<div class='timetable_con'><span class='title'>"+name+"</span><p><span title='节/周'>"+time+"</span></p><p><span title='上课地点'>宝山校区 C101</span></p><p><span title='教师'>测试教师</span></p><p><span title='学分'>2.5</span></p></div>";}
 static String grid(String b){return "<table id='kbgrid_table_0'><tr><td id='3-5' rowspan='4'>"+b+"</td></tr></table>";}
 static Set<Integer> weeks(List<Course> courses){Set<Integer>s=new TreeSet<>();for(Course c:courses)for(int w=c.startWeek;w<=c.endWeek;w++)if(c.type==0 || c.type==1&&w%2==1 || c.type==2&&w%2==0)s.add(w);return s;}
 static Set<Integer> set(int...n){Set<Integer>s=new TreeSet<>();for(int x:n)s.add(x);return s;}
 static void fails(Parser p,String html) throws Throwable {try {p.parse(html);}catch(IllegalArgumentException ok){check(true,"reject malformed");return;}throw new AssertionError("invalid input accepted");}
 public static List<Course> run(Parser p,String real) throws Throwable {
  assertions=0;List<Course> original=p.parse(real);check(original.size()==18,"sample must produce 18 schedule records, got "+original.size());
  check(p.parse(null)==null,"null fallback");check(p.parse("<html>login page</html>")==null,"unrelated fallback");
  List<Course> c=p.parse(grid(block("甲课程(123456)","(3-4节)1-8周")));check(c.size()==1,"normal run");Course x=c.get(0);
  check(x.name.equals("甲课程")&&x.day==3&&x.startNode==3&&x.endNode==4&&x.startWeek==1&&x.endWeek==8&&x.type==0,"basic fields ignore td rowspan");check(x.credit==2.5f&&x.room.equals("宝山校区 C101")&&x.teacher.equals("测试教师"),"course metadata");
  c=p.parse(grid(block("甲课程","(1-2节)1-16周(单)")));check(weeks(c).equals(set(1,3,5,7,9,11,13,15)),"odd weeks");
  c=p.parse(grid(block("甲课程","(1-2节)1-16周(双)")));check(weeks(c).equals(set(2,4,6,8,10,12,14,16)),"even weeks");
  c=p.parse(grid(block("甲课程","(1-2节)1,5,9,13周")));check(c.size()==4&&weeks(c).equals(set(1,5,9,13)),"sparse weeks");
  c=p.parse(grid(block("甲课程","(1-2节)1-3,5,7-9周")));check(weeks(c).equals(set(1,2,3,5,7,8,9)),"mixed sparse intervals");
  c=p.parse(grid(block("甲课程","(1,3-4节)1-2周")));check(c.size()==2&&c.get(0).startNode==1&&c.get(0).endNode==1&&c.get(1).startNode==3&&c.get(1).endNode==4,"sparse periods");
  c=p.parse(grid(block("甲课程","(3-4节)1-8周")+block("乙课程","(3-4节)9-16周")));check(c.size()==2&&c.get(0).endWeek==8&&c.get(1).startWeek==9,"split semesters in one cell");
  c=p.parse(grid(block("甲课程","(5-8节)9-16周")+block("乙课程","(7-8节)1-8周")));check(c.size()==2&&c.get(0).startNode==5&&c.get(1).startNode==7,"mixed rowspans");
  c=p.parse(grid(block("<font color='red'>待筛选课程</font>","(1-2节)1-8周")+block("已选课程","(1-2节)9-16周")));check(c.size()==1&&c.get(0).name.equals("已选课程"),"pending courses excluded");
  String b=block("甲课程","(1-2节)1-8周");c=p.parse(grid(b+b));check(c.size()==1,"duplicate block de-duplication");
  c=p.parse(grid(block("A&amp;B&#x20;课程","（1—2节）1—3周")));check(c.get(0).name.equals("A&B 课程")&&weeks(c).equals(set(1,2,3)),"entities and Unicode punctuation");
  c=p.parse(grid(block("甲课程","(1-2节)2—16双周")));check(weeks(c).equals(set(2,4,6,8,10,12,14,16)),"Chinese parity spelling");
  c=p.parse(grid(block("甲课程","(1-2节)1、5、9、13周")));check(weeks(c).equals(set(1,5,9,13)),"Chinese separators");
  fails(p,grid(block("甲课程","没有节次周次")));fails(p,grid(block("甲课程","(0-2节)1-8周")));fails(p,grid(block("甲课程","(1-2节)0-8周")));fails(p,grid(block("甲课程","(1-2节)9-2周")));fails(p,grid(block("甲课程","(1-2节)1-99周")));
  check(p.parse("<html>kbgrid_table timetable_con missing table</html>")==null,"truncated unrelated markup fallback");
  // Avoid silently interpreting the alternate list view as another copy of the timetable.
  c=p.parse(real+"<table id='other_list'><tr><td id='1-1'>"+block("列表重复","(1-2节)1-16周")+"</td></tr></table>");check(c.size()==18,"unrelated list view excluded");
  System.out.println("assertions="+assertions+" sample_records="+original.size());return original;
 }
 public static void main(String[]args) throws Throwable {
  String input=Files.readString(Path.of(args[0]),StandardCharsets.UTF_8);
  List<Course> courses=run(shu.wakeup.ShuImporter::parseIfSupported,input);
  List<String> out=new ArrayList<>();for(Course c:courses)out.add(c.toString());Collections.sort(out);Files.write(Path.of(args[1]),out,StandardCharsets.UTF_8);
 }
}
