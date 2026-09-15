package android.database.sqlite;
import android.database.Cursor;import java.util.*;
public class SQLiteDatabase {
 public interface CursorFactory {} public static SQLiteDatabase instance; public int version=11,opens,closes,transactions,commits,updates,failAt=-1;public boolean successful;
 public final Map<Integer,List<Object[]>> schedules=new LinkedHashMap<>(); public final Map<Integer,List<Integer>> links=new LinkedHashMap<>();
 private Map<Integer,List<Object[]>> snapshot;public int activeCursors;
 public static SQLiteDatabase openDatabase(String p,CursorFactory f,int flags){instance.opens++;return instance;}
 public int getVersion(){return version;}
 public void beginTransaction(){transactions++;successful=false;snapshot=new LinkedHashMap<>();schedules.forEach((id,rows)->{List<Object[]>r=new ArrayList<>();for(Object[]a:rows)r.add(a.clone());snapshot.put(id,r);});}
 public void setTransactionSuccessful(){successful=true;commits++;}
 public void endTransaction(){if(!successful){schedules.clear();schedules.putAll(snapshot);}}
 public Cursor rawQuery(String sql,String[]args){
  List<Object[]>rows=new ArrayList<>();
  if(sql.equals("SELECT id FROM TimeTableBean")){for(Integer id:schedules.keySet())rows.add(new Object[]{id});}
  else if(sql.equals("SELECT node,startTime,endTime FROM TimeDetailBean WHERE timeTable=? AND node<=12 ORDER BY node")){for(Object[]row:schedules.get(Integer.valueOf(args[0])))if((Integer)row[0]<=12)rows.add(row.clone());rows.sort(Comparator.comparingInt(a->(Integer)a[0]));}
  else if(sql.equals("SELECT id FROM TableBean WHERE timeTable=?")){for(Integer id:links.getOrDefault(Integer.valueOf(args[0]),Collections.emptyList()))rows.add(new Object[]{id});}
  else throw new AssertionError(sql);
  activeCursors++;
  return new Cursor(){int index=-1;boolean closed;public boolean moveToNext(){return ++index<rows.size();}public boolean moveToFirst(){index=0;return !rows.isEmpty();}public int getInt(int n){return(Integer)rows.get(index)[n];}public String getString(int n){return(String)rows.get(index)[n];}public void close(){if(closed)throw new AssertionError("cursor close count");closed=true;activeCursors--;}};
 }
 public void execSQL(String sql,Object[]args){if(!sql.equals("UPDATE TimeDetailBean SET startTime=?,endTime=? WHERE timeTable=? AND node=?"))throw new AssertionError(sql);if(updates==failAt)throw new IllegalStateException("injected update fault");updates++;for(Object[]row:schedules.get((Integer)args[2]))if(row[0].equals(args[3])){row[1]=args[0];row[2]=args[1];}}
 public void close(){closes++;if(activeCursors!=0)throw new AssertionError("cursor lifetime");}
}
