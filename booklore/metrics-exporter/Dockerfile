FROM python:3.11-alpine

WORKDIR /app

RUN pip install --no-cache-dir prometheus_client pymysql

COPY exporter.py .

CMD ["python", "-u", "exporter.py"]
