FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_ENABLE_CORS=false \
    STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION=false \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

RUN groupadd -r appuser && useradd -r -g appuser -m -d /home/appuser appuser

WORKDIR /app

RUN apt-get update && apt-get install -y \
    --no-install-recommends \
    gcc \
    python3-dev\
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY dashboard.py .

# Create Streamlit directories and set permissions
RUN mkdir -p /home/appuser/.streamlit && \
    chown -R appuser:appuser /app && \
    chown -R appuser:appuser /home/appuser

USER appuser

# Create Streamlit config
RUN echo "[server]" > /home/appuser/.streamlit/config.toml && \
    echo "headless = true" >> /home/appuser/.streamlit/config.toml && \
    echo "enableCORS = false" >> /home/appuser/.streamlit/config.toml && \
    echo "enableXsrfProtection = false" >> /home/appuser/.streamlit/config.toml

EXPOSE 8501

CMD ["streamlit", "run", "dashboard.py"]