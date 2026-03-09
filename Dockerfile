FROM python:3.11-slim

WORKDIR /app

# Install SSL certs, curl, git, and build deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    git \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Install Docker CLI (static binary)
RUN curl -fsSL https://download.docker.com/linux/static/stable/x86_64/docker-27.5.1.tgz | tar xz --strip-components=1 -C /usr/local/bin docker/docker

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create data directories with proper permissions
RUN mkdir -p /app/data/chromadb /app/data/episodes && \
    chmod -R 777 /app/data

# Copy source code and skills
COPY src/ ./src/
COPY skills/ ./skills/
COPY .env .env

# Run the bot
CMD ["python", "-m", "src.main"]
