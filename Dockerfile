FROM python:3.12-slim
WORKDIR /app
# Run as non-root; HEALTHCHECK for Render/Docker.
RUN useradd -m -u 10001 app
COPY --chown=app:app . /app
RUN pip install --no-cache-dir ".[max]" && python -c "import turboquant; print(turboquant.__version__)"
USER app
EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s CMD python -c "import urllib.request,os; urllib.request.urlopen('http://localhost:%s/api/health' % os.environ.get('PORT','8765'), timeout=4)"
# REST لأي لغة: POST /compress | POST /decompress
# Render يحقن $PORT ديناميكياً — نلتزم به مع fallback محلي
CMD ["sh", "-c", "python -m turboquant serve --port ${PORT:-8765}"]
