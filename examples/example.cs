// مثال C# — نفس الأسماء: compress / decompress
class Example {
    static void Main() {
        System.Console.WriteLine(TurboQuant.CompressLossless("report.pdf", "report.tqz", "max"));
        System.Console.WriteLine(TurboQuant.Decompress("report.tqz", "report.pdf"));
    }
}
