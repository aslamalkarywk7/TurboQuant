// TurboQuant.java — ربط Java عبر CLI + REST (بدون dependencies).
// الاستخدام:
//   TurboQuant.compressLossless("report.pdf", "report.tqz", "max");
//   TurboQuant.decompress("report.tqz", "report.pdf");
// يتطلب: python -m turboquant مثبت على الجهاز (أو خادم REST).
import java.io.*;
import java.net.http.*;
import java.net.URI;
import java.nio.file.*;

public class TurboQuant {
    static String PY = System.getenv().getOrDefault("TURBOQUANT_PY", "python");

    public static String run(String... args) throws Exception {
        ProcessBuilder pb = new ProcessBuilder(args);
        pb.redirectErrorStream(true);
        Process p = pb.start();
        String out = new String(p.getInputStream().readAllBytes());
        int code = p.waitFor();
        if (code != 0) throw new RuntimeException("TurboQuant failed: " + out);
        return out.trim();
    }

    public static String compressLossless(String src, String dst, String mode) throws Exception {
        if (dst == null) dst = src + ".tqz";
        if (mode == null) mode = "balanced";
        return run(PY, "-m", "turboquant", "lossless", src, "-o", dst, "--mode", mode);
    }

    public static String decompress(String src, String dst) throws Exception {
        if (dst == null) return run(PY, "-m", "turboquant", "decompress", src);
        return run(PY, "-m", "turboquant", "decompress", src, "-o", dst);
    }

    public static String detect(String src) throws Exception {
        return run(PY, "-m", "turboquant", "detect", src);
    }

    // REST بديل (Java 11+): POST الملف الخام إلى /compress
    public static void compressViaRest(String src, String dst, String mode, int port) throws Exception {
        byte[] data = Files.readAllBytes(Paths.get(src));
        HttpClient c = HttpClient.newHttpClient();
        HttpRequest r = HttpRequest.newBuilder(URI.create("http://127.0.0.1:" + port + "/compress?mode=" + mode))
            .POST(HttpRequest.BodyPublishers.ofByteArray(data)).build();
        HttpResponse<byte[]> resp = c.send(r, HttpResponse.BodyHandlers.ofByteArray());
        if (resp.statusCode() != 200) throw new RuntimeException("server " + resp.statusCode());
        Files.write(Paths.get(dst), resp.body());
    }
}
