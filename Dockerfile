FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Seed the (fresh) synthetic DB, then serve. Seeding is deterministic and idempotent
# (schema.sql drops+recreates), so a restart just regenerates the same demo data.
CMD ["sh", "-c", "python db/seed.py && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
