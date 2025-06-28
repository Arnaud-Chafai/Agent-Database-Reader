FROM python:3.12-slim

# Instalar dependencias básicas
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Configurar repositorio Microsoft para Debian 12 (método actualizado)
RUN curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
    && curl -fsSL https://packages.microsoft.com/config/debian/12/packages-microsoft-prod.deb -o packages-microsoft-prod.deb \
    && dpkg -i packages-microsoft-prod.deb \
    && rm packages-microsoft-prod.deb

# Instalar ODBC drivers
RUN apt-get update \
    && ACCEPT_EULA=Y apt-get install -y \
        msodbcsql18 \
        unixodbc-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiar archivos de dependencias
COPY pyproject.toml ./
COPY uv.lock ./

# Instalar UV y dependencias
RUN pip install uv
RUN uv sync --frozen

# Copiar código fuente
COPY src/ ./src/
COPY context/ ./context/
COPY .env ./

# Variables de entorno
ENV DB_DRIVER="ODBC Driver 18 for SQL Server"
ENV PYTHONPATH=/app

# Comando de inicio  
CMD ["uv", "run", "python", "-m", "src.sql_llm_agent.mcp_server.main"]