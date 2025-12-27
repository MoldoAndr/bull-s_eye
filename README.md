# 🎯 Bull's Eye - Intelligent Codebase Analysis Platform

Bull's Eye is a lightweight, automated codebase analysis tool that uses n8n for orchestration, LLM-powered analysis via **Ollama Cloud API**, and a modern web interface for viewing results. It breaks down large codebases into manageable components and performs comprehensive security and code quality analysis.

## ✨ Features

- **Multi-Language Support**: Analyze Python, Go, Rust, and JavaScript/TypeScript codebases
- **Intelligent Component Detection**: Automatically breaks down large codebases into logical components
- **LLM-Powered Analysis**: Uses Ollama Cloud API models for intelligent code understanding
- **User-Selectable Models**: Choose from 40+ models including DeepSeek R1/V3, Llama 3.x, Qwen 2.5, Gemma 3, etc.
- **Precise Status Tracking**: Real-time progress updates with detailed stage information
- **Multiple Security Scanners**:
  - **Secrets Detection**: Gitleaks for credential scanning
  - **SAST**: Semgrep for static analysis
  - **Comprehensive**: Trivy for vulnerabilities and misconfigurations
  - **Language-Specific**:
    - Python: Ruff, Bandit, pip-audit
    - Go: golangci-lint, gosec, govulncheck
    - Rust: Clippy, cargo-audit
    - JavaScript: ESLint, npm-audit
- **n8n Integration**: Flexible workflow automation with webhooks and triggers
- **Modern Web UI**: Real-time job monitoring, findings browser, and downloadable reports
- **Lightweight**: Uses SQLite for storage (no heavy PostgreSQL needed)
- **API-First**: RESTful API for integration with CI/CD pipelines

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Web Interface                            │
│                    (Next.js + TailwindCSS)                       │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                      n8n Orchestrator                            │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────────┐ │
│  │   Webhooks   │ │   Triggers   │ │     Notifications        │ │
│  └──────────────┘ └──────────────┘ └──────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Worker API (FastAPI)                        │
│                    + SSE Real-time Updates                       │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Analysis Worker (Python)                      │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                   Component Detector                       │  │
│  │   (Breaks codebase into logical, analyzable chunks)        │  │
│  └───────────────────────────────────────────────────────────┘  │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │ Security Scans  │  │  Code Quality   │  │   LLM Analysis  │  │
│  │   (Gitleaks,    │  │    (ESLint,     │  │  (Ollama Cloud) │  │
│  │   Semgrep...)   │  │    Ruff...)     │  │   Sequential    │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
         │                      │                      │
         ▼                      ▼                      ▼
┌─────────────────────────────┐  ┌─────────────────────────────────┐
│         SQLite              │  │             Redis               │
│        (Storage)            │  │            (Queue)              │
└─────────────────────────────┘  └─────────────────────────────────┘
                                           │
                                           ▼
                              ┌─────────────────────────────────┐
                              │        Ollama Cloud API         │
                              │    (Sequential Requests Only)   │
                              └─────────────────────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- Docker and Docker Compose
- Git
- **Ollama Cloud API Key** (get from https://ollama.com)
- 4GB+ RAM (no local LLM needed)
- 10GB+ disk space

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-org/bulls-eye.git
   cd bulls-eye
   ```

2. **Create environment file**
   ```bash
   cp .env.example .env
   ```

3. **Configure your Ollama API key**
   Edit `.env` and set your Ollama Cloud API key:
   ```env
   OLLAMA_API_KEY=your-ollama-api-key-here
   OLLAMA_MODEL=qwen2.5-coder:7b   # Default model
   ```

4. **Start all services**
   ```bash
   docker-compose up -d
   ```

5. **Access the services**
   - Web UI: http://localhost:3000
   - n8n: http://localhost:5678
   - API: http://localhost:8000

### Available LLM Models

You can select from these models when starting an analysis:

| Model | Description |
|-------|-------------|
| `deepseek-r1` | DeepSeek R1 - Advanced reasoning model |
| `deepseek-v3` | DeepSeek V3 - Latest DeepSeek model |
| `llama3.3` | Llama 3.3 - Meta's latest model |
| `llama3.1:405b` | Llama 3.1 405B - Largest Llama |
| `qwen2.5-coder` | Qwen 2.5 Coder - Optimized for code |
| `qwen2.5:72b` | Qwen 2.5 72B - Large Qwen model |
| `gemma3` | Gemma 3 - Google's latest |
| `phi4` | Phi-4 - Microsoft's efficient model |
| `mistral` | Mistral 7B - Fast and efficient |

## 📖 Usage

### Web Interface

1. Navigate to http://localhost:3000
2. Click "New Analysis"
3. **Select your LLM model** from the dropdown
4. Enter repository URL and branch
5. Monitor progress in real-time with detailed stage tracking
6. View findings, components, and download reports

### Progress Tracking

Bull's Eye provides detailed progress tracking through these stages:

1. **Queued** - Job is waiting to start
2. **Cloning** - Repository is being cloned
3. **Detecting** - Components are being identified
4. **Scanning** - Security scanners are running
5. **Analyzing** - LLM is analyzing each component (sequential)
6. **Reporting** - Executive summary is being generated
7. **Complete** - Analysis finished

### API

```bash
# Get available models
curl http://localhost:8000/api/models

# Submit a new analysis job with model selection
curl -X POST http://localhost:8000/api/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "repo_url": "https://github.com/user/repo.git",
    "branch": "main",
    "name": "My Analysis",
    "model": "qwen2.5-coder:7b"
  }'

