package android.content;
import java.io.File; import java.util.*;
public class Context {
 public final Map<String,MemoryPreferences> prefs=new HashMap<>(); public File database;
 public Context(File database){this.database=database;}
 public SharedPreferences getSharedPreferences(String name,int mode){return prefs.computeIfAbsent(name,k->new MemoryPreferences());}
 public File getDatabasePath(String name){if(!name.equals("wakeup"))throw new AssertionError(name);return database;}
 public static class MemoryPreferences implements SharedPreferences, SharedPreferences.Editor {
  public final Map<String,Object> values=new HashMap<>();
  public boolean getBoolean(String k,boolean d){return (Boolean)values.getOrDefault(k,d);}
  public int getInt(String k,int d){return (Integer)values.getOrDefault(k,d);}
  public boolean contains(String k){return values.containsKey(k);} public Editor edit(){return this;}
  public Editor putBoolean(String k,boolean v){values.put(k,v);return this;}public Editor putInt(String k,int v){values.put(k,v);return this;}
  public void apply(){}public boolean commit(){return true;}
 }
}
