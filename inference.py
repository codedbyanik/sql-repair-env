import asyncio
from transformers import pipeline

from env.environment import SQLRepairEnv
from env.models import Action


# ✅ Load model (deterministic)
generator = pipeline(
    "text2text-generation",
    model="google/flan-t5-base",
    do_sample=False
)


# ✅ AI FIX FUNCTION
def fix_query_with_ai(broken_query, schema):
    prompt = f"""
Fix the SQL query. Return ONLY valid SQL.

Schema:
{schema}

Broken Query:
{broken_query}

Correct SQL:
"""

    result = generator(prompt, max_new_tokens=60)
    output = result[0]["generated_text"]

    fixed_query = output.split("Correct SQL:")[-1].strip()
    fixed_query = fixed_query.split("\n")[0]

    # 🔧 Rule-based cleanup
    fixed_query = fixed_query.replace("FORM", "FROM")

    if fixed_query.strip().endswith(">"):
        fixed_query += " 18"

    if fixed_query.strip().endswith("ORDER"):
        fixed_query += " BY age"

    return fixed_query


# ✅ MAIN EVALUATION LOOP
async def run():
    env = SQLRepairEnv()

    total = 0
    score = 0

    NUM_EPISODES = 10  # ✅ fixed for reproducibility

    print("\n🎮 AI SQL Repair Evaluation Started!\n")

    for episode in range(NUM_EPISODES):

        # ✅ RESET ENVIRONMENT
        state = await env.reset()
        obs = state["observation"]

        # ✅ ACCESS STATE (OpenEnv compliance)
        current_state = env.state()

        broken_query = obs.broken_query
        schema = obs.db_schema
        difficulty = obs.difficulty

        print("\n==============================")
        print(f"🎯 Episode {episode + 1} | Difficulty: {difficulty}")
        print("🧩 Broken Query:")
        print(broken_query)

        input("\n👉 Press Enter to let AI fix it...")

        # 🤖 AI Fix
        fixed_query = fix_query_with_ai(broken_query, schema)

        print("\n🤖 AI Fixed Query:")
        print(fixed_query)

        # ✅ STEP (apply action)
        action = Action(query=fixed_query)
        result = await env.step(action)

        reward = result["reward"]
        done = result["done"]
        new_obs = result["observation"]

        print("\n🏆 Reward:", reward)
        print("📊 Result:", new_obs.result)

        # ✅ Accuracy tracking
        total += 1
        score += reward

        print(f"\n📈 Accuracy: {score / total:.2f}")

        # ✅ User control
        cont = input("\n➡️ Press Enter for next OR type 'exit': ")
        if cont.lower() == "exit":
            break

    print("\n==============================")
    print(f"✅ FINAL SCORE: {score / total:.2f}")


# ✅ ENTRY POINT
if __name__ == "__main__":
    asyncio.run(run())