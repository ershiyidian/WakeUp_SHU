// SPDX-License-Identifier: MIT
package com.suda.yzune.wakeupschedule;
import android.os.Bundle;
import shu.wakeup.ShuPortal;
/** Compatibility component name retained for existing navigation links. */
public final class DonateActivity extends com.suda.yzune.wakeupschedule.base_view.BaseBlurTitleActivity {
    public OooOo0o.o00O000 Oooo0OO;
    private ShuPortal portal;
    public int OooOo0() {
        return 0x7f0c001e;
    }
    public static void OooOo0O(DonateActivity a) {
    }
    public void onCreate(Bundle state) {
        super.onCreate(state);
        setTitle("上大教务");
        portal=new ShuPortal(this);
        portal.open();
    }
    public void onResume() {
        super.onResume();
        if(portal!=null)portal.resume();
    }
    public void onWindowFocusChanged(boolean focused) {
        super.onWindowFocusChanged(focused);
        if(portal!=null) {
            if(focused)portal.resume();
            else portal.pause();
        }
    }
    public void onDestroy() {
        if(portal!=null) {
            portal.close();
            portal=null;
        }
        super.onDestroy();
    }
    public void onBackPressed() {
        if(portal!=null && portal.back())return;
        super.onBackPressed();
    }
}
