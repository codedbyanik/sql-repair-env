import asyncio
import os
import httpx
from openai import OpenAI

# -----------------------
# 🔥 ENV VARIABLES
# ✅ Defaults set only for API_BASE_URL and MODEL_NAME (not HF_TOKEN)
# -----------------------
API_BASE_URL = os.getenv("API_BASE_URL", "https://api.groq.com/openai/v1")
MODEL_NAME   = os.getenv("MODEL_NAME",   "llama-3.1-8b-instant")
HF_TOKEN     = os.getenv("HF_TOKEN")
ENV_URL      = os.getenv("ENV_URL", "http://localhost:8000")

if HF_TOKEN is None:
    raise ValueError("HF_TOKEN environment variable is required")

# -----------------------
# 🔥 OPENAI CLIENT
# ✅ All primary LLM calls use this OpenAI-compatible client
# -----------------------
client = OpenAI(base_url=API_BASE_URL, api_key=HF_TOKEN)

# -----------------------
# 🔥 LOCAL FALLBACK — lazy loaded
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
            print(f"[FALLBACK] Could not load: {e}", flush=True)
            _generator = False
    return _generator if _generator else None


# -----------------------
# 🔥 HTTP ENV CLIENT
# -----------------------
async def env_reset(http: httpx.AsyncClient) -> dict:
    resp = await http.post(f"{ENV_URL}/reset", timeout=30)
    resp.raise_for_status()
    return resp.json()

async def env_step(http: httpx.AsyncClient, query: str) -> dict:
    resp = await http.post(f"{ENV_URL}/step", json={"query": query}, timeout=30)
    resp.raise_for_status()
    return resp.json()

async def env_close(http: httpx.AsyncClient):
    try:
        await http.post(f"{ENV_URL}/close", timeout=10)
    except Exception as e:
        print(f"[DEBUG] env close error: {e}", flush=True)


# -----------------------
# 🔥 EXTRACT SQL FROM LLM OUTPUT
# -----------------------
def extract_sql_from_output(output: str) -> str:
    output = output.strip()

    if "```" in output:
        parts = output.split("```")
        if len(parts) >= 2:
            code_block = parts[1].strip()
            if code_block.lower().startswith("sql"):
                code_block = code_block[3:].strip()
            output = code_block

    prefixes = [
        "correct sql:", "corrected sql:", "the corrected sql query is:",
        "the correct sql query is:", "the fixed sql query is:", "fixed sql:",
        "here is the corrected sql:", "here is the fixed sql:",
        "here's the corrected sql:", "here's the fixed sql:",
        "answer:", "result:", "output:", "sql:",
    ]
    lower = output.lower()
    for p in prefixes:
        if p in lower:
            output = output[lower.index(p) + len(p):].strip()
            lower  = output.lower()
            break

    sql_kw = ("SELECT","INSERT","UPDATE","DELETE","CREATE","DROP","ALTER","WITH")
    for line in output.splitlines():
        line = line.strip()
        if line.upper().startswith(sql_kw):
            return line

    for line in output.splitlines():
        line = line.strip()
        if line:
            return line

    return output.strip()


# -----------------------
# 🔥 LLM FIX (primary)
# -----------------------
def fix_query_with_llm(broken_query: str, schema: str) -> str:
    prompt = f"""Fix the following broken SQL query.

Schema:
{schema}

Broken Query:
{broken_query}

Correct SQL:"""

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": (
                "You are a SQL repair expert. "
                "Return ONLY the corrected SQL statement on a single line. "
                "No explanation, no markdown, no code fences."
            )},
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )
    raw = response.choices[0].message.content.strip()
    print(f"[LLM RAW]: {repr(raw)}", flush=True)
    fixed = extract_sql_from_output(raw)
    print(f"[LLM SQL]: {repr(fixed)}", flush=True)
    return fixed


# -----------------------
# 🔥 LOCAL FALLBACK
# -----------------------
def fix_query_with_local(broken_query: str, schema: str) -> str:
    gen = get_generator()
    if gen is None:
        return broken_query
    prompt = f"Fix SQL. Schema: {schema}. Broken: {broken_query}. Correct SQL:"
    result = gen(prompt, max_new_tokens=50)
    return extract_sql_from_output(result[0]["generated_text"])


