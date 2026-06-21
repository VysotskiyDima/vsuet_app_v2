FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Install system dependencies if needed (e.g. for building packages, but slim wheels are usually fine)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy pyproject.toml and project metadata to install dependencies
COPY pyproject.toml ./

# Install python dependencies
RUN pip install --no-cache-dir .

# Copy application files
COPY app ./app
COPY resources ./resources

# Expose FastAPI port
EXPOSE 8000

# Start FastAPI application with uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
