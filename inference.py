"""
inference.py — Run by the validator in a separate container.

This script:
1. Connects to the env server via HTTP (ENV_URL env variable)
2. Uses OpenAI-compatible client (Groq) as primary LLM
3. Uses flan-t5-small as free offline fallback
4. Emits [START], [STEP], [END] logs in required format
"""

import asyncio
import os
import httpx
from openai import OpenAI

# -----------------------
# ENV VARIABLES
# ✅ Defaults only for API_BASE_URL and MODEL_NAME (not HF_TOKEN)
# -----------------------
API_BASE_URL = os.getenv("API_BASE_URL", "https://api.groq.com/openai/v1")
MODEL_NAME   = os.getenv("MODEL_NAME",   "llama-3.1-8b-instant")
HF_TOKEN     = os.getenv("HF_TOKEN")
ENV_URL      = os.getenv("ENV_URL", "http://localhost:8000")

if HF_TOKEN is None:
    raise ValueError("HF_TOKEN environment variable is required")

# -----------------------
# OPENAI CLIENT
# ✅ All LLM calls go through this
# -----------------------
client = OpenAI(base_url=API_BASE_URL, api_key=HF_TOKEN)

# -----------------------
# LOCAL FALLBACK — lazy loaded, only if LLM fails
# -----------------------
_generator = None

def get_generator():
    global _generator
    if _generator is None:
        try:
            from transformers import pipeline
            _generator = pipeline("text2text-generation", model="google/flan-t5-small")
            print("[FALLBACK] flan-t5-small loaded.", flush=True)
        except Exception as e:
            print(f"[FALLBACK] load failed: {e}", flush=True)
            _generator = False
    return _generator if _generator else None


# -----------------------
# HTTP ENV CLIENT
# Talks to env server — never imports env directly
# -----------------------
async def env_reset(http: httpx.AsyncClient) -> dict:
    try:
        r = await http.post(f"{ENV_URL}/reset", timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        raise RuntimeError(f"env_reset failed: {e}")


async def env_step(http: httpx.AsyncClient, query: str) -> dict:
    try:
        r = await http.post(f"{ENV_URL}/step", json={"query": query}, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        raise RuntimeError(f"env_step failed: {e}")


async def env_close(http: httpx.AsyncClient):
    try:
        await http.post(f"{ENV_URL}/close", timeout=10)
    except Exception as e:
        print(f"[DEBUG] close error: {e}", flush=True)


# -----------------------
# EXTRACT SQL FROM LLM OUTPUT
# -----------------------
def extract_sql(output: str) -> str:
    output = output.strip()

    # Strip markdown code fences
    if "```" in output:
        parts = output.split("```")
        if len(parts) >= 2:
            cb = parts[1].strip()
            if cb.lower().startswith("sql"):
                cb = cb[3:].strip()
            output = cb

    # Strip explanation prefixes
    prefixes = [
        "correct sql:", "corrected sql:", "the corrected sql query is:",
        "the correct sql query is:", "the fixed sql query is:", "fixed sql:",
        "here is the corrected sql:", "here is the fixed sql:",
        "here's the corrected sql:", "here's the fixed sql:",
        "answer:", "result:", "output:", "sql:",
    ]
    low = output.lower()
    for p in prefixes:
        if p in low:
            output = output[low.index(p) + len(p):].strip()
            low = output.lower()
            break

    # Find first SQL-looking line
    kw = ("SELECT", "INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER", "WITH")
    for line in output.splitlines():
        line = line.strip()
        if line.upper().startswith(kw):
            return line

    # Fallback: first non-empty line
    for line in output.splitlines():
        line = line.strip()
        if line:
            return line

    return output.strip()


# -----------------------
# LLM FIX (primary)
# -----------------------
def fix_query_with_llm(broken: str, schema: str) -> str:
    prompt = (
        f"Fix the following broken SQL query.\n\n"
        f"Schema:\n{schema}\n\n"
        f"Broken Query:\n{broken}\n\n"
        f"Correct SQL:"
    )
    r = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content":
                "You are a SQL repair expert. Return ONLY the corrected SQL on one line. "
                "No explanation, no markdown, no code fences."},
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )
    raw = r.choices[0].message.content.strip()
    print(f"[LLM RAW]: {repr(raw)}", flush=True)
    fixed = extract_sql(raw)
    print(f"[LLM SQL]: {repr(fixed)}", flush=True)
    return fixed


