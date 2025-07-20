# === STAGE 1: Builder (Instalar dependencias) ===
FROM python:3.11-slim as builder

# Instalar dependencias del sistema necesarias para compilar
RUN apt-get update && apt-get install -y \
    build-essential \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Crear directorio para las dependencias
WORKDIR /app

# Copiar solo requirements.txt primero (para aprovechar cache de Docker)
COPY requirements.txt .

# Instalar dependencias de Python en un directorio específico
RUN pip install --upgrade pip && \
    pip install --user --no-cache-dir -r requirements.txt

# === STAGE 2: Runtime (Imagen final optimizada) ===
FROM python:3.11-slim as runtime

# Instalar solo las dependencias de runtime necesarias
RUN apt-get update && apt-get install -y \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Crear usuario no-root para seguridad
RUN useradd --create-home --shell /bin/bash app

# Establecer directorio de trabajo
WORKDIR /app

# Copiar dependencias instaladas desde el stage builder
COPY --from=builder /root/.local /home/app/.local

# Copiar código de la aplicación
COPY --chown=app:app . .

# Crear directorios necesarios
RUN mkdir -p logs media static staticfiles && \
    chown -R app:app /app

# Cambiar al usuario no-root
USER app

# Agregar el directorio local de Python al PATH
ENV PATH=/home/app/.local/bin:$PATH

# Exponer puerto
EXPOSE 8000

# Comando por defecto (se puede sobrescribir en docker-compose)
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
