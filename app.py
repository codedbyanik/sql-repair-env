import asyncio
import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import gradio as gr

from env.environment import SQLRepairEnv
from env.models import Action
from inference import fix_query

# -----------------------
# 🔥 FASTAPI APP
# -----------------------
api = FastAPI(title="SQL Repair OpenEnv", version="1.0")
env = SQLRepairEnv()

# In-memory episode history
episode_history = []


@api.post("/reset")
async def reset():
    """Required by OpenEnv validator — POST /reset → 200 OK."""
    state = await env.reset()
    obs = state["observation"]
    return JSONResponse(status_code=200, content={
        "observation": {
            "broken_query": obs.broken_query,
            "db_schema":    obs.db_schema,
            "difficulty":   obs.difficulty,
        },
        "reward": state["reward"],
        "done":   state["done"],
        "info":   state["info"],
    })


class StepRequest(BaseModel):
    query: str


@api.post("/step")
async def step(body: StepRequest):
    """POST /step → 200 OK with reward + observation."""
    result = await env.step(Action(query=body.query))
    obs = result["observation"]
    return JSONResponse(status_code=200, content={
        "observation": {
            "broken_query": obs.broken_query,
            "db_schema":    obs.db_schema,
            "difficulty":   obs.difficulty,
            "result":       obs.result,
            "error":        obs.error,
        },
        "reward": result["reward"],
        "done":   result["done"],
        "info":   result["info"],
    })


@api.get("/health")
async def health():
    return JSONResponse(status_code=200, content={"status": "ok"})


@api.get("/history")
async def history():
    """Returns all past episode results and average reward."""
    avg = round(sum(e["reward"] for e in episode_history) / len(episode_history), 3) \
          if episode_history else 0.0
    return JSONResponse(status_code=200, content={
        "episodes":       len(episode_history),
        "history":        episode_history,
        "average_reward": avg,
    })


# -----------------------
# 🔥 GRADIO DEMO FUNCTION
# -----------------------
def run_demo():
    async def inner():
        try:
            state = await env.reset()
            obs = state["observation"]

            broken     = obs.broken_query
            schema     = obs.db_schema
            difficulty = getattr(obs, "difficulty", "unknown")

            fixed  = fix_query(broken, schema)
            result = await env.step(Action(query=fixed))

            reward     = result.get("reward", 0.0)
            result_obs = result["observation"]
            output     = result_obs.result
            error      = getattr(result_obs, "error", None)

            output_text = f"❌ ERROR: {error}" if error else str(output)

            # Track episode
            episode_history.append({
                "episode":    len(episode_history) + 1,
                "difficulty": difficulty,
                "broken":     broken,
                "fixed":      fixed,
                "reward":     round(reward, 2),
                "error":      error or "",
            })

            # Reward label with color emoji
            if reward == 1.0:
                reward_label = "🟢 Perfect (1.0)"
            elif reward >= 0.8:
                reward_label = f"🟡 Good ({reward:.2f})"
            elif reward >= 0.3:
                reward_label = f"🟠 Partial ({reward:.2f})"
            else:
                reward_label = f"🔴 Failed ({reward:.2f})"

            avg_reward = sum(e["reward"] for e in episode_history) / len(episode_history)

            # Build history markdown table (last 10, newest first)
            table = "| # | Difficulty | Broken Query | Fixed Query | Reward |\n"
            table += "|---|---|---|---|---|\n"
            for e in reversed(episode_history[-10:]):
                icon = ("🟢" if e["reward"] == 1.0
                        else "🟡" if e["reward"] >= 0.8
                        else "🟠" if e["reward"] >= 0.3
                        else "🔴")
                table += f"| {e['episode']} | {e['difficulty']} | `{e['broken']}` | `{e['fixed']}` | {icon} {e['reward']:.2f} |\n"

            status_msg = (
                f"✅ Episode {len(episode_history)} complete | "
                f"Reward: {reward:.2f} | Avg: {avg_reward:.2f}"
            )

            return (
                broken,
                schema,
                fixed,
                output_text,
                reward_label,
                difficulty.upper(),
                f"{avg_reward:.2f}",
                str(len(episode_history)),
                table,
                status_msg,
            )

        except Exception as e:
            print("ERROR:", str(e))
            return (
                "ERROR", "", "ERROR", str(e),
                "🔴 Failed (0.0)", "unknown",
                "0.00", str(len(episode_history)),
                "", f"❌ Failed: {str(e)}"
            )

    return asyncio.run(inner())


