import gradio as gr
import asyncio

from env.environment import SQLRepairEnv
from env.models import Action
from inference import fix_query

# -----------------------
# 🔥 PERSISTENT ENV (created once, reused across clicks)
# -----------------------
env = SQLRepairEnv()

# -----------------------
# 🔥 MAIN FUNCTION
# -----------------------
def run_demo():

    async def inner():
        try:
            # Reset environment (task_index persists now!)
            state = await env.reset()
            obs = state["observation"]

            broken = obs.broken_query
            schema = obs.db_schema
            difficulty = getattr(obs, "difficulty", "unknown")

            # Fix query
            fixed = fix_query(broken, schema)

            # Run step
            result = await env.step(Action(query=fixed))

            reward = result.get("reward", 0.0)
            result_obs = result["observation"]

            output = result_obs.result
            error = getattr(result_obs, "error", None)

            if error:
                output_text = f"ERROR: {error}"
            else:
                output_text = str(output)

            return broken, fixed, output_text, reward, difficulty, "Done ✅"

        except Exception as e:
            print("ERROR:", str(e))
            return "ERROR", "ERROR", str(e), 0.0, "unknown", "Failed ❌"

    return asyncio.run(inner())


# -----------------------
# 🔥 UI
# -----------------------
with gr.Blocks() as demo:

    gr.Markdown("""
    # 🧠 AI SQL Repair Environment

    Fix broken SQL queries using:
    - LLM (OpenAI-compatible client)
    - Rule-based corrections
    - OpenEnv evaluation

    👉 Click the button to run a full cycle.
    """)

    btn = gr.Button("🚀 Run AI Fix")

    status = gr.Textbox(label="⚡ Status", value="Idle")
    broken = gr.Textbox(label="❌ Broken SQL")
    fixed = gr.Textbox(label="🤖 Fixed SQL")
    result = gr.Textbox(label="📊 Execution Result")
    reward = gr.Number(label="🏆 Reward (0–1)")
    difficulty = gr.Textbox(label="⚙️ Difficulty")

    btn.click(
        fn=run_demo,
        inputs=[],
        outputs=[broken, fixed, result, reward, difficulty, status]
    )


# -----------------------
# 🔥 LAUNCH
# -----------------------
demo.queue().launch(
    server_name="0.0.0.0",
    server_port=7860
)