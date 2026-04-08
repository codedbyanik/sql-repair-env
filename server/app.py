from fastapi import FastAPI
from env.environment import SQLRepairEnv
from env.models import Action
import uvicorn

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


# ✅ REQUIRED MAIN FUNCTION
def main():
    uvicorn.run(app, host="0.0.0.0", port=8000)


# ✅ REQUIRED ENTRY POINT
if __name__ == "__main__":
    main()