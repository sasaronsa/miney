# ---------- Etapa 1: build del CSS (Tailwind precompilado) ----------
FROM node:20-alpine AS css
WORKDIR /build
COPY package.json package-lock.json* ./
RUN npm install
COPY tailwind.config.js tailwind.input.css ./
COPY app/templates ./app/templates
RUN npx tailwindcss -i ./tailwind.input.css -o ./app/static/tailwind.css --minify

# ---------- Etapa 2: aplicación ----------
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# CSS recién compilado en la etapa anterior (sobrescribe el que venga en el repo)
COPY --from=css /build/app/static/tailwind.css /app/app/static/tailwind.css

RUN mkdir -p /data
VOLUME ["/data"]

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/login || exit 1

CMD ["python3", "entrypoint.py"]
