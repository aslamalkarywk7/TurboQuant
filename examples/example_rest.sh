# مثال REST من أي لغة (curl) — بدون أي مكتبة
# 1) شغّل الخادم (أو عبر Docker):
#    python -m turboquant serve --port 8765
#    docker build -t turboquant . && docker run -p 8765:8765 turboquant
# 2) من أي لغة:
curl -X POST --data-binary @report.pdf "http://localhost:8765/compress?mode=max" -o report.tqz
curl -X POST --data-binary @report.tqz "http://localhost:8765/decompress" -o report.pdf
curl "http://localhost:8765/health"
