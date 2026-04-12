"""
server/app.py — Docker entry point (port 7860).
"""

import sys
import os
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import gradio as gr
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from env.environment import SQLRepairEnv
from env.models import Action
from env.grader import grade

api_env = SQLRepairEnv()
ui_env  = SQLRepairEnv()
episode_history = []

fastapi_app = FastAPI(title="SQL Repair OpenEnv", version="1.0")


def obs_to_dict(obs):
    return {
        "broken_query": obs.broken_query,
        "db_schema":    obs.db_schema,
        "difficulty":   obs.difficulty,
        "result":       obs.result,
        "error":        obs.error,
    }


@fastapi_app.get("/")
async def root():
    return {"status": "ok"}


@fastapi_app.get("/health")
async def health():
    return {"status": "ok"}


@fastapi_app.post("/reset")
async def reset():
    result = await api_env.reset()
    obs = result["observation"]
    return JSONResponse(status_code=200, content={
        "observation": obs_to_dict(obs),
        "reward": result["reward"],
        "done":   result["done"],
        "info":   result["info"],
    })


class StepRequest(BaseModel):
    query: str


@fastapi_app.post("/step")
async def step(body: StepRequest):
    result = await api_env.step(Action(query=body.query))
    obs = result["observation"]
    return JSONResponse(status_code=200, content={
        "observation": obs_to_dict(obs),
        "reward": result["reward"],
        "done":   result["done"],
        "info":   result["info"],
    })


@fastapi_app.get("/state")
async def state():
    obs = api_env.state()
    if obs is None:
        return JSONResponse(status_code=200, content={"state": None})
    return JSONResponse(status_code=200, content=obs_to_dict(obs))


class GraderRequest(BaseModel):
    task_id: str = "easy"
    predicted: str = ""
    expected_query: str = ""
    result: object = None
    expected: object = None
    error: str = None


@fastapi_app.post("/grader")
async def grader_endpoint(body: GraderRequest):
    g = grade()
    score = g.grade(
        predicted=body.predicted,
        expected_query=body.expected_query,
        result=body.result,
        expected=body.expected,
        error=body.error,
    )
    return JSONResponse(status_code=200, content={
        "task_id": body.task_id,
        "score":   score,
        "reward":  score,
    })


# =============================================================
# GRADIO UI
# =============================================================

def run_demo():
    async def inner():
        try:
            from inference import fix_query

            state      = await ui_env.reset()
            obs        = state["observation"]
            broken     = obs.broken_query
            schema     = obs.db_schema
            difficulty = obs.difficulty

            fixed  = fix_query(broken, schema)
            result = await ui_env.step(Action(query=fixed))

            reward = result.get("reward", 0.0)
            robs   = result["observation"]
            error  = getattr(robs, "error", None)
            out    = getattr(robs, "result", None)

            output_text = f"ERROR: {error}" if error else str(out)

            if reward >= 0.95:
                reward_label = f"✅ Perfect ({reward:.2f})"
            elif reward >= 0.8:
                reward_label = f"🟢 Good ({reward:.2f})"
            elif reward >= 0.3:
                reward_label = f"🟡 Partial ({reward:.2f})"
            else:
                reward_label = f"🔴 Failed ({reward:.2f})"

            episode_history.append({
                "episode":    len(episode_history) + 1,
                "difficulty": difficulty,
                "broken":     broken,
                "fixed":      fixed,
                "reward":     round(reward, 2),
                "error":      error or "",
            })

            avg = sum(e["reward"] for e in episode_history) / len(episode_history)

            table  = "| # | Difficulty | Broken Query | Fixed Query | Reward |\n"
            table += "|---|---|---|---|---|\n"
            for e in reversed(episode_history[-10:]):
                icon = ("✅" if e["reward"] >= 0.95
                        else "🟢" if e["reward"] >= 0.8
                        else "🟡" if e["reward"] >= 0.3
                        else "🔴")
                table += (
                    f"| {e['episode']} | {e['difficulty']} "
                    f"| `{e['broken']}` | `{e['fixed']}` "
                    f"| {icon} {e['reward']:.2f} |\n"
                )

            return (
                broken, schema, fixed, output_text,
                reward_label, difficulty.upper(),
                f"{avg:.2f}", str(len(episode_history)),
                table, f"✅ Episode {len(episode_history)} | Reward: {reward:.2f} | Avg: {avg:.2f}",
            )

        except Exception as e:
            print("UI ERROR:", str(e), flush=True)
            return (
                "ERROR", "", "ERROR", str(e),
                "🔴 Failed (0.0)", "unknown",
                "0.00", str(len(episode_history)),
                "", f"❌ Failed: {str(e)}"
            )

    return asyncio.run(inner())


with gr.Blocks(title="🧠 SQL Repair Environment") as demo:
    gr.Markdown("""
    # 🧠 AI SQL Repair Environment
    > **OpenEnv-compliant** RL environment — AI agent repairs broken SQL and gets scored 0.05→0.95.
    > Difficulty auto-rotates: **Easy → Medium → Hard → Easy...**
    """)

    with gr.Row():
        episode_count  = gr.Textbox(label="🎮 Episodes Run",       value="0", interactive=False)
        avg_reward_out = gr.Textbox(label="📊 Average Reward",     value="—", interactive=False)
        difficulty_out = gr.Textbox(label="⚙️ Current Difficulty", value="—", interactive=False)
        reward_out     = gr.Textbox(label="🏆 Last Reward",        value="—", interactive=False)

    with gr.Row():
        btn    = gr.Button("🚀 Run AI Fix", variant="primary", scale=2)
        status = gr.Textbox(label="⚡ Status", value="Click '🚀 Run AI Fix' to start...", interactive=False)

    gr.Markdown("---")

    with gr.Row():
        with gr.Column():
            gr.Markdown("### 📥 Input (Broken)")
            broken_out = gr.Textbox(label="❌ Broken SQL",        lines=3, interactive=False)
            schema_out = gr.Textbox(label="🗄️ Schema",           lines=1, interactive=False)
        with gr.Column():
            gr.Markdown("### 📤 Output (Fixed)")
            fixed_out  = gr.Textbox(label="🤖 AI-Fixed SQL",     lines=3, interactive=False)
            result_out = gr.Textbox(label="📊 Execution Result", lines=1, interactive=False)

    gr.Markdown("---")
    gr.Markdown("### 📋 Episode History _(last 10, newest first)_")
    history_table = gr.Markdown(value="_No episodes yet — click Run to begin._")

    with gr.Accordion("🔌 REST API Reference", open=False):
        gr.Markdown("""
        | Endpoint | Method | Description |
        |---|---|---|
        | `/reset` | POST | Reset env, get new broken query |
        | `/step` | POST `{"query":"..."}` | Submit fixed SQL, get reward |
        | `/grader` | POST | Score a query directly |
        | `/state` | GET | Current env state |
        | `/health` | GET | `{"status": "ok"}` |
        | `/docs` | GET | Swagger API docs |
        """)

    btn.click(
        fn=run_demo,
        inputs=[],
        outputs=[
            broken_out, schema_out, fixed_out, result_out,
            reward_out, difficulty_out, avg_reward_out,
            episode_count, history_table, status,
        ],
    )


app = gr.mount_gradio_app(fastapi_app, demo, path="/")


def main():
    import uvicorn
    uvicorn.run("server.app:app", host="0.0.0.0", port=7860, reload=False)


if __name__ == "__main__":
    main()
