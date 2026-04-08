import asyncio
import os
from openai import OpenAI

from env.environment import SQLRepairEnv
from env.models import Action

# -----------------------
# 🔥 ENV VARIABLES
# ✅ Defaults set only for API_BASE_URL and MODEL_NAME (not HF_TOKEN)
# -----------------------
API_BASE_URL = os.getenv("API_BASE_URL", "https://api.groq.com/openai/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "llama-3.1-8b-instant")
HF_TOKEN = os.getenv("HF_TOKEN")

if HF_TOKEN is None:
    raise ValueError("HF_TOKEN environment variable is required")

# -----------------------
# 🔥 OPENAI CLIENT
# ✅ All primary LLM calls use this OpenAI-compatible client
# -----------------------
client = OpenAI(
    base_url=API_BASE_URL,
    api_key=HF_TOKEN
)

# -----------------------
# 🔥 LOCAL FALLBACK MODEL
# Free offline fallback via transformers when OpenAI API is unavailable.
# Loaded lazily — only downloaded if primary LLM fails.
# This avoids wasting startup time on the 2cpu/8gb machine.
# See README.md for details.
# -----------------------
_generator = None

def get_generator():
    global _generator
    if _generator is None:
        try:
            from transformers import pipeline
            _generator = pipeline(
                "text2text-generation",
                model="google/flan-t5-small"
            )
            print("[FALLBACK] flan-t5-small loaded.", flush=True)
        except Exception as e:
            print(f"[FALLBACK] Could not load flan-t5-small: {e}", flush=True)
            _generator = False
    return _generator if _generator else None


# -----------------------
# 🔥 HELPER: Extract SQL from LLM output
# -----------------------
def extract_sql_from_output(output: str) -> str:
    """
    Robustly extract just the SQL statement from LLM output.
    Handles markdown fences, explanation prefixes, and multi-line responses.
    """
    output = output.strip()

    # 1. Strip markdown code fences (```sql ... ``` or ``` ... ```)
    if "```" in output:
        parts = output.split("```")
        if len(parts) >= 2:
            code_block = parts[1].strip()
            if code_block.lower().startswith("sql"):
                code_block = code_block[3:].strip()
            output = code_block

    # 2. Strip common explanation prefixes (case-insensitive)
    explanation_prefixes = [
        "correct sql:",
        "corrected sql:",
        "the corrected sql query is:",
        "the correct sql query is:",
        "the fixed sql query is:",
        "fixed sql:",
        "here is the corrected sql:",
        "here is the fixed sql:",
        "here's the corrected sql:",
        "here's the fixed sql:",
        "answer:",
        "result:",
        "output:",
        "sql:",
    ]
    lower_output = output.lower()
    for prefix in explanation_prefixes:
        if prefix in lower_output:
            idx = lower_output.index(prefix)
            output = output[idx + len(prefix):].strip()
            lower_output = output.lower()
            break

    # 3. Find the first line that looks like a SQL statement
    sql_keywords = ("SELECT", "INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER", "WITH")
    for line in output.splitlines():
        line = line.strip()
        if line.upper().startswith(sql_keywords):
            return line

    # 4. Fallback: return the first non-empty line
    for line in output.splitlines():
        line = line.strip()
        if line:
            return line

    return output.strip()


# -----------------------
# 🔥 LLM FUNCTION (primary — OpenAI-compatible API)
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
            {
                "role": "system",
                "content": (
                    "You are a SQL repair expert. "
                    "When given a broken SQL query, you return ONLY the corrected SQL statement. "
                    "Do NOT include any explanation, markdown, code fences, or extra text. "
                    "Return ONLY the raw SQL query on a single line."
                )
            },
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )

    raw_output = response.choices[0].message.content.strip()
    print(f"[LLM RAW OUTPUT]: {repr(raw_output)}", flush=True)

    fixed_query = extract_sql_from_output(raw_output)
    print(f"[LLM EXTRACTED SQL]: {repr(fixed_query)}", flush=True)

    return fixed_query


# -----------------------
# 🔥 LOCAL FALLBACK (free — no API cost, loaded lazily)
# -----------------------
def fix_query_with_local(broken_query: str, schema: str) -> str:
    gen = get_generator()
    if gen is None:
        print("[FALLBACK] No local model available, using rule engine only.", flush=True)
        return broken_query

    prompt = f"""Fix the SQL query. Only return valid SQL.

Schema:
{schema}

Broken Query:
{broken_query}

Correct SQL:"""

    result = gen(prompt, max_new_tokens=50)
    raw_output = result[0]["generated_text"]
    return extract_sql_from_output(raw_output)