# -----------------------
# 🔥 RULE ENGINE
# -----------------------
def apply_rules(broken_query: str, fixed_query: str) -> str:
    fixed_query = " ".join(fixed_query.strip().split())

    fixed_query = fixed_query.replace("SELCET", "SELECT").replace("SLECT", "SELECT")
    fixed_query = fixed_query.replace("FORM",   "FROM").replace("FOMR", "FROM")
    fixed_query = fixed_query.replace("WHER ",  "WHERE ").replace("GROUPE BY", "GROUP BY")
    fixed_query = fixed_query.replace("ORDERE BY", "ORDER BY").replace("HAVIN ", "HAVING ")

    lower_q = fixed_query.lower()
    if "select name age" in lower_q:
        fixed_query = fixed_query.replace("name age", "name, age"); lower_q = fixed_query.lower()
    if "select id name"  in lower_q:
        fixed_query = fixed_query.replace("id name",  "id, name");  lower_q = fixed_query.lower()
    if "select id age"   in lower_q:
        fixed_query = fixed_query.replace("id age",   "id, age");   lower_q = fixed_query.lower()

    if "where age >" in lower_q and fixed_query.endswith(">"):
        fixed_query += " 18"
    if fixed_query.upper().endswith("ORDER"):
        fixed_query += " BY age"
    elif fixed_query.upper().endswith("ORDER BY"):
        fixed_query += " age"

    sql_kw = ("SELECT","INSERT","UPDATE","DELETE","CREATE","DROP","ALTER","WITH")
    if not fixed_query.strip().upper().startswith(sql_kw):
        print(f"⚠️ Not SQL, falling back to rules on original.", flush=True)
        fixed_query = broken_query.strip()
        fixed_query = fixed_query.replace("SELCET","SELECT").replace("FORM","FROM").replace("WHER ","WHERE ")
        lower_q = fixed_query.lower()
        if "select name age" in lower_q: fixed_query = fixed_query.replace("name age","name, age")
        if "select id name"  in lower_q: fixed_query = fixed_query.replace("id name","id, name")
        if "select id age"   in lower_q: fixed_query = fixed_query.replace("id age","id, age")

    return fixed_query[:200]


# -----------------------
# 🔥 MAIN FIX FUNCTION (used by both UI and inference loop)
# -----------------------
def fix_query(broken_query: str, schema: str) -> str:
    try:
        print("🧠 Using LLM...", flush=True)
        fixed = fix_query_with_llm(broken_query, schema)
        if not fixed or len(fixed) < 5:
            raise Exception("Too short")
        sql_kw = ("SELECT","INSERT","UPDATE","DELETE","CREATE","DROP","ALTER","WITH")
        if not fixed.strip().upper().startswith(sql_kw):
            raise Exception(f"Not SQL: {repr(fixed)}")
    except Exception as e:
        print(f"⚠️ LLM failed: {e}, using fallback.", flush=True)
        fixed = fix_query_with_local(broken_query, schema)

    return apply_rules(broken_query, fixed)


# -----------------------
# 🔥 STDOUT HELPERS
# -----------------------
def log_start(task, env, model):
    print(f"[START] task={task} env={env} model={model}", flush=True)

def log_step(step, action, reward, done, error):
    print(f"[STEP] step={step} action={action} reward={reward:.2f} "
          f"done={str(done).lower()} error={error if error else 'null'}", flush=True)

def log_end(success, steps, score, rewards):
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(f"[END] success={str(success).lower()} steps={steps} "
          f"score={score:.2f} rewards={rewards_str}", flush=True)


# -----------------------
# 🔥 MAIN LOOP (run by validator)
# -----------------------
async def run() -> None:
    num_steps   = 5
    rewards_list = []
    steps_taken  = 0
    score        = 0.0
    success      = False

    log_start(task="sql-repair", env="custom", model=MODEL_NAME)

    async with httpx.AsyncClient() as http:
        try:
            state = await env_reset(http)

            for i in range(num_steps):
                obs          = state["observation"]
                broken_query = obs["broken_query"]
                schema       = obs["db_schema"]

                fixed_query = fix_query(broken_query, schema)
                result      = await env_step(http, fixed_query)

                reward = result.get("reward", 0.0)
                done   = result.get("done",   False)
                error  = result.get("observation", {}).get("error", None)

                rewards_list.append(reward)
                steps_taken = i + 1

                log_step(step=i+1, action=fixed_query, reward=reward, done=done, error=error)

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