---
title: SQL Repair Environment
emoji: 🤖
colorFrom: blue
colorTo: green
sdk: docker
app_port: 8000
pinned: false
---

# 🧠 AI SQL Repair Environment

An **OpenEnv-compliant** reinforcement learning environment where an AI agent repairs broken SQL queries and is scored on correctness.

---

## 🚀 Overview

| Property | Value |
|---|---|
| Environment Type | Single-agent |
| Reward Range | 0.0 → 1.0 |
| Difficulty Levels | Easy, Medium, Hard |
| Execution Backend | SQLite (in-memory) |
| Inference | Groq LLM (llama-3.1-8b) + FLAN-T5 fallback |
| Framework | OpenEnv + FastAPI + Gradio |

---

## 🎮 How It Works

```
1. Agent receives:  broken SQL query + DB schema + difficulty
2. Agent produces:  corrected SQL query
3. Environment:     executes SQL in SQLite sandbox
4. Reward issued:   based on correctness (0.0 → 1.0)
```

---

## 🏆 Reward Scale

| Score | Condition |
|---|---|
| **1.0** | Exact normalized query match |
| **0.8** | Output rows match expected result |
| **0.3** | Valid SELECT structure, wrong output |
| **0.0** | Syntax error or no SELECT |

---

## 🔌 REST API

The environment server runs on **port 8000**:

```bash
POST /reset      → get new broken SQL task
POST /step       → submit fixed SQL, receive reward
GET  /state      → current environment state
POST /close      → close environment
GET  /health     → {"status": "ok"}
GET  /docs       → interactive Swagger docs
```

---

## 🧠 Inference Pipeline

```
Broken SQL
    ↓
[1] Groq LLM (llama-3.1-8b-instant)   ← primary (OpenAI-compatible)
    ↓ (on failure)
[2] FLAN-T5 (google/flan-t5-small)     ← free local fallback
    ↓
[3] Rule Engine                         ← post-processing
    ↓
Fixed SQL → submitted to env server via HTTP
```

---

## 🏗️ Architecture

```
Docker container (port 8000)
└── server/app.py       ← Pure FastAPI env server (no Gradio, no inference import)
    ├── POST /reset
    ├── POST /step
    ├── GET  /state
    ├── POST /close
    └── GET  /health

Validator (separate container)
└── inference.py        ← Connects to env server via ENV_URL over HTTP

Local demo
└── app.py              ← Gradio UI (run locally, not in Docker)
```

---

## 🔧 Environment Variables

| Variable | Required | Description |
|---|---|---|
| `HF_TOKEN` | ✅ Yes | Groq API key (set in HF Space secrets) |
| `API_BASE_URL` | No | Defaults to `https://api.groq.com/openai/v1` |
| `MODEL_NAME` | No | Defaults to `llama-3.1-8b-instant` |
| `ENV_URL` | No | Env server URL for inference.py (default: `http://localhost:8000`) |

> **Note on fallback:** The primary inference uses OpenAI-compatible API (Groq). FLAN-T5 is loaded lazily only if the LLM call fails, keeping startup fast on 2 vCPU / 8 GB hardware.