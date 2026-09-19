#!/bin/sh
# تثبيت TurboQuant بنقرة واحدة (Linux/macOS)
# Usage: sh scripts/install.sh
set -e
echo "Installing TurboQuant..."
python3 -m pip install --upgrade pip
pip3 install "turboquant[max]"
python3 -m turboquant detect --help >/dev/null
echo "Done! Try: python3 -m turboquant lossless <file> -o out.tqz --mode max"
