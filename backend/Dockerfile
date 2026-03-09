FROM python:3.11-slim

# System dependencies
# libxcb1, libgl1, libglib2.0-0: required by EasyOCR (OpenCV headless still needs these)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    curl \
    libxcb1 \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast package management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy project files
COPY pyproject.toml .
COPY alembic.ini .
COPY alembic/ alembic/
COPY src/ src/

# Install dependencies (with CUDA PyTorch)
RUN uv pip install --system \
    torch torchvision --index-url https://download.pytorch.org/whl/cu128 \
    && uv pip install --system -e ".[dev]"

EXPOSE 8080

CMD ["python", "-m", "cortex"]
