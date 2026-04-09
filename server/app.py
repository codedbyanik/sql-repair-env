import sys
import os
import asyncio
import gradio as gr
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from env.environment import SQLRepairEnv
from env.models import Action
from inference import fix_query

# -----------------------
# 🔥 TWO SEPARATE ENV INSTANCES
# api_env  → used by /reset /step /close (validator)
# ui_env   → used by Gradio UI button
# -----------------------
api_env = SQLRepairEnv()
ui_env  = SQLRepairEnv()

# -----------------------
# 🔥 FASTAPI
# -----------------------
app = FastAPI(title="SQL Repair Environment", version="1.0")


def obs_to_dict(obs):
    return {
        "broken_query": obs.broken_query,
        "db_schema":    obs.db_schema,
        "difficulty":   obs.difficulty,
        "result":       obs.result,
        "error":        obs.error,
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/reset")
async def reset():
    result = await api_env.reset()
    obs = result["observation"]
    return {"observation": obs_to_dict(obs), "reward": result["reward"],
            "done": result["done"], "info": result["info"]}


@app.post("/step")
async def step(action: dict):
    act = Action(**action)
    result = await api_env.step(act)
    obs = result["observation"]
    return {"observation": obs_to_dict(obs), "reward": result["reward"],
            "done": result["done"], "info": result["info"]}


@app.get("/state")
async def state():
    return obs_to_dict(api_env.state())


@app.post("/close")
async def close():
    await api_env.close()
    return {"status": "closed"}


# -----------------------
# 🔥 GRADIO UI
# -----------------------
def run_demo():
    async def inner():
        try:
            state   = await ui_env.reset()
            obs     = state["observation"]
            broken  = obs.broken_query
            schema  = obs.db_schema
            difficulty = obs.difficulty

            fixed  = fix_query(broken, schema)
            result = await ui_env.step(Action(query=fixed))

            reward     = result.get("reward", 0.0)
            result_obs = result["observation"]
            error      = getattr(result_obs, "error", None)
            output     = getattr(result_obs, "result", None)

            output_text = f"ERROR: {error}" if error else str(output)
            return broken, fixed, output_text, round(reward, 2), difficulty, "Done ✅"

        except Exception as e:
            print("UI ERROR:", str(e), flush=True)
            return "ERROR", "ERROR", str(e), 0.0, "unknown", "Failed ❌"

    return asyncio.run(inner())


with gr.Blocks(title="🧠 SQL Repair Environment") as demo:
    gr.Markdown("""
    # 🧠 AI SQL Repair Environment
    Fix broken SQL queries using LLM + rule engine.
    Difficulty rotates automatically: **Easy → Medium → Hard**
    """)

    btn = gr.Button("🚀 Run AI Fix", variant="primary", size="lg")

    with gr.Row():
        status     = gr.Textbox(label="⚡ Status",     value="Idle")
        difficulty = gr.Textbox(label="⚙️ Difficulty", value="")

    with gr.Row():
        broken = gr.Textbox(label="❌ Broken SQL")
        fixed  = gr.Textbox(label="🤖 Fixed SQL")

    with gr.Row():
        result = gr.Textbox(label="📊 Execution Result")
        reward = gr.Number( label="🏆 Reward (0–1)")

    btn.click(
        fn=run_demo,
        inputs=[],
        outputs=[broken, fixed, result, reward, difficulty, status]
    )

# -----------------------
# 🔥 MOUNT GRADIO INTO FASTAPI at root "/"
# Validator hits /reset and /step  → FastAPI handles them first
# Browser hitting /                → Gradio UI
# -----------------------
app = gr.mount_gradio_app(app, demo, path="/")