# Get job status with detailed progress
curl http://localhost:8000/api/jobs/{job_id}

# Stream real-time status updates (SSE)
curl http://localhost:8000/api/jobs/{job_id}/stream

# Get job findings
curl http://localhost:8000/api/jobs/{job_id}/findings

# Get findings summary
curl http://localhost:8000/api/jobs/{job_id}/findings/summary
```

### n8n Webhooks

```bash
# Trigger analysis via n8n webhook
curl -X POST http://localhost:5678/webhook/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "repo_url": "https://github.com/user/repo.git",
    "branch": "main",
    "model": "qwen2.5-coder:7b"
  }'
```

### GitHub Integration

Configure a GitHub webhook to point to:
```
http://your-server:5678/webhook/github-push
```

Events: `push`, `pull_request`

## ⚙️ Configuration

### Environment Variables

```env
# Ollama Cloud API (REQUIRED)
OLLAMA_API_KEY=your-ollama-api-key-here
OLLAMA_MODEL=qwen2.5-coder:7b

# Redis
REDIS_URL=redis://redis:6379/0

# Worker Settings
CLONE_BASE_DIR=/tmp/repos
MAX_FILE_SIZE_KB=500
ANALYSIS_TIMEOUT=3600
ENABLE_LLM_ANALYSIS=true

# n8n
N8N_BASIC_AUTH_ACTIVE=true
N8N_BASIC_AUTH_USER=admin
N8N_BASIC_AUTH_PASSWORD=your-password
WEBHOOK_URL=http://n8n:5678

# Web
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### Database

Bull's Eye uses **SQLite** for lightweight storage. The database is automatically created at `/app/data/bullseye.db` inside the worker container. Data is persisted in a Docker volume.

### Sequential LLM Requests

The Ollama Cloud API does not support parallel requests. Bull's Eye ensures all LLM calls are made sequentially using an async lock. This means:

- Larger codebases will take longer to analyze
- Progress updates show exactly which component is being analyzed
- You can monitor token usage and response times in the logs

## 🔧 Development

### Running Locally

```bash
# Start infrastructure
docker-compose up -d redis n8n

# Run worker (requires Python 3.11+)
cd worker
pip install -r requirements.txt
python -m uvicorn api.main:app --reload --port 8000

# Run web UI (requires Node.js 18+)
cd web
npm install
npm run dev
```

### Project Structure

```
bulls_eye/
├── docker-compose.yml      # Service orchestration
├── .env.example           # Environment template
├── database/
│   └── schema.sql         # SQLite schema
├── worker/
│   ├── api/               # FastAPI endpoints
│   ├── analysis/          # Analysis engine & component detection
│   ├── llm/               # Ollama Cloud API client
│   ├── scanners/          # Security scanner integrations
│   └── config.py          # Configuration with model list
├── web/                   # Next.js frontend
│   ├── src/app/           # App router pages
│   ├── src/components/    # React components
│   └── src/lib/           # API client & utilities
└── n8n/
    └── workflows/         # n8n workflow templates
```

## 📊 API Response Examples

### Job Status
```json
{
  "id": "uuid",
  "name": "My Analysis",
  "repo_url": "https://github.com/user/repo.git",
  "branch": "main",
  "model": "qwen2.5-coder:7b",
  "status": "analyzing",
  "progress": 65,
  "status_message": "Analyzing component: api",
  "progress_detail": "Processing file 3/12: handlers.py"
}
```

### SSE Stream Events
```
data: {"status": "analyzing", "progress": 65, "message": "Analyzing component: api", "detail": "LLM analyzing src/api/handlers.py"}

data: {"status": "analyzing", "progress": 70, "message": "Analyzing component: api", "detail": "LLM analyzing src/api/routes.py"}
```

## 🐛 Troubleshooting

### "Ollama API key not configured"
- Ensure `OLLAMA_API_KEY` is set in your `.env` file
- Get your API key from https://ollama.com

### Analysis seems slow
- LLM requests are sequential (Ollama Cloud limitation)
- Larger codebases have more components to analyze
- Check the progress detail to see exactly what's happening

### Container won't start
```bash
# Check logs
docker-compose logs worker

# Verify environment
docker-compose config
```

### Database issues
```bash
# Reset database (warning: deletes all data)
docker-compose down -v
docker-compose up -d
```

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

## 🤝 Contributing

Contributions are welcome! Please read our [Contributing Guide](CONTRIBUTING.md) first.
