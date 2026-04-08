from fastapi import FastAPI
from env.environment import SQLRepairEnv
from env.models import Action

app = FastAPI()
env = SQLRepairEnv()

@app.post("/reset")
async def reset():
    result = await env.reset()
    return result

@app.post("/step")
async def step(action: dict):
    act = Action(**action)
    result = await env.step(act)
    return result