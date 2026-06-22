FROM python:3.11-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install --no-cache-dir uv

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock ./

# Install dependencies (without dev)
RUN uv sync --frozen --no-dev

# Copy source code
COPY src/ ./src/
COPY .env.example ./

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "wheel_scout.main:app", "--host", "0.0.0.0", "--port", "8000"]
