package android.app;
public class Activity extends android.content.Context {
 protected void onCreate(android.os.Bundle b){} protected void onResume(){} protected void onPause(){} protected void onDestroy(){} public void onBackPressed(){} public void onWindowFocusChanged(boolean focused){}
 public void setContentView(android.view.View v){} public void setTitle(CharSequence t){} public void finish(){} public android.view.Window getWindow(){return null;} public boolean isFinishing(){return false;}
}
