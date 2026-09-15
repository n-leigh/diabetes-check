FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable unbuffered output for log streaming
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    DIABEATES_DATA_DIR=/var/lib/diabeates

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Create logs directory and ensure appropriate ownership for non-root execution
RUN mkdir -p /app/logs /var/lib/diabeates \
    && useradd --system --user-group --no-create-home appuser \
    && chown -R appuser:appuser /app /var/lib/diabeates

# Switch to non-root user
USER appuser

# Expose production port
EXPOSE 5000

# Container healthcheck targeting http://127.0.0.1:5000/health with python urllib
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request, sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:5000/health').getcode() == 200 else 1)"

# Start production WSGI server
CMD ["python", "wsgi.py"]
