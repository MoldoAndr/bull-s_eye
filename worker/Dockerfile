FROM python:3.12-slim

# Create a non-root user
RUN groupadd -r bullseye && useradd -r -g bullseye -m -d /home/bullseye bullseye

# Install system dependencies and security tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    wget \
    build-essential \
    libffi-dev \
    libssl-dev \
    # For PDF generation
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libcairo2 \
    libgirepository1.0-dev \
    # Cleanup
    && rm -rf /var/lib/apt/lists/*

# Install Go (for Go tools)
ENV GO_VERSION=1.22.0
RUN curl -LO https://go.dev/dl/go${GO_VERSION}.linux-amd64.tar.gz \
    && tar -C /usr/local -xzf go${GO_VERSION}.linux-amd64.tar.gz \
    && rm go${GO_VERSION}.linux-amd64.tar.gz
ENV PATH="/usr/local/go/bin:/usr/local/bin:${PATH}"

# Install Rust (for Rust tools)
ENV CARGO_HOME=/usr/local/cargo
ENV RUSTUP_HOME=/usr/local/rustup
ENV PATH="/usr/local/cargo/bin:/usr/local/bin:${PATH}"
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --no-modify-path

# Install Node.js (for JS/TS tools)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install security scanning tools
# Python
RUN pip install --no-cache-dir ruff bandit pip-audit mypy lizard

# Go
ENV GOBIN=/usr/local/bin
RUN go install github.com/securego/gosec/v2/cmd/gosec@latest \
    && go install golang.org/x/vuln/cmd/govulncheck@latest \
    && go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest

# Rust
RUN cargo install --root /usr/local cargo-audit cargo-deny

# Node.js
RUN npm install -g @biomejs/biome

# Multi-language tools
RUN curl -fsSL https://github.com/opengrep/opengrep/releases/latest/download/opengrep_manylinux_x86 -o /usr/local/bin/opengrep \
    && chmod +x /usr/local/bin/opengrep

# OSV-Scanner
RUN curl -fsSL https://github.com/google/osv-scanner/releases/latest/download/osv-scanner_linux_amd64 -o /usr/local/bin/osv-scanner \
    && chmod +x /usr/local/bin/osv-scanner

# Secrets detection
ARG GITLEAKS_VERSION=8.30.0
RUN curl -fsSL https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}/gitleaks_${GITLEAKS_VERSION}_linux_x64.tar.gz -o /tmp/gitleaks.tar.gz \
    && tar -xzf /tmp/gitleaks.tar.gz -C /tmp \
    && mv /tmp/gitleaks /usr/local/bin/gitleaks \
    && chmod +x /usr/local/bin/gitleaks \
    && rm /tmp/gitleaks.tar.gz

# Trivy for comprehensive scanning
RUN curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b /usr/local/bin

WORKDIR /app

# Copy requirements first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directories
RUN mkdir -p /app/repos /app/cache /app/reports /app/data

RUN chown -R bullseye:bullseye /app /home/bullseye

# Ensure non-root can use installed toolchains
RUN chmod -R a+rX /usr/local/cargo /usr/local/rustup || true

USER bullseye

# Run the worker
CMD ["python", "-m", "celery", "-A", "worker.celery_app", "worker", "--loglevel=info", "--concurrency=1"]
