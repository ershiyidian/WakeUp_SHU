package android.view;
public class ViewGroup extends View implements ViewParent {public ViewGroup(android.content.Context c){super(c);}public static class LayoutParams {public int width,height;public LayoutParams(int w,int h){width=w;height=h;}}public void addView(View v){}public void addView(View v,LayoutParams p){}public void removeView(View v){}public void removeAllViews(){}}
