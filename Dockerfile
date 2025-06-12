# Use an official Python runtime as base image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgl1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

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
