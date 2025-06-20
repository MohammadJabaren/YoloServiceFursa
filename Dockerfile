FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get dist-upgrade -y && \
    apt-get install -y --no-install-recommends \
    build-essential \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    curl && \
    apt-get autoremove -y && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Pre-copy requirements
COPY torch-requirements.txt requirements.txt ./

# Install Python packages
RUN pip install --upgrade pip setuptools && \
    pip install -r torch-requirements.txt && \
    pip install -r requirements.txt

# Copy application code
COPY . .

# Run the bot
CMD ["python", "app.py"]






