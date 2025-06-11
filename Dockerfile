# Use an official Python runtime as base image
FROM python:3.10-slim

# Install required system packages (e.g., for OpenCV support)
RUN apt-get update && apt-get install -y libgl1 && apt-get clean

# Create a working directory
WORKDIR /app

# Copy the application code
COPY . .

# Upgrade pip and install Python dependencies
RUN pip install --upgrade pip \
    && pip install -r torch-requirements.txt \
    && pip install -r requirements.txt

# Expose the Flask port
EXPOSE 8080

# Run the bot
CMD ["python", "app.py"]
