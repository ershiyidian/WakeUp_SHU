package android.database;
public interface Cursor {boolean moveToNext();boolean moveToFirst();int getInt(int n);String getString(int n);void close();}
