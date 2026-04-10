"""
app.py — Gradio UI for human interaction.

This file is NOT the Docker entry point.
The Docker container runs server/app.py (the pure FastAPI env server).
This file can be run locally for demo purposes:
    python app.py

It calls the env server via HTTP just like inference.py does.
"""

import asyncio
import httpx
import gradio as gr
from inference import fix_query

ENV_URL = "http://localhost:8000"

episode_history = []


async def call_reset():
    async with httpx.AsyncClient() as http:
        r = await http.post(f"{ENV_URL}/reset", timeout=30)
        r.raise_for_status()
        return r.json()


async def call_step(query: str):
    async with httpx.AsyncClient() as http:
        r = await http.post(f"{ENV_URL}/step", json={"query": query}, timeout=30)
        r.raise_for_status()
        return r.json()


def run_demo():
    async def inner():
        try:
            state      = await call_reset()
            obs        = state["observation"]
            broken     = obs["broken_query"]
            schema     = obs["db_schema"]
            difficulty = obs["difficulty"]

            fixed  = fix_query(broken, schema)
            result = await call_step(fixed)

            reward = result.get("reward", 0.0)
            robs   = result.get("observation", {})
            error  = robs.get("error")
            out    = robs.get("result")

            output_text = f"ERROR: {error}" if error else str(out)

            if reward == 1.0:
                reward_label = "✅ Perfect (1.0)"
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

            table = "| # | Difficulty | Broken Query | Fixed Query | Reward |\n"
            table += "|---|---|---|---|---|\n"
            for e in reversed(episode_history[-10:]):
                icon = ("✅" if e["reward"] == 1.0
                        else "🟢" if e["reward"] >= 0.8
                        else "🟡" if e["reward"] >= 0.3
                        else "🔴")
                table += f"| {e['episode']} | {e['difficulty']} | `{e['broken']}` | `{e['fixed']}` | {icon} {e['reward']:.2f} |\n"

            status_msg = (
                f"✅ Episode {len(episode_history)} complete | "
                f"Reward: {reward:.2f} | Avg: {avg:.2f}"
            )

            return (
                broken, schema, fixed, output_text,
                reward_label, difficulty.upper(),
                f"{avg:.2f}", str(len(episode_history)),
                table, status_msg,
            )

        except Exception as e:
            print("ERROR:", str(e), flush=True)
            return (
                "ERROR", "", "ERROR", str(e),
                "🔴 Failed (0.0)", "unknown",
                "0.00", str(len(episode_history)),
                "", f"❌ Failed: {str(e)}"
            )

    return asyncio.run(inner())


CSS = """
.reward-display textarea { font-size: 1.3em !important; font-weight: bold !important; text-align: center !important; }
.stat-box textarea { font-size: 1.2em !important; text-align: center !important; }
footer { display: none !important; }
"""

with gr.Blocks(css=CSS, title="🧠 SQL Repair Environment") as demo:
    gr.Markdown("""
    # 🧠 AI SQL Repair Environment
    > An **OpenEnv-compliant** RL environment where an AI agent repairs broken SQL queries.
    > Difficulty auto-rotates: **Easy → Medium → Hard → Easy...**
    """)

    with gr.Row():
        episode_count  = gr.Textbox(label="🎮 Episodes Run",       value="0",  interactive=False, elem_classes="stat-box")
        avg_reward_out = gr.Textbox(label="📊 Average Reward",     value="—",  interactive=False, elem_classes="stat-box")
        difficulty_out = gr.Textbox(label="⚙️ Current Difficulty", value="—",  interactive=False, elem_classes="stat-box")
        reward_out     = gr.Textbox(label="🏆 Last Reward",        value="—",  interactive=False, elem_classes="reward-display")

    with gr.Row():
        btn    = gr.Button("🚀 Run AI Fix", variant="primary", scale=2)
        status = gr.Textbox(label="⚡ Status", value="Click '🚀 Run AI Fix' to start...", interactive=False)

    gr.Markdown("---")

    with gr.Row():
        with gr.Column():
            gr.Markdown("### 📥 Input (Broken)")
            broken_out = gr.Textbox(label="❌ Broken SQL",  lines=3, interactive=False)
            schema_out = gr.Textbox(label="🗄️ Schema",     lines=1, interactive=False)
        with gr.Column():
            gr.Markdown("### 📤 Output (Fixed)")
            fixed_out  = gr.Textbox(label="🤖 AI-Fixed SQL",      lines=3, interactive=False)
            result_out = gr.Textbox(label="📊 Execution Result",   lines=1, interactive=False)

    gr.Markdown("---")
    gr.Markdown("### 📋 Episode History _(last 10, newest first)_")
    history_table = gr.Markdown(value="_No episodes yet — click Run to begin._")

    with gr.Accordion("🔌 REST API Reference", open=False):
        gr.Markdown("""
        The env server exposes a REST API on **port 8000**:

        | Endpoint | Method | Description |
        |---|---|---|
        | `/reset` | POST | Reset env, get new broken query |
        | `/step` | POST `{"query": "..."}` | Submit fixed SQL, get reward |
        | `/state` | GET | Current env state |
        | `/close` | POST | Close environment |
        | `/health` | GET | Health check |
        | `/docs` | GET | Interactive Swagger docs |

        **Reward Scale:**
        - `1.0` — Exact query match
        - `0.8` — Output matches expected rows
        - `0.3` — Valid SELECT but wrong result
        - `0.0` — Syntax error
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

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)