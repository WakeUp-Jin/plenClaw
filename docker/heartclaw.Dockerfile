FROM python:3.12-slim

WORKDIR /app

# Install uv
RUN pip install uv

# Copy dependency file first for better caching
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen --no-dev

# Copy application code
COPY . .

# Create data directory
RUN mkdir -p /app/data

EXPOSE 8000

CMD ["uv", "run", "--no-sync", "python", "src/main.py"]
