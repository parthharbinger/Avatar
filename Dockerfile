FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install uv for fast dependency management
RUN pip install uv

# Copy dependency files first (for layer caching)
COPY pyproject.toml uv.lock ./

# Install production dependencies (no dev tools)
RUN uv sync --frozen --no-dev

# Copy application code
COPY app/ ./app/

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# Run the FastAPI server
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
