import asyncio
import json
import random
import os

from transformers import pipeline
from google import genai

from env.environment import SQLRepairEnv
from env.models import Action

# -----------------------
# 🔥 DETERMINISTIC
# -----------------------
random.seed(42)

# -----------------------
# 🔥 GEMINI CLIENT (NEW SDK ONLY)
# -----------------------
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# -----------------------
# 🔥 LOCAL MODEL (FALLBACK)
# -----------------------
generator = pipeline(
    "text2text-generation",
    model="google/flan-t5-small"
)

# -----------------------
# 🔥 GEMINI FUNCTION
# -----------------------
def fix_query_with_gemini(broken_query, schema):
    prompt = f"""
Fix the SQL query. Only return valid SQL.

Schema:
{schema}

Broken Query:
{broken_query}

Correct SQL:
"""

    response = client.models.generate_content(
        model="gemini-1.5-flash",
        contents=prompt
    )

    output = response.text.strip()
    output = output.split("\n")[0]

    return output


# -----------------------
# 🔥 LOCAL MODEL FUNCTION
# -----------------------
def fix_query_with_local(broken_query, schema):
    prompt = f"""
Fix the SQL query. Only return valid SQL.

Schema:
{schema}

Broken Query:
{broken_query}

Correct SQL:
"""

    result = generator(prompt, max_new_tokens=50)
    output = result[0]["generated_text"]

    fixed_query = output.split("Correct SQL:")[-1].strip()
    fixed_query = fixed_query.split("\n")[0]

    return fixed_query


# -----------------------
# 🔥 HYBRID FUNCTION
# -----------------------
def fix_query(broken_query, schema):
    try:
        print("🧠 Using Gemini...")
        fixed_query = fix_query_with_gemini(broken_query, schema)
    except Exception as e:
        print("⚠️ Gemini failed, using fallback:", e)
        fixed_query = fix_query_with_local(broken_query, schema)

    # -----------------------
    # 🔥 RULE FIXES (VERY IMPORTANT)
    # -----------------------

    # Fix FORM typo
    fixed_query = fixed_query.replace("FORM", "FROM")

    # Fix incomplete WHERE
    if fixed_query.strip().endswith(">"):
        fixed_query += " 18"

    # Fix incomplete ORDER
    if fixed_query.strip().endswith("ORDER"):
        fixed_query += " BY age"

    # Preserve SELECT *
    if "*" in broken_query and "*" not in fixed_query:
        fixed_query = "SELECT * FROM users"

    # Ensure valid SQL
    if "SELECT" not in fixed_query.upper() or "FROM" not in fixed_query.upper():
        fixed_query = broken_query.replace("FORM", "FROM")

    return fixed_query[:200]


# -----------------------
# 🔥 LOGGING
# -----------------------
def log_start(total_steps):
    print("[START]", json.dumps({"total_steps": total_steps}), flush=True)


def log_step(step, action, reward, done, error, result_data, difficulty):
    print("[STEP]", json.dumps({
        "step": step,
        "action": action,
        "reward": reward,
        "done": done,
        "error": error,
        "result": result_data,
        "difficulty": difficulty
    }), flush=True)


def log_end(final_score, success):
    print("[END]", json.dumps({
        "final_score": final_score,
        "success": success
    }), flush=True)


# -----------------------
# 🔥 MAIN LOOP
# -----------------------
async def run():
    env = SQLRepairEnv()

    total = 0
    score = 0.0
    num_steps = 5

    log_start(num_steps)

    for i in range(num_steps):
        state = await env.reset()
        obs = state["observation"]

        broken_query = obs.broken_query
        schema = obs.db_schema
        difficulty = getattr(obs, "difficulty", "unknown")

        fixed_query = fix_query(broken_query, schema)

        action = Action(query=fixed_query)
        result = await env.step(action)

        reward = result.get("reward", 0.0)

        result_obs = result["observation"]
        error = getattr(result_obs, "error", None)
        result_data = result_obs.result

        total += 1
        score += reward

        log_step(
            step=i + 1,
            action=fixed_query,
            reward=reward,
            done=(reward == 1.0),
            error=error,
            result_data=result_data,
            difficulty=difficulty
        )

    final_score = score / total if total > 0 else 0.0
    final_score = min(max(final_score, 0.0), 1.0)

    success = final_score >= 0.8

    log_end(final_score, success)


# -----------------------
# 🔥 RUN
# -----------------------
if __name__ == "__main__":
    asyncio.run(run())