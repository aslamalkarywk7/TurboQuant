using System;
using System.IO;
using System.IO.Compression;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

/// <summary>TqzDecode — مفكك TurboQuant أصلي بلغة C# (بدون Python، بدون حزم).
/// يدعم: method=single + codecs (gzip/brotli/store) + transforms
/// (none/delta8/xor8/delta16le/pngfilter/bwt). الباقي → استثناء واضح.</summary>
public static class TqzDecode
{
    static int Paeth(int a, int b, int c)
    {
        int p = a + b - c, pa = Math.Abs(p - a), pb = Math.Abs(p - b), pc = Math.Abs(p - c);
        return (pa <= pb && pa <= pc) ? a : (pb <= pc ? b : c);
    }

    static byte[] Gunzip(byte[] b)
    {
        using var ms = new MemoryStream(b);
        using var g = new GZipStream(ms, CompressionMode.Decompress);
        using var o = new MemoryStream();
        g.CopyTo(o);
        return o.ToArray();
    }

    static byte[] Brotli(byte[] b)
    {
        using var ms = new MemoryStream(b);
        using var g = new BrotliStream(ms, CompressionMode.Decompress);
        using var o = new MemoryStream();
        g.CopyTo(o);
        return o.ToArray();
    }

    static byte[] Invert(byte[] d, string t, int stride)
    {
        int n = d.Length;
        if (string.IsNullOrEmpty(t) || t == "none") return d;
        if (t == "delta8" || t == "xor8")
        {
            var o = new byte[n];
            if (n == 0) return o;
            o[0] = d[0];
            for (int i = 1; i < n; i++)
                o[i] = t == "delta8" ? (byte)(d[i] + o[i - 1]) : (byte)(d[i] ^ o[i - 1]);
            return o;
        }
        if (t == "delta16le")
        {
            if (n == 0) return Array.Empty<byte>();
            int pad = d[0];
            int m = (n - 1) / 2;
            var o = new byte[m * 2];
            int acc = BitConverter.ToInt16(d, 1);
            Buffer.BlockCopy(BitConverter.GetBytes((short)acc), 0, o, 0, 2);
            for (int i = 1; i < m; i++)
            {
                acc = (short)(acc + BitConverter.ToInt16(d, 1 + i * 2));
                Buffer.BlockCopy(BitConverter.GetBytes((short)acc), 0, o, i * 2, 2);
            }
            Array.Resize(ref o, o.Length - pad);
            return o;
        }
        if (t == "pngfilter")
        {
            int orig = (d[0] << 24) | (d[1] << 16) | (d[2] << 8) | d[3];
            int st = (d[4] << 8) | d[5];
            int rows = (d[6] << 24) | (d[7] << 16) | (d[8] << 8) | d[9];
            int off = 10;
            using var o = new MemoryStream();
            var prev = new byte[st];
            for (int r = 0; r < rows; r++)
            {
                int f = d[off];
                if (f > 4) throw new InvalidDataException("bad filter byte");
                var cur = new byte[st];
                for (int i = 0; i < st; i++)
                {
                    int a = i > 0 ? cur[i - 1] : 0, b = prev[i], c = i > 0 ? prev[i - 1] : 0;
                    int v = d[off + 1 + i];
                    cur[i] = f == 0 ? (byte)v : f == 1 ? (byte)(v + a) : f == 2 ? (byte)(v + b)
                        : f == 3 ? (byte)(v + ((a + b) >> 1)) : (byte)(v + Paeth(a, b, c));
                }
                o.Write(cur, 0, st);
                prev = cur;
                off += 1 + st;
            }
            var all = o.ToArray();
            Array.Resize(ref all, orig);
            return all;
        }
        if (t == "bwt")
        {
            int nb = (d[0] << 24) | (d[1] << 16) | (d[2] << 8) | d[3];
            int off = 4;
            using var o = new MemoryStream();
            for (int k = 0; k < nb; k++)
            {
                int bl = (d[off] << 24) | (d[off + 1] << 16) | (d[off + 2] << 8) | d[off + 3];
                int pr = (d[off + 4] << 24) | (d[off + 5] << 16) | (d[off + 6] << 8) | d[off + 7];
                off += 8;
                var cnt = new int[256];
                for (int i = 0; i < bl; i++) cnt[d[off + i]]++;
                var start = new int[256];
                int s = 0;
                for (int c = 0; c < 256; c++) { start[c] = s; s += cnt[c]; }
                var occ = new int[256];
                var lf = new int[bl];
                for (int i = 0; i < bl; i++) { lf[i] = start[d[off + i]] + occ[d[off + i]]++; }
                var blk = new byte[bl];
                int j = pr;
                for (int i = bl - 1; i >= 0; i--) { blk[i] = d[off + j]; j = lf[j]; }
                o.Write(blk, 0, bl);
                off += bl;
            }
            return o.ToArray();
        }
        throw new NotSupportedException($"transform '{t}' needs Python");
    }

    public static string Decode(string src, string dst)
    {
        byte[] all = File.ReadAllBytes(src);
        if (all.Length < 8 || all[0] != 'T' || all[1] != 'Q' || all[2] != 'Z' || all[3] != '2')
            throw new InvalidDataException("not a TQZ2 file");
        int hl = (all[4] << 24) | (all[5] << 16) | (all[6] << 8) | all[7];
        using var doc = JsonDocument.Parse(Encoding.UTF8.GetString(all, 8, hl));
        var root = doc.RootElement;
        string method = root.TryGetProperty("method", out var m) ? m.GetString() ?? "" : "";
        string codec = root.TryGetProperty("codec", out var c) ? c.GetString() ?? "" : "";
        string tr = root.TryGetProperty("transform", out var t) ? t.GetString() ?? "" : "";
        int stride = (root.TryGetProperty("tparams", out var tp) && tp.TryGetProperty("stride", out var st)) ? st.GetInt32() : 1;
        long want = root.GetProperty("orig_size").GetInt64();
        string sha = root.GetProperty("sha256").GetString() ?? "";
        if (method != "" && method != "single") throw new NotSupportedException($"method '{method}' needs Python");
        byte[] body = new ArraySegment<byte>(all, 8 + hl, all.Length - 8 - hl).ToArray();
        byte[] dec = codec switch
        {
            "gzip" => Gunzip(body),
            "brotli" => Brotli(body),
            "store" => body,
            _ => throw new NotSupportedException($"codec '{codec}' needs Python"),
        };
        byte[] raw = Invert(dec, tr, stride);
        if (raw.Length != want) throw new InvalidDataException("size mismatch");
        string got = Convert.ToHexString(SHA256.HashData(raw)).ToLowerInvariant();
        if (got != sha) throw new InvalidDataException("sha256 mismatch");
        File.WriteAllBytes(dst, raw);
        return "{\"output\":\"" + dst + "\",\"verified\":true}";
    }
}
