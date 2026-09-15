package com.suda.yzune.wakeupschedule.schedule_parser.bean.base;
/** Host test double, matching the verified APK constructor signature and field assignment order. */
public class Course {
 public final String name,room,teacher,note,startTime,endTime;
 public final int day,startNode,endNode,startWeek,endWeek,type;
 public final float credit;
 public Course(String name,int day,String room,String teacher,int startNode,int endNode,int startWeek,int endWeek,int type,float credit,String note,String startTime,String endTime) {
  this.name=name;this.day=day;this.room=room;this.teacher=teacher;this.startNode=startNode;this.endNode=endNode;this.startWeek=startWeek;this.endWeek=endWeek;this.type=type;this.credit=credit;this.note=note;this.startTime=startTime;this.endTime=endTime;
 }
 public String toString(){return name+"\t"+day+"\t"+room+"\t"+teacher+"\t"+startNode+"\t"+endNode+"\t"+startWeek+"\t"+endWeek+"\t"+type+"\t"+credit+"\t"+note;}
}
