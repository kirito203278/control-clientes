# Dos etapas: node compila el frontend; python lo sirve junto con la API (un solo proceso, un solo origen).
# Contexto de build: la RAÍZ del repo (necesita frontend/ y backend/):  docker build -f backend/Dockerfile .

# ---------------------------------------------------------------- etapa 1: frontend
FROM node:22-alpine AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .
# vite.config.ts compila a ../backend/app/static  ->  /backend/app/static
RUN npm run build

# ---------------------------------------------------------------- etapa 2: backend
FROM python:3.14-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 TZ=America/Mexico_City
WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .
COPY --from=frontend /backend/app/static ./app/static
RUN chmod +x entrypoint.sh && useradd --create-home --uid 10001 app && chown -R app /app
USER app

# Render asigna PORT; en local es 8000
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s \
  CMD python -c "import os,urllib.request;urllib.request.urlopen('http://127.0.0.1:%s/api/health' % os.environ.get('PORT','8000'),timeout=4)" || exit 1
ENTRYPOINT ["./entrypoint.sh"]
