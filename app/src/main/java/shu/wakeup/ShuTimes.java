// SPDX-License-Identifier: MIT
package shu.wakeup;
public final class ShuTimes {
    public static final String[] START= {
        "08:00","08:55","10:00","10:55","13:00","13:55","15:00","15:55","18:00","18:55","20:00","20:55"
    };
    public static final String[] END= {
        "08:45","09:40","10:45","11:40","13:45","14:40","15:45","16:40","18:45","19:40","20:45","21:40"
    };
    public static final String[] OLD_START= {
        "08:00","09:00","10:10","11:10","13:30","14:30","15:40","16:40","18:30","19:30","20:30","21:25"
    };
    public static final String[] OLD_END= {
        "08:50","09:50","11:00","12:00","14:20","15:20","16:30","17:30","19:20","20:20","21:20","21:30"
    };
    private ShuTimes() {
    }
    public static boolean stockRow(int node,String start,String end) {
        return node>=1 && node<=12 && OLD_START[node-1].equals(start) && OLD_END[node-1].equals(end);
    }
}
