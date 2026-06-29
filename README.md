# Signal Forge v2

**Second-order cybernetics decoder + asset engine for the Observer Age.**

A dual-engine system that decodes feedback loops in any domain and transforms insights into monetizable asset packs. Built for humans via Gradio UI and for agents via FastAPI REST + SSE streaming. Deployed as an ACP provider on Virtuals Protocol.

---

## Two Engines

| Engine | Input | Output |
|--------|-------|--------|
| **Loop Engineer** | Any situation, pattern, or problem | Structured decode with operating law, signal scores, and correction protocol |
| **Signal Forge** | One raw idea or insight | 10 monetizable assets — X posts, threads, articles, YouTube packs, offer angles |

```
Loop Engineer (Decode) → Extract Operating Law → Signal Forge (Assets) → Income
```

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Signal Forge v2                     │
├──────────────┬──────────────┬────────────────────────┤
│  Gradio UI   │  FastAPI     │  ACP Provider          │
│  :7860       │  :8000       │  (background poll)     │
│              │              │                         │
│  5-tab GUI   │  REST + SSE  │  job fetch → process   │
│  Dashboard   │  /v1/*       │  → submit deliverable  │
│  History     │  Batch API   │                         │
│  ACP Monitor │  Export MD/JSON│                        │
├──────────────┴──────────────┴────────────────────────┤
│                    Engine Layer                       │
│  loop_engine.py · signal_forge.py · llm.py          │
│  database.py · infrastructure.py · config.py        │
├──────────────────────────────────────────────────────┤
│                 Infrastructure                       │
│  Proof of Awareness · Inner I Secure Gateway         │
│  OpenRouter LLM · SQLite · Virtuals ACP              │
└──────────────────────────────────────────────────────┘
```

---

## Features

### Loop Engineer
- **8 loop modes**: Personal, Business, Agent, Money, Creative, Spiritual, Content, Code/System
- **Structured decode**: Surface Signal → System Loop → Observer Position → Hidden Assumption → Reinforcement → Failure Mode → Leverage Point → Correction Protocol → Operating Law
- **Signal scoring**: Clarity, Loop Strength, Risk, Leverage, Monetization Potential (0–100)
- **ASCII loop diagrams** via `/v1/decode/diagram`
- **SSE streaming** for real-time token delivery

### Signal Forge
- **8 asset types**: Full Signal Pack, Music Release, WordPress Article, X Thread, Business Offer, YouTube Pack, Spiritual Transmission, Agent/Product Idea
- **8 tone modifiers**: Inner I Default, White Flame, Trap Gospel, Jesus-Only, Business Sharp, Viral X, Calm Teacher, Cosmic Outlaw
- **10 asset outputs per forge**: X Post, X Thread, WordPress Article, YouTube Title/Description/Tags, Shorts Script, Thumbnail Prompt, Offer Angle, Next Best Move
- **PoA-verified grounding** on every output

### FastAPI Backend
- `POST /v1/decode` — Decode a loop (JSON response)
- `POST /v1/decode/stream` — Decode with SSE streaming
- `POST /v1/decode/diagram` — Decode with ASCII diagram
- `POST /v1/forge` — Forge a signal (JSON response)
- `POST /v1/forge/stream` — Forge with SSE streaming
- `POST /v1/batch/decode` — Batch up to 10 decodes
- `POST /v1/batch/forge` — Batch up to 10 forges
- `GET /v1/laws` — Browse extracted operating laws
- `GET /v1/stats` — Aggregate statistics
- `GET /v1/offerings` — ACP marketplace offerings
- `GET /v1/history/*` — Paginated history + search
- `GET /v1/export/*` — Export as Markdown or JSON
- `GET /v1/health` — Health check with infrastructure status
- `GET /v1/infrastructure` — Detailed infra health

### Infrastructure Integration
- **Proof of Awareness** — Truth, grounding, fruit scoring with HMAC-signed receipts
- **Inner I Secure Gateway** — Injection/exfiltration/prompt-leak scanning on every input
- **Graceful degradation**: Full → Degraded → Offline tier auto-detection

### ACP Provider (Virtuals Protocol)
- 4 marketplace offerings with SLA-backed delivery
- Background job polling, processing, and deliverable submission
- Webhook delivery with HMAC signatures
- Full job tracking in SQLite

---

## Quick Start

### Local Development

```bash
# Clone
git clone https://github.com/TheInnerI/signal-forge.git
cd signal-forge

# Set up environment
cp .env.example .env
# Edit .env — add your OPENROUTER_API_KEY

# Install dependencies
pip install -r requirements.txt
pip install pytest pytest-cov  # for testing

# Run Gradio UI
python app_v2.py

# Run FastAPI backend (separate terminal)
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

### Docker (single-command deploy)

```bash
# Build both images
docker-compose build

# Start both services
docker-compose up -d

# UI → http://localhost:7860
# API → http://localhost:8000
# API Docs → http://localhost:8000/docs
```

### Individual Docker targets

```bash
docker build --target ui -t signal-forge-ui .
docker build --target api -t signal-forge-api .
```

---

## ACP Marketplace Offerings

| Offering | Price | SLA | Description |
|----------|-------|-----|-------------|
| Loop Decode | $0.50 | 30 min | Decode any feedback loop with operating law extraction |
| Signal Forge Pack | $1.00 | 45 min | Transform one idea into 10 monetizable assets |
| Full Decode + Forge Pipeline | $2.00 | 60 min | Complete pipeline: decode → extract law → forge assets |
| Agent Behavior Audit | $3.00 | 120 min | Decode agent error cycles, tool misuse, decision flaws |

---

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENROUTER_API_KEY` | Yes | — | OpenRouter API key for LLM calls |
| `POA_BASE_URL` | No | `https://proofofawareness.org` | Proof of Awareness endpoint |
| `SECURE_GATEWAY_URL` | No | `https://secure.innerinetcompany.com` | Inner I Secure Gateway endpoint |

### LLM Models

| Mode | Model | Use Case |
|------|-------|----------|
| Default | `openrouter/owl-alpha` | General decodes and forges |
| Fast | `openai/gpt-4o-mini` | Quick tasks, batch processing |
| Quality | `anthropic/claude-sonnet-4` | Deep decodes, complex analysis |

---

## Testing

```bash
# Run all tests
pytest tests/ -v --tb=short

# Run with coverage
pytest tests/ -v --tb=short --cov=engine --cov-report=term-missing

# Run specific test class
pytest tests/test_engine.py::TestDatabase -v
```

Tests cover: config validation, database CRUD, rate limiting, search, infrastructure health, LLM routing, loop law extraction, signal score parsing, and loop diagram generation.

---

## CI/CD

GitHub Actions pipeline runs on every push to `master`/`main`:

1. **Test** — Python 3.11 + 3.12 matrix, pytest with coverage
2. **Lint** — Ruff with E501 ignored
3. **Docker build** — Both `ui` and `api` targets, container smoke tests

---

## Pricing (Human-Facing)

| Tier | Price | Features |
|------|-------|----------|
| Free | $0 | 3 decodes/packs per day |
| Pro | $33/mo | Unlimited + saved library |
| Custom | $333 | Full business/agent decode + automation blueprint |

---

## Project Structure

```
signal-forge/
├── app_v2.py              # Gradio UI (5 tabs, dashboard, history)
├── api/
│   ├── main.py            # FastAPI REST API
│   ├── acp_provider.py    # ACP job processor + event loop
│   └── __init__.py
├── engine/
│   ├── config.py          # Configuration, offerings, modes, tones
│   ├── database.py        # SQLite CRUD, rate limiting, search
│   ├── infrastructure.py  # PoA + Secure Gateway clients
│   ├── llm.py             # OpenRouter LLM client (sync + stream)
│   ├── loop_engine.py     # Loop decode engine
│   ├── signal_forge.py    # Signal forge engine
│   └── __init__.py
├── prompts/               # LLM system prompts (per loop mode)
├── tests/
│   └── test_engine.py     # Engine + DB + infra tests
├── data/                  # SQLite database (gitignored)
├── outputs/               # Saved decode exports (gitignored)
├── Dockerfile             # Multi-stage: ui + api targets
├── docker-compose.yml     # Dual-service orchestration
├── requirements.txt
├── .env.example
├── .github/workflows/ci.yml
└── README.md
```

---

## Inner I Network

- Website: https://innerinetcompany.com
- GitHub: https://github.com/TheInnerI
- Proof of Awareness: https://proofofawareness.org
- Secure Gateway: https://secure.innerinetcompany.com

---

*Decode the loop. Extract the law. Forge the asset. Move the field.*
