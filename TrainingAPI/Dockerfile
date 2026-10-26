FROM python:3.12-slim

# Do not generate .pyc files and ensure stdout/stderr are unbuffered (useful for container logs).
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set working directory inside the container
WORKDIR /app

# Install system dependencies required to build some Python packages (kept minimal).
# If your project needs additional system libs, add them here.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy only requirements first to leverage Docker layer caching
COPY requirements.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . /app

# Expose the port the Sanic app runs on (configured in config.py / .env)
EXPOSE 8080

# Default environment variables (can be overridden via docker-compose or .env)
ENV SERVER_HOST=0.0.0.0
ENV SERVER_PORT=8080
ENV AUTO_RELOAD=false
ENV SERVER_WORKERS=1

RUN useradd --create-home training && chown -R training:training /app
USER training

# Command to run the Sanic application. Using `python main.py` which calls app.run(...)
# For production you may want to use a process manager or gunicorn with sanic workers.
CMD ["python", "main.py"]
