# Use an official Python runtime as base image
FROM python:3.10-alpine

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Set working directory
WORKDIR /app

# Install system dependencies compatible with Alpine
RUN apk update && apk upgrade && \
    apk add --no-cache \
    build-base \
    libffi-dev \
    musl-dev \
    jpeg-dev \
    zlib-dev \
    libstdc++ \
    mesa-gl \
    libxrender \
    libxext \
    libsm \
    curl


# Pre-copy only requirements files for caching
COPY torch-requirements.txt requirements.txt ./

# Install Python dependencies (this step is cached unless these files change)
RUN pip install --upgrade pip \
    && pip install -r torch-requirements.txt \
    && pip install -r requirements.txt

# Now copy the full application code
COPY . .


# Run the bot
CMD ["python", "app.py"]






