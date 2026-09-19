// Package turboquant — Go binding عبر CLI + REST (stdlib فقط).
// usage:
//   out, err := turboquant.CompressLossless("report.pdf", "report.tqz", "max")
package turboquant

import (
	"bytes"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
)

func py() string {
	if v := os.Getenv("TURBOQUANT_PY"); v != "" {
		return v
	}
	return "python"
}

func run(args ...string) (string, error) {
	c := exec.Command(py(), args...)
	var b bytes.Buffer
	c.Stdout = &b
	c.Stderr = &b
	if err := c.Run(); err != nil {
		return b.String(), fmt.Errorf("turboquant: %v: %s", err, b.String())
	}
	return b.String(), nil
}

// CompressLossless يضغط أي ملف lossless بدون فقد جودة.
func CompressLossless(src, dst, mode string) (string, error) {
	if dst == "" {
		dst = src + ".tqz"
	}
	if mode == "" {
		mode = "balanced"
	}
	return run("-m", "turboquant", "lossless", src, "-o", dst, "--mode", mode)
}

// Decompress يفك الضغط مع تحقق sha256.
func Decompress(src, dst string) (string, error) {
	if dst == "" {
		return run("-m", "turboquant", "decompress", src)
	}
	return run("-m", "turboquant", "decompress", src, "-o", dst)
}

// CompressViaRest بديل عبر الخادم: python -m turboquant serve --port 8765
func CompressViaRest(src, dst, mode string, port int) error {
	data, err := os.ReadFile(src)
	if err != nil {
		return err
	}
	resp, err := http.Post(fmt.Sprintf("http://127.0.0.1:%d/compress?mode=%s", port, mode),
		"application/octet-stream", bytes.NewReader(data))
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode != 200 {
		return fmt.Errorf("server %d", resp.StatusCode)
	}
	out, _ := io.ReadAll(resp.Body)
	return os.WriteFile(dst, out, 0644)
}
