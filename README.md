---
title: SQL Repair Environment
emoji: 🤖
colorFrom: blue
colorTo: green
sdk: docker
pinned: false
---

# 🎮 AI SQL Repair Environment

An AI-powered training environment where an agent repairs incorrect SQL queries and gets scored based on correctness.

---

# 🚀 Overview

This project simulates a **real-world SQL debugging task**:

- Given a **broken SQL query**
- AI fixes the query using a language model
- Query is executed on a database
- A **reward score (0.0 → 1.0)** is assigned

---

# 🧠 Features

- ✅ OpenEnv compliant (`step()`, `reset()`, `state()`)
- ✅ Multiple difficulty levels (Easy → Medium → Hard)
- ✅ Reward-based evaluation system
- ✅ SQLite execution environment
- ✅ AI-powered query correction (FLAN-T5)
- ✅ Deployable on Hugging Face Spaces
- ✅ Interactive UI using Gradio

---

# 🏗️ Environment Design

## 📥 Observation Space

```python
broken_query: str
db_schema: str
difficulty: str
result: Optional[Any]
error: Optional[str]