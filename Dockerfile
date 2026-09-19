FROM python:3.12-slim
WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir ".[max]" && python -c "import turboquant; print(turboquant.__version__)"
EXPOSE 8765
# REST لأي لغة: POST /compress | POST /decompress
CMD ["python", "-m", "turboquant", "serve", "--port", "8765"]
