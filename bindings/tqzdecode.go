// tqzdecode.go — مفكك TurboQuant أصلي بلغة Go (بدون Python، stdlib فقط).
// يدعم: method=single + codecs (gzip/store) + transforms
// (none/delta8/xor8/delta16le/pngfilter/bwt). الباقي → خطأ واضح.
// الاستخدام: go run bindings/tqzdecode.go in.tqz out.bin
package main

import (
	"bytes"
	"compress/gzip"
	"crypto/sha256"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"os"
)

type header struct {
	Codec    string         `json:"codec"`
	Method   string         `json:"method"`
	Transform string        `json:"transform"`
	TParams  map[string]int `json:"tparams"`
	OrigSize int64          `json:"orig_size"`
	Sha256   string         `json:"sha256"`
}

func paeth(a, b, c int) int {
	p := a + b - c
	pa, pb, pc := abs(p-a), abs(p-b), abs(p-c)
	if pa <= pb && pa <= pc {
		return a
	}
	if pb <= pc {
		return b
	}
	return c
}
func abs(x int) int {
	if x < 0 {
		return -x
	}
	return x
}

func invert(d []byte, t string, stride int) ([]byte, error) {
	switch t {
	case "", "none":
		return d, nil
	case "delta8", "xor8":
		o := make([]byte, len(d))
		if len(d) == 0 {
			return o, nil
		}
		o[0] = d[0]
		for i := 1; i < len(d); i++ {
			if t == "delta8" {
				o[i] = d[i] + o[i-1]
			} else {
				o[i] = d[i] ^ o[i-1]
			}
		}
		return o, nil
	case "delta16le":
		if len(d) == 0 {
			return []byte{}, nil
		}
		pad := int(d[0])
		raw := d[1:]
		m := len(raw) / 2
		o := make([]byte, len(raw))
		acc := int(int16(binary.LittleEndian.Uint16(raw)))
		binary.LittleEndian.PutUint16(o, uint16(int16(acc)))
		for i := 1; i < m; i++ {
			acc = int(int16(acc + int(int16(binary.LittleEndian.Uint16(raw[i*2:])))))
			binary.LittleEndian.PutUint16(o[i*2:], uint16(int16(acc)))
		}
		return o[:len(o)-pad], nil
	case "pngfilter":
		orig := int(binary.BigEndian.Uint32(d))
		st := int(binary.BigEndian.Uint16(d[4:]))
		nrows := int(binary.BigEndian.Uint32(d[6:]))
		off := 10
		var out []byte
		prev := make([]byte, st)
		for r := 0; r < nrows; r++ {
			f := int(d[off])
			if f > 4 {
				return nil, fmt.Errorf("bad filter byte")
			}
			cur := make([]byte, st)
			for i := 0; i < st; i++ {
				a, b, c := 0, int(prev[i]), 0
				if i > 0 {
					a, c = int(cur[i-1]), int(prev[i-1])
				}
				v := int(d[off+1+i])
				switch f {
				case 0:
					cur[i] = byte(v)
				case 1:
					cur[i] = byte(v + a)
				case 2:
					cur[i] = byte(v + b)
				case 3:
					cur[i] = byte(v + ((a + b) >> 1))
				case 4:
					cur[i] = byte(v + paeth(a, b, c))
				}
			}
			out = append(out, cur...)
			prev = cur
			off += 1 + st
		}
		return out[:orig], nil
	case "bwt":
		nb := int(binary.BigEndian.Uint32(d))
		off := 4
		var out []byte
		for k := 0; k < nb; k++ {
			bl := int(binary.BigEndian.Uint32(d[off:]))
			pr := int(binary.BigEndian.Uint32(d[off+4:]))
			off += 8
			last := d[off : off+bl]
			off += bl
			var cnt [256]int
			for _, b := range last {
				cnt[b]++
			}
			var start [256]int
			s := 0
			for c := 0; c < 256; c++ {
				start[c] = s
				s += cnt[c]
			}
			occ := [256]int{}
			lf := make([]int, bl)
			for i, b := range last {
				lf[i] = start[b] + occ[b]
				occ[b]++
			}
			blk := make([]byte, bl)
			j := pr
			for i := bl - 1; i >= 0; i-- {
				blk[i] = last[j]
				j = lf[j]
			}
			out = append(out, blk...)
		}
		return out, nil
	}
	return nil, fmt.Errorf("transform '%s' needs Python", t)
}

func main() {
	if len(os.Args) < 3 {
		fmt.Fprintln(os.Stderr, "usage: go run tqzdecode.go in.tqz out")
		os.Exit(2)
	}
	all, _ := os.ReadFile(os.Args[1])
	if string(all[:4]) != "TQZ2" {
		fmt.Fprintln(os.Stderr, "not TQZ2")
		os.Exit(1)
	}
	hl := int(binary.BigEndian.Uint32(all[4:]))
	var h header
	if err := json.Unmarshal(all[8:8+hl], &h); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	body := all[8+hl:]
	if h.Method != "" && h.Method != "single" {
		fmt.Fprintln(os.Stderr, "method '"+h.Method+"' needs Python")
		os.Exit(1)
	}
	var dec []byte
	switch h.Codec {
	case "gzip":
		r, err := gzip.NewReader(bytes.NewReader(body))
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		dec, _ = io.ReadAll(r)
	case "store":
		dec = body
	default:
		fmt.Fprintln(os.Stderr, "codec '"+h.Codec+"' needs Python")
		os.Exit(1)
	}
	raw, err := invert(dec, h.Transform, h.TParams["stride"])
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	if int64(len(raw)) != h.OrigSize {
		fmt.Fprintln(os.Stderr, "size mismatch")
		os.Exit(1)
	}
	sum := sha256.Sum256(raw)
	if hex.EncodeToString(sum[:]) != h.Sha256 {
		fmt.Fprintln(os.Stderr, "sha256 mismatch")
		os.Exit(1)
	}
	os.WriteFile(os.Args[2], raw, 0644)
	fmt.Println(`{"verified":true}`)
}
