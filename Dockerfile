FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y curl netcat-traditional && rm -rf /var/lib/apt/lists/*
COPY docker-requirements.txt .
RUN pip install --no-cache-dir -r docker-requirements.txt
COPY . .
CMD ["python", "-m", "pytest", "test/test_latency_optimization.py", "-v"]
