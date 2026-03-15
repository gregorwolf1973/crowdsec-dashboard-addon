FROM python:3.11-alpine

RUN pip3 install --no-cache-dir flask requests

COPY rootfs/app /app

WORKDIR /app
EXPOSE 8099

CMD ["python3", "/app/app.py"]