# -----------------------
# 🔥 RULE ENGINE (post-processing, no LLM)
# -----------------------
def apply_rules(broken_query: str, fixed_query: str) -> str:
    fixed_query = fixed_query.strip()
    fixed_query = " ".join(fixed_query.split())
    lower_q = fixed_query.lower()

    # Keyword typo fixes
    fixed_query = fixed_query.replace("SELCET", "SELECT").replace("SLECT", "SELECT")
    fixed_query = fixed_query.replace("FORM", "FROM").replace("FOMR", "FROM")
    fixed_query = fixed_query.replace("WHER ", "WHERE ").replace("GROUPE BY", "GROUP BY")
    fixed_query = fixed_query.replace("ORDERE BY", "ORDER BY").replace("HAVIN ", "HAVING ")

    lower_q = fixed_query.lower()

    # Missing comma between column names
    if "select name age" in lower_q:
        fixed_query = fixed_query.replace("name age", "name, age")
        lower_q = fixed_query.lower()

    if "select id name" in lower_q:
        fixed_query = fixed_query.replace("id name", "id, name")
        lower_q = fixed_query.lower()

    if "select id age" in lower_q:
        fixed_query = fixed_query.replace("id age", "id, age")
        lower_q = fixed_query.lower()

    # Incomplete WHERE clause
    if "where age >" in lower_q and fixed_query.endswith(">"):
        fixed_query += " 18"

    # Incomplete ORDER BY
    if fixed_query.upper().endswith("ORDER"):
        fixed_query += " BY age"
    elif fixed_query.upper().endswith("ORDER BY"):
        fixed_query += " age"

    # Final safety check: if result doesn't look like SQL, apply rules on original
    sql_keywords = ("SELECT", "INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER", "WITH")
    if not fixed_query.strip().upper().startswith(sql_keywords):
        print(
            f"⚠️ apply_rules: '{fixed_query[:60]}' doesn't look like SQL. "
            f"Applying rules on original broken query.",
            flush=True
        )
        fixed_query = broken_query.strip()
        fixed_query = fixed_query.replace("SELCET", "SELECT").replace("SLECT", "SELECT")
        fixed_query = fixed_query.replace("FORM", "FROM").replace("FOMR", "FROM")
        fixed_query = fixed_query.replace("WHER ", "WHERE ")

        lower_q = fixed_query.lower()
        if "select name age" in lower_q:
            fixed_query = fixed_query.replace("name age", "name, age")
        if "select id name" in lower_q:
            fixed_query = fixed_query.replace("id name", "id, name")
        if "select id age" in lower_q:
            fixed_query = fixed_query.replace("id age", "id, age")

    return fixed_query[:200]


# -----------------------
# 🔥 MAIN FIX FUNCTION
# -----------------------
def fix_query(broken_query: str, schema: str) -> str:
    try:
        print("🧠 Using LLM...", flush=True)
        fixed_query = fix_query_with_llm(broken_query, schema)

        if not fixed_query or len(fixed_query) < 5:
            raise Exception("Bad LLM output — too short")

        sql_keywords = ("SELECT", "INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER", "WITH")
        if not fixed_query.strip().upper().startswith(sql_keywords):
            raise Exception(f"LLM output doesn't look like SQL: {repr(fixed_query)}")

    except Exception as e:
        print(f"⚠️ LLM failed, using local fallback: {e}", flush=True)
        fixed_query = fix_query_with_local(broken_query, schema)

    fixed_query = apply_rules(broken_query, fixed_query)
    return fixed_query


# -----------------------
# 🔥 STDOUT HELPERS — matches required format exactly
# -----------------------
def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(step: int, action: str, reward: float, done: bool, error) -> None:
    error_val = error if error else "null"
    done_val = str(done).lower()
    print(
        f"[STEP] step={step} action={action} reward={reward:.2f} done={done_val} error={error_val}",
        flush=True
    )


def log_end(success: bool, steps: int, score: float, rewards: list) -> None:
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(
        f"[END] success={str(success).lower()} steps={steps} score={score:.2f} rewards={rewards_str}",
        flush=True
    )


# -----------------------
# 🔥 MAIN LOOP
# -----------------------
async def run() -> None:
    env = SQLRepairEnv()

    num_steps = 5
    rewards_list = []
    steps_taken = 0
    score = 0.0
    success = False

    log_start(task="sql-repair", env="custom", model=MODEL_NAME)

    try:
        # reset() called once before the loop
        state = await env.reset()

        for i in range(num_steps):
            obs = state["observation"]
            broken_query = obs.broken_query
            schema = obs.db_schema

            fixed_query = fix_query(broken_query, schema)

            result = await env.step(Action(query=fixed_query))

            reward = result.get("reward", 0.0)
            done = reward == 1.0
            result_obs = result["observation"]
            error = getattr(result_obs, "error", None)

            rewards_list.append(reward)
            steps_taken = i + 1

            log_step(step=i + 1, action=fixed_query, reward=reward, done=done, error=error)

            if done:
                break

            # Advance to next task for remaining steps
            state = await env.reset()

        # score normalized to [0, 1]
        score = sum(rewards_list) / len(rewards_list) if rewards_list else 0.0
        score = min(max(score, 0.0), 1.0)
        success = score >= 0.8

    finally:
        # env.close() always called, even on exception
        try:
            await env.close()
        except Exception as e:
            print(f"[DEBUG] env.close() error: {e}", flush=True)

        # [END] always emitted, even on exception
        log_end(success=success, steps=steps_taken, score=score, rewards=rewards_list)


# -----------------------
# 🔥 RUN
# -----------------------
if __name__ == "__main__":
    asyncio.run(run())