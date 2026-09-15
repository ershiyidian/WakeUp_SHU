// SPDX-License-Identifier: MIT
package shu.wakeup;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import com.suda.yzune.wakeupschedule.schedule_parser.bean.base.Course;
/** Local-only adapter for the grid exported by Shanghai University's current JWGLXT.
* Reads course fields from the timetable grid; authentication stays in the school WebView.
* Returns null for other HTML formats, preserving the original WakeUp parser routing.
*/
public final class ShuImporter {
    private static final Pattern TABLE = Pattern.compile("<table\\b[^>]*\\bid\\s*=\\s*[\"']kbgrid_table(?:_\\d+)?[\"'][^>]*>(.*?)</table\\s*>", Pattern.CASE_INSENSITIVE | Pattern.DOTALL);
    private static final Pattern CELL = Pattern.compile("<td\\b[^>]*\\bid\\s*=\\s*[\"']([1-7])-(\\d+)[\"'][^>]*>(.*?)</td\\s*>", Pattern.CASE_INSENSITIVE | Pattern.DOTALL);
    private static final Pattern BLOCK = Pattern.compile("<div\\b[^>]*\\bclass\\s*=\\s*[\"'][^\"']*\\btimetable_con\\b[^\"']*[\"'][^>]*>(.*?)</div\\s*>", Pattern.CASE_INSENSITIVE | Pattern.DOTALL);
    private static final Pattern TITLE = Pattern.compile("<span\\b[^>]*\\bclass\\s*=\\s*[\"'][^\"']*\\btitle\\b[^\"']*[\"'][^>]*>(.*?)</span\\s*>", Pattern.CASE_INSENSITIVE | Pattern.DOTALL);
    private static final Pattern PARA = Pattern.compile("<p\\b[^>]*>(.*?)</p\\s*>", Pattern.CASE_INSENSITIVE | Pattern.DOTALL);
    private static final Pattern TIP = Pattern.compile("\\btitle\\s*=\\s*[\"']([^\"']*)[\"']", Pattern.CASE_INSENSITIVE);
    private static final Pattern PERIOD = Pattern.compile("[（(]?\\s*([0-9,，、\\-~—至\\s]+)\\s*节\\s*[）)]?\\s*(.+)");
    private static final Pattern RANGE = Pattern.compile("(\\d+)(?:\\s*[-~—至]\\s*(\\d+))?");
    private static final Pattern WEEK = Pattern.compile("(\\d+)(?:\\s*[-~—至]\\s*(\\d+))?\\s*周?\\s*(?:[（(]([单双])[周]?[）)])?");
    private static final Pattern RED = Pattern.compile("(?:\\bcolor\\s*=\\s*[\"']?(?:red|#ff0000|#f00)(?:[\"'\\s>])|\\bcolor\\s*:\\s*(?:red|#ff0000|#f00)(?:[;\"'\\s]))", Pattern.CASE_INSENSITIVE);
    private static final Pattern TAG = Pattern.compile("<[^>]*>");
    private static final Pattern ENTITY = Pattern.compile("&#(?:[xX]([0-9a-fA-F]+)|(\\d+));?");
    private static final Pattern CODE = Pattern.compile("[（(]([0-9A-Za-z]{6,})[）)]$");
    private static final int MAX_WEEK = 60;
    private static final int MAX_NODE = 32;
    private ShuImporter() {
    }
    public static List<Course> parseIfSupported(String html) {
        if (html == null || html.indexOf("timetable_con") < 0 || html.indexOf("kbgrid_table") < 0) return null;
        Matcher tables = TABLE.matcher(html);
        if (!tables.find()) return null;
        String grid = tables.group(1);
        ArrayList<Course> out = new ArrayList<Course>();
        Set<String> seen = new HashSet<String>();
        Matcher cells = CELL.matcher(grid);
        int courseBlocks = 0;
        while (cells.find()) {
            int day = Integer.parseInt(cells.group(1));
            Matcher blocks = BLOCK.matcher(cells.group(3));
            while (blocks.find()) {
                String block = blocks.group(1);
                Matcher title = TITLE.matcher(block);
                if (!title.find()) throw problem("课程标题缺失");
                String titleHtml = title.group(1);
                // SHU marks pending/unselected courses red. Import the enrolled-course blocks.
                if (RED.matcher(titleHtml).find()) continue;
                String rawName = text(titleHtml);
                String name = CODE.matcher(rawName).replaceAll("").trim();
                if (name.length() == 0) throw problem("课程名称为空");
                String time = "", room = "", teacher = "", note = "", creditText = "";
                Matcher paragraphs = PARA.matcher(block);
                while (paragraphs.find()) {
                    String paragraph = paragraphs.group(1);
                    Matcher tip = TIP.matcher(paragraph);
                    if (!tip.find()) continue;
                    String label = text(tip.group(1));
                    String value = text(paragraph);
                    if (label.indexOf("节/周") >= 0 || label.indexOf("节／周") >= 0) time = value;
                    else if (label.indexOf("上课地点") >= 0) room = value;
                    else if (label.indexOf("教师") >= 0) teacher = value;
                    else if (label.indexOf("备注") >= 0) note = value;
                    else if (label.indexOf("学分") >= 0) creditText = value;
                }
                Matcher schedule = PERIOD.matcher(time);
                if (!schedule.matches()) throw problem("无法识别 " + name + " 的节次/周次：" + time);
                int[] nodes = numbers(schedule.group(1), MAX_NODE, "节次");
                int[] weeks = weeks(schedule.group(2));
                float credit = 0.0f;
                if (creditText.length() != 0) {
                    try {
                        credit = Float.parseFloat(creditText);
                    }
                    catch (NumberFormatException ignored) {
                    }
                }  // Source td rowspans can combine 5-8 and 7-8 courses. Always use each course's own time.
                for (int startNode = 1; startNode <= MAX_NODE; startNode++) {
                    if (nodes[startNode] == 0) continue;
                    int endNode = startNode;
                    while (endNode < MAX_NODE && nodes[endNode + 1] != 0) endNode++;
                    addWeeks(out, seen, name, day, room, teacher, startNode, endNode, weeks, credit, note);
                    startNode = endNode;
                }
                courseBlocks++;
            }
        }
        if (out.isEmpty()) throw problem(courseBlocks == 0 ? "当前表格中没有已选课程；请先在教务中选择学年、学期并查询" : "没有可导入的课程");
        return out;
    }
    private static void addWeeks(List<Course> out, Set<String> seen, String name, int day, String room, String teacher, int startNode, int endNode, int[] weeks, float credit, String note) {
        int[] remaining = weeks.clone();
        for (int start = 1; start <= MAX_WEEK; start++) {
            if (remaining[start] == 0) continue;
            int end = start;
            int step = 1;
            // Prefer contiguous weeks; only use parity for exact runs of at least three occurrences.
            if (start + 4 <= MAX_WEEK && remaining[start + 1] == 0 && remaining[start + 2] != 0 && remaining[start + 3] == 0 && remaining[start + 4] != 0) step = 2;
            while (end + step <= MAX_WEEK && remaining[end + step] != 0 && (step == 1 || remaining[end + 1] == 0)) end += step;
            int type = step == 2 ? (start % 2 == 1 ? 1 : 2) : 0;
            String key = name + "\u0001" + day + "\u0001" + room + "\u0001" + teacher + "\u0001" + startNode + "-" + endNode + "\u0001" + start + "-" + end + "\u0001" + type;
            if (seen.add(key)) out.add(new Course(name, day, room, teacher, startNode, endNode, start, end, type, credit, note, "", ""));
            for (int week = start; week <= end; week += step) remaining[week] = 0;
        }
    }
    private static int[] numbers(String value, int max, String label) {
        int[] found = new int[max + 1];
        Matcher range = RANGE.matcher(value);
        int count = 0;
        while (range.find()) {
            int start = Integer.parseInt(range.group(1));
            String endText = range.group(2);
            int end = endText == null ? start : Integer.parseInt(endText);
            if (start < 1 || end < start || end > max) throw problem(label + "超出范围：" + value);
            for (int n = start; n <= end; n++) found[n] = 1;
            count++;
        }
        if (count == 0) throw problem("未找到" + label + "：" + value);
        return found;
    }
    private static int[] weeks(String value) {
        String normalized = value.replace('，', ',').replace('、', ',').replace("单周", "(单)").replace("双周", "(双)");
        int[] found = new int[MAX_WEEK + 1];
        Matcher range = WEEK.matcher(normalized);
        int count = 0;
        while (range.find()) {
            int start = Integer.parseInt(range.group(1));
            String endText = range.group(2);
            int end = endText == null ? start : Integer.parseInt(endText);
            if (start < 1 || end < start || end > MAX_WEEK) throw problem("周次超出范围：" + value);
            String parity = range.group(3);
            for (int n = start; n <= end; n++) {
                if (parity == null || (parity.equals("单") && n % 2 == 1) || (parity.equals("双") && n % 2 == 0)) found[n] = 1;
            }
            count++;
        }
        if (count == 0) throw problem("未找到周次：" + value);
        return found;
    }
    private static String text(String html) {
        String value = TAG.matcher(html).replaceAll("") .replace("&nbsp;", " ").replace("&#160;", " ").replace("&lt;", "<") .replace("&gt;", ">").replace("&quot;", "\"").replace("&apos;", "'").replace("&amp;", "&");
        Matcher entities = ENTITY.matcher(value);
        StringBuffer decoded = new StringBuffer();
        while (entities.find()) {
            String hex = entities.group(1);
            int cp = Integer.parseInt(hex == null ? entities.group(2) : hex, hex == null ? 10 : 16);
            String replacement = Character.isValidCodePoint(cp) ? new String(Character.toChars(cp)) : "\ufffd";
            entities.appendReplacement(decoded, Matcher.quoteReplacement(replacement));
        }
        entities.appendTail(decoded);
        return decoded.toString().replace('\u00a0', ' ').replaceAll("\\s+", " ").trim();
    }
    private static IllegalArgumentException problem(String detail) {
        return new IllegalArgumentException("上海大学课表导入：" + detail + "。请打开个人课表的“表格”视图后重试。");
    }
}
