# Imagen base liviana con Python
FROM python:3.11-slim

# Establecer el directorio de trabajo
WORKDIR /app

# Instalar dependencias del sistema necesarias para compilar y para psycopg2 o similares
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copiar e instalar las dependencias de Python
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copiar archivos y carpetas del proyecto de forma explícita
COPY manage.py .
COPY db.sqlite3 .
COPY backend/ backend/
COPY PreprocessingApp/ PreprocessingApp/
COPY UsersApp/ UsersApp/
COPY csv_uploads/ csv_uploads/
COPY media/ media/

# Variables de entorno necesarias
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Recolectar archivos estáticos (opcional, puede omitirse si no aplica)
RUN python manage.py collectstatic --noinput || true

# Ejecutar migraciones (opcional)
RUN python manage.py migrate --noinput || true

# Exponer el puerto para AWS App Runner
EXPOSE 8080

# Comando para iniciar el servidor con Gunicorn
CMD ["gunicorn", "backend.wsgi:application", "--bind", "0.0.0.0:8080"]
