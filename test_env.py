import sys
import os

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

import asyncio
from env.environment import SQLRepairEnv
from env.models import Action

async def test():
    env = SQLRepairEnv()
    result = await env.reset()

    print("Broken Query:", result["observation"].broken_query)
    action = Action(query="SELECT * FROM users;")

    result = await env.step(action)

    print("Reward:", result["reward"])
    print("Result:", result["observation"].result)



asyncio.run(test())