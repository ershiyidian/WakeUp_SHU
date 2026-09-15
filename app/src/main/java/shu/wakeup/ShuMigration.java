// SPDX-License-Identifier: MIT
package shu.wakeup;
import android.content.Context;
import android.content.SharedPreferences;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import java.io.File;
import java.util.ArrayList;
/** Upgrade the original stock timetable once, preserving user-edited tables. */
public final class ShuMigration {
    private ShuMigration() {
    }
    public static void apply(Context context) {
        SharedPreferences state=context.getSharedPreferences("shu_release",0);
        if(state.getBoolean("times_r5",false)) return;
        File file=context.getDatabasePath("wakeup");
        if(!file.isFile()) {
            state.edit().putBoolean("times_r5",true).apply();
            return;
        }
        SQLiteDatabase db=null;
        try {
            db=SQLiteDatabase.openDatabase(file.getPath(),null,0);
            if(db.getVersion()!=11) return;
            ArrayList<Integer> migrated=new ArrayList<Integer>();
            ArrayList<Integer> tables=new ArrayList<Integer>();
            db.beginTransaction();
            try {
                Cursor ids=db.rawQuery("SELECT id FROM TimeTableBean",null);
                try {
                    while(ids.moveToNext()) {
                        int id=ids.getInt(0);
                        int count=0;
                        boolean stock=true;
                        Cursor rows=db.rawQuery("SELECT node,startTime,endTime FROM TimeDetailBean WHERE timeTable=? AND node<=12 ORDER BY node",new String[] {
                            String.valueOf(id)
                        });
                        try {
                            while(rows.moveToNext()) {
                                count++;
                                if(rows.getInt(0)!=count || !ShuTimes.stockRow(count,rows.getString(1),rows.getString(2))) stock=false;
                            }
                        }
                        finally {
                            rows.close();
                        }
                        if(stock && count==12) {
                            for(int n=0;n<12;n++) db.execSQL("UPDATE TimeDetailBean SET startTime=?,endTime=? WHERE timeTable=? AND node=?",new Object[] {
                                ShuTimes.START[n],ShuTimes.END[n],Integer.valueOf(id),Integer.valueOf(n+1)
                            });
                            migrated.add(Integer.valueOf(id));
                            Cursor links=db.rawQuery("SELECT id FROM TableBean WHERE timeTable=?",new String[] {
                                String.valueOf(id)
                            });
                            try {
                                while(links.moveToNext()) tables.add(Integer.valueOf(links.getInt(0)));
                            }
                            finally {
                                links.close();
                            }
                        }
                    }
                }
                finally {
                    ids.close();
                }
                db.setTransactionSuccessful();
            }
            finally {
                db.endTransaction();
            }
            for(Integer id:migrated) {
                SharedPreferences p=context.getSharedPreferences("time"+id+"_config",0);
                if(p.getInt("courseLen",50)==50) p.edit().putInt("courseLen",45).apply();
            }
            for(Integer id:tables) {
                SharedPreferences p=context.getSharedPreferences("table"+id+"_config",0);
                if(p.getInt("nodes",20)==20) p.edit().putInt("nodes",12).apply();
            }
            state.edit().putBoolean("times_r5",true).apply();
        }
        catch(RuntimeException error) {
            android.util.Log.w("WakeUp_SHU","作息升级将在下次启动时继续",error);
        }
        finally {
            if(db!=null) db.close();
        }
    }
}
