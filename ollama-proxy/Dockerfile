FROM python:3.12-slim
RUN pip install --no-cache-dir aiohttp
COPY ollama-wol-proxy.py /app/proxy.py
CMD ["python3", "-u", "/app/proxy.py"]
