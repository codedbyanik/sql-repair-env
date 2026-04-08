---
title: SQL Repair Environment
emoji: 🧠
colorFrom: blue
colorTo: green
sdk: docker
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

## 📥 Observation Space

```python
{
  "broken_query": str,   # The malformed SQL query
  "db_schema":    str,   # Schema: users(id INT, name TEXT, age INT)
  "difficulty":   str,   # "easy" | "medium" | "hard"
  "result":       list,  # Rows returned after step()
  "error":        str,   # SQLite error if execution failed
}
```

## 📤 Action Space

```python
{
  "query": str   # Agent's corrected SQL query
}
```

---

## 🔌 REST API

The environment exposes a full REST API on port 7860:

```bash
# Reset environment
POST /reset
→ { "observation": {...}, "reward": 0.0, "done": false }

# Submit fixed query
POST /step
Body: { "query": "SELECT name, age FROM users" }
→ { "observation": {...}, "reward": 1.0, "done": true }

# Health check
GET /health
→ { "status": "ok" }

# Episode history
GET /history
→ { "episodes": 5, "average_reward": 0.76, "history": [...] }

# Interactive API docs
GET /docs
```

---

## ⚙️ Difficulty Levels

### Easy — Single-clause keyword/syntax errors
- Missing comma: `SELECT name age FROM users`
- Typo: `SELECT * FORM users`
- Wrong keyword: `SELCET name FROM users`

### Medium — Incomplete clauses
- Truncated WHERE: `SELECT name FROM users WHERE age >`
- Missing ORDER column: `SELECT age FROM users ORDER`
- Incomplete LIMIT: `SELECT * FROM users LIMIT`

### Hard — Multi-clause compound errors
- Double truncation: `SELECT name FROM users WHERE age > AND name =`
- BETWEEN without range: `SELECT * FROM users WHERE age BETWEEN`
- HAVING without condition: `SELECT name FROM users GROUP BY age HAVING`

---

## 🧠 Inference Pipeline

```
Broken SQL
    ↓
[1] Groq LLM (llama-3.1-8b-instant)   ← primary
    ↓ (on failure)
[2] FLAN-T5 (google/flan-t5-small)     ← local fallback
    ↓
[3] Rule Engine                         ← post-processing fixes
    ↓
Fixed SQL → submitted to environment
```

---

## 🏗️ Project Structure

```
.
├── app.py                  # FastAPI + Gradio server (port 7860)
├── inference.py            # LLM + fallback + rule engine
├── openenv.yaml            # OpenEnv spec
├── Dockerfile
├── requirements.txt
└── env/
    ├── environment.py      # SQLRepairEnv (reset, step, state)
    ├── grader.py           # Reward scoring logic
    ├── models.py           # Observation + Action pydantic models
    └── tasks/
        ├── easy.py         # 7 easy tasks
        ├── medium.py       # 7 medium tasks
        └── hard.py         # 7 hard tasks
```

---

## 🔧 Environment Variables

| Variable | Required | Description |
|---|---|---|
| `HF_TOKEN` | ✅ Yes | Groq API key (set in HF Space secrets) |
| `API_BASE_URL` | No | Defaults to `https://api.groq.com/openai/v1` |
| `MODEL_NAME` | No | Defaults to `llama-3.1-8b-instant` |