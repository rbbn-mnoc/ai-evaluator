FROM python:3.13-slim

WORKDIR /app

# Install uv package manager
RUN pip install --no-cache-dir uv

# Copy project files
COPY pyproject.toml ./
COPY README.md ./
COPY src ./src

# Install dependencies
RUN uv pip install --system -e .

# Install additional dependencies
RUN uv pip install --system fastapi uvicorn

# Create directory for any potential data
RUN mkdir -p /app/data

# Expose port (default 8002, but configurable via SERVER_PORT env var)
EXPOSE 8002

# Run the application using main.py which respects SERVER_HOST and SERVER_PORT env vars
CMD ["python", "-m", "ai_evaluator.main"]
