FROM python:3.12-slim
WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir ".[max]" && python -c "import turboquant; print(turboquant.__version__)"
EXPOSE 8765
# REST لأي لغة: POST /compress | POST /decompress
# Render يحقن $PORT ديناميكياً — نلتزم به مع fallback محلي
CMD ["sh", "-c", "python -m turboquant serve --port ${PORT:-8765}"]
