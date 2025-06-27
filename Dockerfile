FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    unixodbc \
    unixodbc-dev \
    && rm -rf /var/lib/apt/lists/*

RUN curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - \
    && curl https://packages.microsoft.com/config/debian/11/prod.list > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y msodbcsql18 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ./
COPY uv.lock ./

RUN pip install uv
RUN uv sync --frozen

COPY src/ ./src/
COPY context/ ./context/
COPY .env ./

ENV DB_DRIVER="ODBC Driver 18 for SQL Server"
ENV PYTHONPATH=/app

CMD ["uv", "run", "python", "-m", "src.sql_llm_agent.mcp_server.main"]