FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 7860

ENV OPENROUTER_API_KEY=${OPENROUTER_API_KEY}

CMD ["python", "app.py"]
