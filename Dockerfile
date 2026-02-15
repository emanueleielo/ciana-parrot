FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY config.yaml .
COPY workspace/ workspace/
COPY skills/ skills/

RUN mkdir -p data

CMD ["python", "-m", "src.main"]
