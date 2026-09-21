FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable unbuffered output for log streaming
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Create logs directory and ensure appropriate ownership for non-root execution
RUN mkdir -p /app/logs \
    && useradd --system --user-group --no-create-home appuser \
    && chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose production port
EXPOSE 5000

# Healthcheck the port assigned by the platform, falling back to the local default.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os, urllib.request, sys; port = os.environ.get('PORT', '5000'); sys.exit(0 if urllib.request.urlopen(f'http://127.0.0.1:{port}/health').getcode() == 200 else 1)"

# Start production WSGI server
CMD ["python", "wsgi.py"]
