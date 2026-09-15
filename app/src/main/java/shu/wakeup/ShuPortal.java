// SPDX-License-Identifier: MIT
package shu.wakeup;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.DialogInterface;
import android.content.Intent;
import android.net.Uri;
import android.view.View;
import android.view.ViewGroup;
import android.widget.LinearLayout;
import android.widget.HorizontalScrollView;
import android.widget.Button;
import android.widget.TextView;
import android.widget.Toast;
import android.webkit.*;
/** On-demand academic browser sharing the app's WebView cookie store. */
public final class ShuPortal implements View.OnClickListener {
    public static final String HOME="https://jwxt.shu.edu.cn/";
    public static final String TABLE="https://jwxt.shu.edu.cn/jwglxt/kbcx/xskbcx_cxXskbcxIndex.html?gnmkdm=N2151&layout=default";
    public static final String SELECT="https://jwxk.shu.edu.cn/";
    private final Activity activity;
    private WebView web;
    private TextView location;
    private Button home,table,select,importButton,settings,session,clock;
    public ShuPortal(Activity activity) {
        this.activity=activity;
    }
    private int dp(int n) {
        return Math.round(n*activity.getResources().getDisplayMetrics().density);
    }
    private Button button(String text,LinearLayout row) {
        Button b=new Button(activity);
        b.setText(text);
        b.setTextSize(13);
        b.setAllCaps(false);
        b.setMinWidth(dp(72));
        b.setOnClickListener(this);
        row.addView(b,new LinearLayout.LayoutParams(-2,dp(48)));
        return b;
    }
    public void open() {
        boolean dark=(activity.getResources().getConfiguration().uiMode&48)==32;
        LinearLayout root=new LinearLayout(activity);
        root.setOrientation(1);
        root.setFitsSystemWindows(true);
        root.setBackgroundColor(dark?0xff10171b:0xfff8f9fc);
        LinearLayout row=new LinearLayout(activity);
        row.setOrientation(0);
        HorizontalScrollView scroller=new HorizontalScrollView(activity);
        scroller.setHorizontalScrollBarEnabled(false);
        scroller.addView(row);
        root.addView(scroller,new LinearLayout.LayoutParams(-1,dp(52)));
        home=button("教务首页",row);
        table=button("个人课表",row);
        select=button("选课系统",row);
        importButton=button("导入课表",row);
        settings=button("功能设置",row);
        session=button("登录管理",row);
        clock=button("时钟",row);
        location=new TextView(activity);
        location.setTextSize(11);
        location.setTextColor(dark?0xffc4cad0:0xff596572);
        location.setPadding(dp(12),dp(4),dp(12),dp(6));
        location.setSingleLine(true);
        root.addView(location,new LinearLayout.LayoutParams(-1,-2));
        web=new WebView(activity);
        WebSettings s=web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setAllowFileAccess(false);
        s.setAllowContentAccess(false);
        s.setBuiltInZoomControls(true);
        s.setDisplayZoomControls(false);
        s.setUseWideViewPort(true);
        s.setLoadWithOverviewMode(true);
        CookieManager cookies=CookieManager.getInstance();
        cookies.setAcceptCookie(true);
        cookies.setAcceptThirdPartyCookies(web,true);
        web.setWebViewClient(new WebViewClient() {
            public void onPageFinished(WebView v,String url) {
                location.setText(url);
                CookieManager.getInstance().flush();
            }
            public boolean shouldOverrideUrlLoading(WebView v,String url) {
                String scheme=Uri.parse(url).getScheme();
                return !("https".equals(scheme)||"http".equals(scheme));
            }
        });
        root.addView(web,new LinearLayout.LayoutParams(-1,0,1));
        activity.setContentView(root);
        web.loadUrl(HOME);
    }
    public void onClick(View view) {
        if(view==home)web.loadUrl(HOME);
        else if(view==table) {
            String url=web.getUrl();
            String host=url==null?"":Uri.parse(url).getHost();
            if(!"jwxt.shu.edu.cn".equals(host)) {
                notice("请先在教务首页完成统一身份认证");
                web.loadUrl(HOME);
                return;
            }
            web.evaluateJavascript("Boolean(document.querySelector('input[type=password]'))",new ValueCallback<String>() {
                public void onReceiveValue(String value) {
                    if(web==null)return;
                    if("false".equals(value))web.loadUrl(TABLE);
                    else notice("请先完成统一身份认证，再打开个人课表");
                }
            });
        }
        else if(view==select)web.loadUrl(SELECT);
        else if(view==importButton) {
            CookieManager.getInstance().flush();
            Intent i=new Intent();
            i.setClassName(activity,"com.suda.yzune.wakeupschedule.schedule_import.LoginWebActivity");
            i.putExtra("school_name","上海大学（新教务·推荐）");
            i.putExtra("import_type","zf");
            i.putExtra("url",HOME);
            i.putExtra("edu_type",0);
            i.putExtra("tableId",activity.getSharedPreferences("config",0).getInt("show_table_id",1));
            activity.startActivity(i);
        }
        else if(view==settings) {
            Intent i=new Intent();
            i.setClassName(activity,"com.suda.yzune.wakeupschedule.settings.AdvancedSettingsActivity");
            activity.startActivity(i);
        }
        else if(view==clock) {
            Intent i=new Intent();
            i.setClassName(activity,"com.suda.yzune.wakeupschedule.clock.ClockActivity");
            activity.startActivity(i);
        }
        else if(view==session) {
            new AlertDialog.Builder(activity).setTitle("登录状态").setMessage("教务与选课页面共享当前应用的浏览器会话。有效期由学校设置。清除后可重新登录或切换账号。").setNegativeButton("保留登录",null).setPositiveButton("清除登录状态",new DialogInterface.OnClickListener() {
                public void onClick(DialogInterface dialog,int which) {
                    WebStorage.getInstance().deleteAllData();
                    CookieManager.getInstance().removeAllCookies(new ValueCallback<Boolean>() {
                        public void onReceiveValue(Boolean done) {
                            CookieManager.getInstance().flush();
                            if(web!=null)web.loadUrl(HOME);
                        }
                    });
                }
            }).show();
        }
    }
    private void notice(String text) {
        Toast.makeText(activity,text,1).show();
    }
    public boolean back() {
        if(web!=null && web.canGoBack()) {
            web.goBack();
            return true;
        }
        return false;
    }
    public void pause() {
        if(web!=null)web.onPause();
        CookieManager.getInstance().flush();
    }
    public void resume() {
        if(web!=null)web.onResume();
    }
    public void close() {
        if(web==null)return;
        WebView closing=web;
        web=null;
        closing.stopLoading();
        closing.setWebViewClient(new WebViewClient());
        if(closing.getParent() instanceof ViewGroup)((ViewGroup)closing.getParent()).removeView(closing);
        closing.removeAllViews();
        closing.destroy();
        location=null;
    }
}
