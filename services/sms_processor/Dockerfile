FROM python:3.12-slim
WORKDIR /app
COPY sms_processor/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY shared /app/shared
COPY sms_processor/consumer.py .
CMD ["python", "consumer.py"]
