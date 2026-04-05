import gradio as gr
import asyncio

from env.environment import SQLRepairEnv
from env.models import Action
from inference import fix_query_with_ai


# -----------------------
# 🔥 MAIN DEMO FUNCTION
# -----------------------
def run_demo():
    async def inner():
        try:
            env = SQLRepairEnv()

            # Reset environment
            state = await env.reset()
            obs = state["observation"]

            # ✅ Correct object access
            broken = obs.broken_query
            schema = obs.db_schema

            # 🤖 AI fix
            fixed = fix_query_with_ai(broken, schema)

            # Run environment step
            result = await env.step(Action(query=fixed))

            # ✅ Safe extraction
            reward = result.get("reward", 0.0)

            result_obs = result["observation"]

            output = result_obs.result
            error = getattr(result_obs, "error", None)

            return broken, fixed, str(output), reward

        except Exception as e:
            print("ERROR:", str(e))  # shows in Logs tab
            return "ERROR", "ERROR", str(e), 0.0

    return asyncio.run(inner())

# -----------------------
# 🔥 UI LAYOUT
# -----------------------
with gr.Blocks() as demo:
    gr.Markdown("""
    # 🧠 AI SQL Repair Environment
    This system takes a broken SQL query, fixes it using AI, 
    executes it, and assigns a reward based on correctness.
    """)

    btn = gr.Button("🚀 Run AI Fix")

    broken = gr.Textbox(label="❌ Broken SQL")
    fixed = gr.Textbox(label="🤖 Fixed SQL")
    result = gr.Textbox(label="📊 Execution Result")
    reward = gr.Number(label="🏆 Reward (0–1)")

    btn.click(
        fn=run_demo,
        inputs=[],   # ✅ IMPORTANT FIX
        outputs=[broken, fixed, result, reward]
    )


# -----------------------
# 🔥 LAUNCH (HF READY)
# -----------------------
demo.queue().launch(
    server_name="0.0.0.0",
    server_port=7860
)