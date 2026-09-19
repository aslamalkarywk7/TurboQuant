// مثال Java — نفس الأسماء: compress / decompress / detect
public class Example {
    public static void main(String[] a) throws Exception {
        System.out.println(TurboQuant.compressLossless("report.pdf", "report.tqz", "max"));
        System.out.println(TurboQuant.decompress("report.tqz", "report.pdf"));
    }
}
