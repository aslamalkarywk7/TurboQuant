import java.io.*;
import java.nio.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import java.util.zip.GZIPInputStream;

/** TqzDecode — مفكك TurboQuant أصلي بلغة Java (بدون Python، بدون dependencies).
 *  يدعم: method=single + codecs (gzip/store) + transforms
 *  (none/delta8/xor8/delta16le/pngfilter/bwt). الباقي → خطأ واضح.
 *  الاستخدام: java TqzDecode in.tqz out.bin
 */
public class TqzDecode {
    static String str(byte[] j, String k) {
        String s = new String(j, StandardCharsets.UTF_8);
        String q = "\"" + k + "\"";
        int i = s.indexOf(q);
        if (i < 0) return "";
        i = s.indexOf(':', i + q.length()) + 1;
        while (i < s.length() && Character.isWhitespace(s.charAt(i))) i++;
        if (s.charAt(i) == '"') {
            int e = s.indexOf('"', i + 1);
            return s.substring(i + 1, e);
        }
        int e = i;
        while (e < s.length() && "-+0123456789.eE".indexOf(s.charAt(e)) >= 0) e++;
        return s.substring(i, e);
    }
    static int strideOf(byte[] j) {
        String s = new String(j, StandardCharsets.UTF_8);
        int i = s.indexOf("\"stride\"");
        if (i < 0) return 1;
        i = s.indexOf(':', i) + 1;
        StringBuilder n = new StringBuilder();
        while (i < s.length() && Character.isDigit(s.charAt(i))) n.append(s.charAt(i++));
        return n.length() == 0 ? 1 : Integer.parseInt(n.toString());
    }
    static byte[] gunzip(byte[] b) throws Exception {
        try (GZIPInputStream g = new GZIPInputStream(new ByteArrayInputStream(b));
             ByteArrayOutputStream o = new ByteArrayOutputStream()) {
            g.transferTo(o);
            return o.toByteArray();
        }
    }
    static int paeth(int a, int b, int c) {
        int p = a + b - c, pa = Math.abs(p - a), pb = Math.abs(p - b), pc = Math.abs(p - c);
        return (pa <= pb && pa <= pc) ? a : (pb <= pc ? b : c);
    }
    static byte[] invert(byte[] d, String t, int stride) throws Exception {
        int n = d.length;
        if (t.isEmpty() || t.equals("none")) return d;
        if (t.equals("delta8") || t.equals("xor8")) {
            byte[] o = new byte[n];
            if (n == 0) return o;
            o[0] = d[0];
            for (int i = 1; i < n; i++)
                o[i] = t.equals("delta8") ? (byte) (d[i] + o[i - 1]) : (byte) (d[i] ^ o[i - 1]);
            return o;
        }
        if (t.equals("delta16le")) {
            if (n == 0) return new byte[0];
            int pad = d[0] & 0xFF;
            byte[] raw = Arrays.copyOfRange(d, 1, n);
            ShortBuffer sb = ByteBuffer.wrap(raw).order(ByteOrder.LITTLE_ENDIAN).asShortBuffer();
            short[] s = new short[sb.remaining()];
            sb.get(s);
            ByteBuffer ob = ByteBuffer.allocate(raw.length).order(ByteOrder.LITTLE_ENDIAN);
            int acc = s[0];
            ob.putShort((short) acc);
            for (int i = 1; i < s.length; i++) { acc = (short) (acc + s[i]); ob.putShort((short) acc); }
            return Arrays.copyOf(ob.array(), raw.length - pad);
        }
        if (t.equals("pngfilter")) {
            ByteBuffer h = ByteBuffer.wrap(d).order(ByteOrder.BIG_ENDIAN);
            int orig = h.getInt(0), st = h.getShort(4) & 0xFFFF, rows = h.getInt(6), off = 10;
            ByteArrayOutputStream o = new ByteArrayOutputStream();
            byte[] prev = new byte[st];
            for (int r = 0; r < rows; r++) {
                int f = d[off] & 0xFF;
                byte[] cur = new byte[st];
                for (int i = 0; i < st; i++) {
                    int a = i > 0 ? cur[i - 1] & 0xFF : 0, b = prev[i] & 0xFF, c = i > 0 ? prev[i - 1] & 0xFF : 0;
                    int v = d[off + 1 + i] & 0xFF;
                    cur[i] = (byte) (f == 0 ? v : f == 1 ? (v + a) & 0xFF : f == 2 ? (v + b) & 0xFF
                        : f == 3 ? (v + ((a + b) >> 1)) & 0xFF : (v + paeth(a, b, c)) & 0xFF);
                }
                o.write(cur, 0, st);
                prev = cur;
                off += 1 + st;
            }
            return Arrays.copyOf(o.toByteArray(), orig);
        }
        if (t.equals("bwt")) {
            ByteBuffer h = ByteBuffer.wrap(d).order(ByteOrder.BIG_ENDIAN);
            int nb = h.getInt(0), off = 4;
            ByteArrayOutputStream o = new ByteArrayOutputStream();
            for (int k = 0; k < nb; k++) {
                int bl = h.getInt(off), pr = h.getInt(off + 4);
                off += 8;
                byte[] last = Arrays.copyOfRange(d, off, off + bl);
                off += bl;
                int[] cnt = new int[256];
                for (byte x : last) cnt[x & 0xFF]++;
                int[] st2 = new int[256];
                int s2 = 0;
                for (int c = 0; c < 256; c++) { st2[c] = s2; s2 += cnt[c]; }
                int[] occ = new int[256], lf = new int[bl];
                for (int i = 0; i < bl; i++) { lf[i] = st2[last[i] & 0xFF] + occ[last[i] & 0xFF]++; }
                byte[] blk = new byte[bl];
                int j2 = pr;
                for (int i = bl - 1; i >= 0; i--) { blk[i] = last[j2]; j2 = lf[j2]; }
                o.write(blk, 0, bl);
            }
            return o.toByteArray();
        }
        throw new Exception("transform '" + t + "' needs Python");
    }
    public static void main(String[] a) throws Exception {
        byte[] all = Files.readAllBytes(Paths.get(a[0]));
        if (!(all[0] == 'T' && all[1] == 'Q' && all[2] == 'Z' && all[3] == '2')) throw new Exception("not TQZ2");
        int hl = ByteBuffer.wrap(all, 4, 4).order(ByteOrder.BIG_ENDIAN).getInt();
        byte[] j = Arrays.copyOfRange(all, 8, 8 + hl);
        byte[] body = Arrays.copyOfRange(all, 8 + hl, all.length);
        String method = str(j, "method"), codec = str(j, "codec"), tr = str(j, "transform");
        if (!method.isEmpty() && !method.equals("single")) throw new Exception("method '" + method + "' needs Python");
        byte[] dec;
        if (codec.equals("gzip")) dec = gunzip(body);
        else if (codec.equals("store")) dec = body;
        else throw new Exception("codec '" + codec + "' needs Python");
        byte[] raw = invert(dec, tr, strideOf(j));
        long want = Long.parseLong(str(j, "orig_size"));
        if (raw.length != want) throw new Exception("size mismatch");
        MessageDigest md = MessageDigest.getInstance("SHA-256");
        StringBuilder sha = new StringBuilder();
        for (byte x : md.digest(raw)) sha.append(String.format("%02x", x));
        if (!sha.toString().equals(str(j, "sha256"))) throw new Exception("sha256 mismatch");
        Files.write(Paths.get(a[1]), raw);
        System.out.println("{\"output\":\"" + a[1] + "\",\"verified\":true}");
    }
}
