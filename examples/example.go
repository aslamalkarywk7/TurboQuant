// مثال Go — نفس الأسماء: compress / decompress
package main

import (
	"fmt"
	tq "example.com/tq/bindings"
)

func main() {
	out, err := tq.CompressLossless("report.pdf", "report.tqz", "max")
	fmt.Println(out, err)
	out, err = tq.Decompress("report.tqz", "report.pdf")
	fmt.Println(out, err)
}
