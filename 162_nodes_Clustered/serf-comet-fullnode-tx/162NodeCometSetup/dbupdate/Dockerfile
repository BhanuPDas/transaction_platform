FROM python:3.14-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY logging_setup.py db.py app.py scheduler.py main.py wsgi.py ./

ENV FLASK_PORT=5000
EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Single worker is sufficient: the scheduler runs once, in a background
# thread of this same worker process (started in wsgi.py). --threads 4
# lets the Flask API still serve requests concurrently.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "wsgi:app"]
