# Etapa única por ahora (aún no hay frontend). En la Fase 7 pasa a dos etapas
# (node compila el frontend, python lo sirve), como en el proyecto anterior.
FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["./entrypoint.sh"]
