---
title: SQL Repair Environment
emoji: 🤖
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
---

# 🧠 AI SQL Repair Environment

An **OpenEnv-compliant** reinforcement learning environment where an AI agent repairs broken SQL queries and is scored on correctness.

---

## 🚀 Overview

| Property | Value |
|---|---|
| Environment Type | Single-agent |
| Reward Range | 0.05 → 0.95 |
| Difficulty Levels | Easy, Medium, Hard |
| Execution Backend | SQLite (in-memory) |
| Inference | Groq LLM (llama-3.1-8b) + Lookup Table fallback |
| Framework | OpenEnv + FastAPI + Gradio |

---

## 🎮 How It Works

```
1. Agent receives:  broken SQL query + DB schema + difficulty
2. Agent produces:  corrected SQL query
3. Environment:     executes SQL in SQLite sandbox
4. Reward issued:   based on correctness (0.05 → 0.95)
```

---

## 🏆 Reward Scale

| Score | Condition |
|---|---|
| **0.95** | Exact normalized query match |
| **0.80** | Output rows match expected result |
| **0.30** | Valid SELECT structure, wrong output |
| **0.05** | Syntax error or no SELECT |

---

## 🔌 REST API

The environment server runs on **port 7860**:

```bash
POST /reset      → get new broken SQL task
POST /step       → submit fixed SQL, receive reward
POST /grader     → score a query directly (Task Validation)
GET  /state      → current environment state
GET  /health     → {"status": "ok"}
GET  /docs       → interactive Swagger docs
```

---

## 🧠 Inference Pipeline

```
Broken SQL
    ↓
[1] Groq LLM via OpenAI-compatible proxy  ← primary (API_KEY injected by validator)
    ↓
[2] Lookup Table                           ← snaps to exact correct answer
    ↓
Fixed SQL → submitted directly via SQLRepairEnv
```

---

## 🏗️ Architecture

```
Docker container (port 7860)
└── server/app.py       ← FastAPI + Gradio UI
    ├── POST /reset
    ├── POST /step
    ├── POST /grader
    ├── GET  /state
    └── GET  /health

inference.py            ← LLM agent (run by validator)
env/environment.py      ← SQLRepairEnv core logic
env/grader.py           ← grade class with .grade() method
openenv.yaml            ← OpenEnv spec
```

---

## 🔧 Environment Variables

| Variable | Required | Description |
|---|---|---|
| `API_KEY` | ✅ Yes | Groq API key (injected by validator) |
| `API_BASE_URL` | No | Defaults to `https://api.groq.com/openai/v1` |
| `MODEL_NAME` | No | Defaults to `llama-3.1-8b-instant` |
