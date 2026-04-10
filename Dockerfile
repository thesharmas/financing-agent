FROM python:3.13-slim

WORKDIR /app

# Copy source and install
COPY pyproject.toml .
COPY src/ src/
RUN pip install --no-cache-dir .

# Cloud Run sets PORT env var (default 8080)
ENV PORT=8080
ENV PYTHONPATH=/app/src

# Run MCP server in HTTP mode
CMD ["python", "-m", "financing_mcp", "--transport", "streamable-http"]
