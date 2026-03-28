FROM python:3.11-slim

# Runtime libraries required by PyMuPDF (fitz).
# build-essential is intentionally omitted — all packages in requirements.txt
# ship pre-built manylinux wheels for Python 3.11 and need no compilation.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/backend

# Install Python dependencies first (layer cache).
#
# IMPORTANT: torch must be installed BEFORE requirements.txt so pip resolves
# sentence-transformers against the CPU-only build (~700 MB) instead of the
# default full build (~2 GB). Without this step the image exceeds Railway's
# 4.0 GB limit. The --index-url flag points pip at PyTorch's CPU-only wheel
# registry; --extra-index-url lets it fall back to PyPI for everything else.
RUN pip install --no-cache-dir \
    torch==2.2.2 \
    --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Data directory — in production this is a Railway persistent volume mount.
# The default (DATA_DIR not set) reads from /app/backend/data which is where
# local data lives inside the container for local Docker testing.
# On Railway: set DATA_DIR=/data and mount the volume at /data.
ENV DATA_DIR=/data

# Railway injects $PORT. Default to 8000 for local docker run.
ENV PORT=8000

EXPOSE $PORT

CMD uvicorn main:app --host 0.0.0.0 --port $PORT