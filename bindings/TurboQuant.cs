// TurboQuant.cs — ربط C# عبر CLI + REST (net6+ بدون packages).
// TurboQuant.CompressLossless("report.pdf", "report.tqz", "max");
// TurboQuant.Decompress("report.tqz", "report.pdf");
using System;
using System.Diagnostics;
using System.IO;
using System.Net.Http;
using System.Threading.Tasks;

public static class TurboQuant
{
    static string Py => Environment.GetEnvironmentVariable("TURBOQUANT_PY") ?? "python";

    public static string Run(params string[] args)
    {
        var psi = new ProcessStartInfo(Py, string.Join(" ", args))
        {
            RedirectStandardOutput = true, RedirectStandardError = true, UseShellExecute = false
        };
        // تمرير المسارات ذات المسافات بأمان
        psi.ArgumentList.Clear();
        foreach (var a in args) psi.ArgumentList.Add(a);
        var p = Process.Start(psi)!;
        string outp = p.StandardOutput.ReadToEnd() + p.StandardError.ReadToEnd();
        p.WaitForExit();
        if (p.ExitCode != 0) throw new Exception("TurboQuant failed: " + outp);
        return outp.Trim();
    }

    public static string CompressLossless(string src, string? dst = null, string mode = "balanced")
        => Run("-m", "turboquant", "lossless", src, "-o", dst ?? (src + ".tqz"), "--mode", mode);

    public static string Decompress(string src, string? dst = null)
        => dst == null ? Run("-m", "turboquant", "decompress", src)
                       : Run("-m", "turboquant", "decompress", src, "-o", dst);

    public static async Task CompressViaRestAsync(string src, string dst, string mode = "max", int port = 8765)
    {
        using var http = new HttpClient();
        var data = await File.ReadAllBytesAsync(src);
        var res = await http.PostAsync($"http://127.0.0.1:{port}/compress?mode={mode}",
            new ByteArrayContent(data));
        res.EnsureSuccessStatusCode();
        await File.WriteAllBytesAsync(dst, await res.Content.ReadAsByteArrayAsync());
    }
}
