# Usa una imagen base oficial de Python
FROM python:3.11-slim

# Instala dependencias del sistema, incluyendo libgomp
RUN apt-get update && apt-get install -y \
    libgomp1 \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Establece el directorio de trabajo
WORKDIR /app

# Copia el código al contenedor
COPY . /app/

# Instala las dependencias de Python
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

EXPOSE 8000

CMD ["gunicorn", "backend.wsgi:application", "--bind", "0.0.0.0:8000"]
