FROM python:3.11-alpine

WORKDIR /app

RUN pip install --no-cache-dir pymysql

COPY sync.py .

CMD ["python", "-u", "sync.py"]
