FROM python:3.13-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Copy source code
COPY src/ src/

# Cloud Run sets PORT env var (default 8080)
ENV PORT=8080

# Run MCP server in HTTP mode
CMD ["python", "-m", "financing_mcp", "--transport", "streamable-http"]
