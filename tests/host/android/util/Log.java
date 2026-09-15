package android.util;public final class Log {public static int warnings;public static int w(String tag,String text,Throwable t){warnings++;return 0;}}
