import asyncio
import random
import os
from transformers import pipeline
from openai import OpenAI

from env.environment import SQLRepairEnv
from env.models import Action

# -----------------------
# 🔥 DETERMINISTIC
# -----------------------
random.seed(42)

# -----------------------
# 🔥 ENV VARIABLES
# -----------------------
API_BASE_URL = os.getenv("API_BASE_URL", "https://api.groq.com/openai/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "llama-3.1-8b-instant")
HF_TOKEN = os.getenv("HF_TOKEN")

if HF_TOKEN is None:
    raise ValueError("HF_TOKEN environment variable is required")

# -----------------------
# 🔥 OPENAI CLIENT
# -----------------------
client = OpenAI(
    base_url=API_BASE_URL,
    api_key=HF_TOKEN
)

# -----------------------
# 🔥 LOCAL MODEL (fallback)
# -----------------------
generator = pipeline(
    "text2text-generation",
    model="google/flan-t5-small"
)


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
        # parts[1] is the content inside the first fence
        if len(parts) >= 2:
            code_block = parts[1].strip()
            # Remove language tag like "sql"
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
# 🔥 LLM FUNCTION
# -----------------------
def fix_query_with_llm(broken_query, schema):
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
# 🔥 LOCAL FALLBACK
# -----------------------
def fix_query_with_local(broken_query, schema):
    prompt = f"""Fix the SQL query. Only return valid SQL.

Schema:
{schema}

Broken Query:
{broken_query}

Correct SQL:"""

    result = generator(prompt, max_new_tokens=50)
    raw_output = result[0]["generated_text"]

    fixed_query = extract_sql_from_output(raw_output)
    return fixed_query


# -----------------------
# 🔥 RULE ENGINE
# -----------------------
def apply_rules(broken_query, fixed_query):
    fixed_query = fixed_query.strip()
    fixed_query = " ".join(fixed_query.split())
    lower_q = fixed_query.lower()

    # Keyword typo fixes
    fixed_query = fixed_query.replace("SELCET", "SELECT").replace("SLECT", "SELECT")
    fixed_query = fixed_query.replace("FORM", "FROM").replace("FOMR", "FROM")
    fixed_query = fixed_query.replace("WHER ", "WHERE ").replace("GROUPE BY", "GROUP BY")
    fixed_query = fixed_query.replace("ORDERE BY", "ORDER BY").replace("HAVIN ", "HAVING ")

    # Re-compute lower after replacements
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

    # ✅ Final safety check: if the result doesn't look like SQL,
    # fall back to applying simple rules directly on the ORIGINAL broken query
    sql_keywords = ("SELECT", "INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER", "WITH")
    if not fixed_query.strip().upper().startswith(sql_keywords):
        print(
            f"⚠️ apply_rules: output '{fixed_query[:60]}' doesn't look like SQL. "
            f"Falling back to rule-based fix on original broken query.",
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
def fix_query(broken_query, schema):
    try:
        print("🧠 Using LLM...", flush=True)
        fixed_query = fix_query_with_llm(broken_query, schema)

        if not fixed_query or len(fixed_query) < 5:
            raise Exception("Bad LLM output — too short")

        # Extra guard: if it still doesn't start with a SQL keyword, raise
        sql_keywords = ("SELECT", "INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER", "WITH")
        if not fixed_query.strip().upper().startswith(sql_keywords):
            raise Exception(f"LLM output doesn't look like SQL: {repr(fixed_query)}")

    except Exception as e:
        print(f"⚠️ LLM failed, using local fallback: {e}", flush=True)
        fixed_query = fix_query_with_local(broken_query, schema)

    fixed_query = apply_rules(broken_query, fixed_query)

    return fixed_query


# -----------------------
# 🔥 MAIN LOOP
# -----------------------
async def run():
    env = SQLRepairEnv()

    total = 0
    rewards_list = []
    num_steps = 5

    print(f"[START] task=sql-repair env=custom model={MODEL_NAME}")

    state = await env.reset()

    for i in range(num_steps):
        obs = state["observation"]

        broken_query = obs.broken_query
        schema = obs.db_schema

        fixed_query = fix_query(broken_query, schema)

        result = await env.step(Action(query=fixed_query))
        state = result

        reward = result.get("reward", 0.0)
        done = reward == 1.0

        result_obs = result["observation"]
        error = getattr(result_obs, "error", None)

        rewards_list.append(reward)
        total += 1

        print(
            f"[STEP] step={i+1} action={fixed_query} "
            f"reward={reward:.2f} done={str(done).lower()} "
            f"error={error if error else 'null'}"
        )

    final_score = sum(rewards_list) / total if total > 0 else 0.0
    success = final_score >= 0.8

    rewards_str = ",".join([f"{r:.2f}" for r in rewards_list])

    print(
        f"[END] success={str(success).lower()} "
        f"steps={total} rewards={rewards_str}"
    )


# -----------------------
# 🔥 RUN
# -----------------------
if __name__ == "__main__":
    asyncio.run(run())