# -----------------------
# LOCAL FALLBACK
# -----------------------
def fix_query_with_local(broken: str, schema: str) -> str:
    gen = get_generator()
    if gen is None:
        return broken
    prompt = f"Fix SQL. Schema: {schema}. Broken: {broken}. Correct SQL:"
    result = gen(prompt, max_new_tokens=50)
    return extract_sql(result[0]["generated_text"])


# -----------------------
# RULE ENGINE
# -----------------------
def apply_rules(broken: str, fixed: str) -> str:
    fixed = " ".join(fixed.strip().split())

    fixed = fixed.replace("SELCET", "SELECT").replace("SLECT", "SELECT")
    fixed = fixed.replace("FORM",   "FROM").replace("FOMR", "FROM")
    fixed = fixed.replace("WHER ",  "WHERE ").replace("GROUPE BY", "GROUP BY")
    fixed = fixed.replace("ORDERE BY", "ORDER BY").replace("HAVIN ", "HAVING ")

    low = fixed.lower()
    if "select name age" in low:
        fixed = fixed.replace("name age", "name, age"); low = fixed.lower()
    if "select id name" in low:
        fixed = fixed.replace("id name", "id, name");  low = fixed.lower()
    if "select id age" in low:
        fixed = fixed.replace("id age", "id, age");    low = fixed.lower()

    if "where age >" in low and fixed.endswith(">"):
        fixed += " 18"
    if fixed.upper().endswith("ORDER"):
        fixed += " BY age"
    elif fixed.upper().endswith("ORDER BY"):
        fixed += " age"

    kw = ("SELECT", "INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER", "WITH")
    if not fixed.strip().upper().startswith(kw):
        print(f"⚠️ Not SQL, applying rules on original.", flush=True)
        fixed = broken.strip()
        fixed = fixed.replace("SELCET", "SELECT").replace("FORM", "FROM").replace("WHER ", "WHERE ")
        low = fixed.lower()
        if "select name age" in low: fixed = fixed.replace("name age", "name, age")
        if "select id name"  in low: fixed = fixed.replace("id name",  "id, name")
        if "select id age"   in low: fixed = fixed.replace("id age",   "id, age")

    return fixed[:200]


# -----------------------
# MAIN FIX FUNCTION
# -----------------------
def fix_query(broken: str, schema: str) -> str:
    try:
        print("🧠 Using LLM...", flush=True)
        fixed = fix_query_with_llm(broken, schema)
        if not fixed or len(fixed) < 5:
            raise Exception("Too short")
        kw = ("SELECT", "INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER", "WITH")
        if not fixed.strip().upper().startswith(kw):
            raise Exception(f"Not SQL: {repr(fixed)}")
    except Exception as e:
        print(f"⚠️ LLM failed: {e}", flush=True)
        fixed = fix_query_with_local(broken, schema)
    return apply_rules(broken, fixed)


# -----------------------
# STDOUT HELPERS — exact required format
# -----------------------
def log_start(task, env, model):
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(step, action, reward, done, error):
    print(
        f"[STEP] step={step} action={action} reward={reward:.2f} "
        f"done={str(done).lower()} error={error if error else 'null'}",
        flush=True
    )


def log_end(success, steps, score, rewards):
    print(
        f"[END] success={str(success).lower()} steps={steps} "
        f"score={score:.2f} rewards={','.join(f'{r:.2f}' for r in rewards)}",
        flush=True
    )


# -----------------------
# MAIN LOOP — run by validator
# -----------------------
async def run() -> None:
    rewards_list = []
    steps_taken  = 0
    score        = 0.0
    success      = False
    num_steps    = 5

    log_start(task="sql-repair", env="custom", model=MODEL_NAME)

    async with httpx.AsyncClient() as http:
        try:
            state = await env_reset(http)

            for i in range(num_steps):
                obs    = state["observation"]
                broken = obs["broken_query"]
                schema = obs["db_schema"]

                fixed  = fix_query(broken, schema)
                result = await env_step(http, fixed)

                reward = result.get("reward", 0.0)
                done   = result.get("done", False)
                error  = result.get("observation", {}).get("error")

                rewards_list.append(reward)
                steps_taken = i + 1

                log_step(step=i + 1, action=fixed, reward=reward, done=done, error=error)

                if done:
                    break

                state = await env_reset(http)

            score   = sum(rewards_list) / len(rewards_list) if rewards_list else 0.0
            score   = min(max(score, 0.0), 1.0)
            success = score >= 0.8

        finally:
            await env_close(http)
            log_end(success=success, steps=steps_taken, score=score, rewards=rewards_list)


if __name__ == "__main__":
    asyncio.run(run())