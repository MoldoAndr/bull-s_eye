
<div align="center">

**Bull's eye 🦬**

<div align="center">

**AI-powered security scanning**
</div>
<img width="50%" src="logo.png">

[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)
[![FastAPI](https://img.shields.io/badge/FastAPI-109989?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-000000?style=for-the-badge&logo=next.js&logoColor=white)](https://nextjs.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](LICENSE)

```ascii
    ┌─────────────────────────────────────┐
    │  🔍 Clone → 🧩 Detect → 🔒 Scan     │
    │  🤖 Analyze → 📊 Report → 💰 Profit │
    └─────────────────────────────────────┘
```
</div>

---

## ⚡ What It Does

Point it at a repo. It **rips apart your codebase**, runs security scanners, feeds everything to an LLM, and spits out a comprehensive analysis. No infrastructure nightmares. No configuration hell.

**Supports:** Python • Go • Rust • JavaScript/TypeScript

---

## 🚀 Quick Start

```bash
git clone https://github.com/MoldoAndr/bulls-eye.git && cd bulls-eye
echo "OLLAMA_API_KEY=your-key-here" > .env
docker-compose up -d
```

**That's it.** No PostgreSQL. No Kubernetes. No selling your soul.

---

## 🛠️ What's Under The Hood

- **Component Detection** - Automatically breaks down massive codebases
- **Multi-Scanner** - Gitleaks, Semgrep, Trivy, Ruff, Bandit, ESLint, Clippy...
- **n8n Orchestration** - Workflow automation without the pain
- **Real-Time Updates** - SSE streams, precise progress tracking
- **SQLite** - Because not everything needs PostgreSQL
- **One-File-At-A-Time** - Ollama Cloud = sequential only (we handle it)

---

## 📡 API That Makes Sense

```bash
# List models
curl localhost:8000/api/models
# Start analysis
curl -X POST localhost:8000/api/jobs -H "Content-Type: application/json" \
  -d '{"repo_url":"https://github.com/user/repo","model":"qwen2.5-coder:7b"}'
# Stream progress
curl localhost:8000/api/jobs/{id}/stream
# Get findings
curl localhost:8000/api/jobs/{id}/findings
```

---

## 🎯 Architecture

```
Web (Next.js) → n8n → FastAPI → Analysis Worker
                                      ↓
                            Security Scanners + LLM
                                      ↓
                            SQLite + Redis + Ollama Cloud
```

Lightweight. Fast. No unnecessary complexity.

---

## ⚙️ Config

```env
OLLAMA_API_KEY=your-key         # Required
OLLAMA_MODEL=gpt-oss:120b-cloud # Default
REDIS_URL=redis://redis:6379/0
ENABLE_LLM_ANALYSIS=true
```

Check `.env.example` for more.

---

## 🐛 Troubleshooting

**Slow?** → LLM requests are sequential. Watch the progress bar.  
**Won't start?** → `docker-compose logs worker`  
**Need to reset?** → `docker-compose down -v && docker-compose up -d`

---

## 📜 License

MIT - Do whatever you want

---