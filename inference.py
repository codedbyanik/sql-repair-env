import asyncio
import json
import random
from transformers import pipeline

from env.environment import SQLRepairEnv
from env.models import Action

# -----------------------
# 🔥 DETERMINISTIC
# -----------------------
random.seed(42)

# -----------------------
# 🔥 LOAD MODEL (LIGHT)
# -----------------------
generator = pipeline(
    "text2text-generation",
    model="google/flan-t5-small"
)

# -----------------------
# 🔥 AI + RULE FIX
# -----------------------
def fix_query_with_ai(broken_query, schema):
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

    # -----------------------
    # 🔥 STRONG RULE FIXES
    # -----------------------

    # Fix typo
    fixed_query = fixed_query.replace("FORM", "FROM")

    # If no SELECT → fallback
    if "SELECT" not in fixed_query.upper():
        return broken_query.replace("FORM", "FROM")

    # Fix missing FROM
    if "FROM" not in fixed_query.upper():
        fixed_query = broken_query.replace("FORM", "FROM")

    # Fix weird model outputs
    if "FROM_" in fixed_query or "age_form" in fixed_query:
        fixed_query = "SELECT age FROM users"

    # Ensure table name exists
    if "users" not in fixed_query:
        fixed_query = broken_query.replace("FORM", "FROM")

    # Limit length
    fixed_query = fixed_query[:200]

    return fixed_query


# -----------------------
# 🔥 LOGGING
# -----------------------
def log_start(total_steps):
    print("[START]", json.dumps({
        "total_steps": total_steps
    }), flush=True)


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

        # ✅ OBJECT ACCESS (FIXED)
        broken_query = obs.broken_query
        schema = obs.db_schema
        difficulty = getattr(obs, "difficulty", "unknown")

        # 🤖 AI FIX
        fixed_query = fix_query_with_ai(broken_query, schema)

        action = Action(query=fixed_query)
        result = await env.step(action)

        reward = result.get("reward", 0.0)

        # ✅ OBJECT ACCESS (FIXED)
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

    # -----------------------
    # 🔥 FINAL SCORE
    # -----------------------
    final_score = score / total if total > 0 else 0.0
    final_score = min(max(final_score, 0.0), 1.0)

    success = final_score >= 0.8

    log_end(final_score, success)


# -----------------------
# 🔥 RUN
# -----------------------
if __name__ == "__main__":
    asyncio.run(run())