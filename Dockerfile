# Lightweight Python runtime
FROM python:3.12-alpine

WORKDIR /app

# Copy application files
COPY . .

ENV PORT=8080
ENV PYTHONUNBUFFERED=1

EXPOSE 8080

CMD ["python3", "server.py", "8080"]
