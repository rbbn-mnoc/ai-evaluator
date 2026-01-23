FROM python:3.13-slim

WORKDIR /app

# Install uv package manager
RUN pip install --no-cache-dir uv

# Copy project files
COPY pyproject.toml ./
COPY src ./src

# Install dependencies
RUN uv pip install --system -e .

# Install additional dependencies
RUN uv pip install --system fastapi uvicorn

# Create directory for any potential data
RUN mkdir -p /app/data

# Expose port
EXPOSE 8001

# Run the application
CMD ["python", "-m", "uvicorn", "ai_evaluator.main:app", "--host", "0.0.0.0", "--port", "8001"]