# -----------------------
# 🔥 GRADIO UI
# -----------------------
CSS = """
.reward-display textarea {
    font-size: 1.3em !important;
    font-weight: bold !important;
    text-align: center !important;
}
.stat-box textarea {
    font-size: 1.2em !important;
    text-align: center !important;
}
footer { display: none !important; }
"""

with gr.Blocks(css=CSS, title="🧠 SQL Repair Environment") as demo:

    gr.Markdown("""
    # 🧠 AI SQL Repair Environment
    > An **OpenEnv-compliant** RL environment where an AI agent repairs broken SQL queries and is scored on correctness.
    > Difficulty auto-rotates: **Easy → Medium → Hard → Easy ...**
    """)

    # --- Stats Row ---
    with gr.Row():
        episode_count  = gr.Textbox(
            label="🎮 Episodes Run", value="0",
            interactive=False, elem_classes="stat-box"
        )
        avg_reward_out = gr.Textbox(
            label="📈 Average Reward", value="—",
            interactive=False, elem_classes="stat-box"
        )
        difficulty_out = gr.Textbox(
            label="⚙️ Current Difficulty", value="—",
            interactive=False, elem_classes="stat-box"
        )
        reward_out = gr.Textbox(
            label="🏆 Last Reward", value="—",
            interactive=False, elem_classes="reward-display"
        )

    # --- Run Button & Status ---
    with gr.Row():
        btn = gr.Button("🚀 Run AI Fix", variant="primary", scale=2)
    status = gr.Textbox(
        label="⚡ Status", value="Click '🚀 Run AI Fix' to start...",
        interactive=False
    )

    gr.Markdown("---")

    # --- SQL Panel ---
    with gr.Row():
        with gr.Column():
            gr.Markdown("### 🔴 Input (Broken)")
            broken_out = gr.Textbox(label="❌ Broken SQL", lines=3, interactive=False)
            schema_out = gr.Textbox(label="🗂️ Schema", lines=1, interactive=False)

        with gr.Column():
            gr.Markdown("### 🟢 Output (Fixed)")
            fixed_out  = gr.Textbox(label="✅ AI-Fixed SQL", lines=3, interactive=False)
            result_out = gr.Textbox(label="📊 Execution Result", lines=1, interactive=False)

    gr.Markdown("---")

    # --- History Table ---
    gr.Markdown("### 📋 Episode History _(last 10, newest first)_")
    history_table = gr.Markdown(value="_No episodes yet — click Run to begin._")

    # --- API Docs ---
    with gr.Accordion("🔌 REST API Reference", open=False):
        gr.Markdown("""
        This space exposes a full REST API on the same port as the UI:

        | Endpoint | Method | Description |
        |---|---|---|
        | `/reset` | POST | Reset environment, receive a new broken query |
        | `/step` | POST `{"query": "..."}` | Submit fixed SQL, receive reward |
        | `/health` | GET | Health check → `{"status": "ok"}` |
        | `/history` | GET | All episode results + average reward |
        | `/docs` | GET | Interactive FastAPI Swagger docs |

        **Reward Scale:**
        - 🟢 `1.0` — Exact query match
        - 🟡 `0.8` — Output matches expected result
        - 🟠 `0.3` — Structurally valid SELECT
        - 🔴 `0.0` — Syntax error or completely wrong
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


# -----------------------
# 🔥 MOUNT GRADIO INSIDE FASTAPI (single port 7860)
# -----------------------
app = gr.mount_gradio_app(api, demo, path="/")

# -----------------------
# 🔥 LAUNCH
# -----------------------
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7860)