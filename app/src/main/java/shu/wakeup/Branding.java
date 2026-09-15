// SPDX-License-Identifier: MIT
package shu.wakeup;
import android.app.Activity;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ImageView;
import android.widget.TextView;
/** Native brand screen and one-time SHU timetable migration. */
public final class Branding {
    private Branding() {
    }
    private static int dp(Activity a,int n) {
        return Math.round(n*a.getResources().getDisplayMetrics().density);
    }
    public static void show(Activity a) {
        ShuMigration.apply(a);
        boolean dark=(a.getResources().getConfiguration().uiMode&48)==32;
        FrameLayout root=new FrameLayout(a);
        root.setBackgroundColor(dark?0xff10171b:0xfff8f9fc);
        LinearLayout center=new LinearLayout(a);
        center.setOrientation(1);
        center.setGravity(17);
        ImageView mark=new ImageView(a);
        mark.setImageResource(0x7f080300);
        mark.setScaleType(ImageView.ScaleType.FIT_CENTER);
        mark.setContentDescription("WakeUp_SHU 上海大学");
        center.addView(mark,new LinearLayout.LayoutParams(dp(a,240),dp(a,240)));
        TextView title=new TextView(a);
        title.setText("WakeUp_SHU");
        title.setTextSize(20);
        title.setTextColor(dark?0xffeeeeee:0xff104a72);
        title.setGravity(17);
        center.addView(title);
        root.addView(center,new FrameLayout.LayoutParams(-2,-2,17));
        TextView footer=new TextView(a);
        footer.setText("仅供学习使用，请在下载后24小时内删除");
        footer.setTextSize(10);
        footer.setTextColor(dark?0xffc4cad0:0xff596572);
        footer.setGravity(17);
        footer.setPadding(dp(a,10),0,dp(a,10),0);
        FrameLayout.LayoutParams p=new FrameLayout.LayoutParams(-1,-2,81);
        p.bottomMargin=dp(a,32);
        root.addView(footer,p);
        a.setContentView(root);
    }
}
