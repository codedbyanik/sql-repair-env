import sqlite3
import random

from env.tasks.easy import get_task as easy_task
from env.tasks.medium import get_task as medium_task
from env.tasks.hard import get_task as hard_task

from env.grader import grade
from env.models import Observation, Action


# ✅ reproducibility
random.seed(42)


class SQLRepairEnv:

    def __init__(self):
        self.task = None

        # ✅ cycle through difficulty levels
        self.task_index = 0
        self.task_types = ["easy", "medium", "hard"]

    # ✅ OpenEnv state
    def state(self):
        if not self.task:
            return None

        return Observation(
            broken_query=self.task["broken_query"],
            db_schema=self.task["schema"],
            difficulty=self.task["difficulty"]
        )

    # ✅ RESET (fixed properly)
    async def reset(self):

        # pick difficulty in order
        task_type = self.task_types[self.task_index % len(self.task_types)]
        self.task_index += 1

        # call task generator EVERY time (important fix)
        if task_type == "easy":
            self.task = easy_task()
        elif task_type == "medium":
            self.task = medium_task()
        else:
            self.task = hard_task()

        # attach difficulty
        self.task["difficulty"] = task_type

        return {
            "observation": Observation(
                broken_query=self.task["broken_query"],
                db_schema=self.task["schema"],
                difficulty=self.task["difficulty"]
            ),
            "reward": 0.0,
            "done": False,
            "info": {}
        }

    # ✅ STEP
    async def step(self, action: Action):
        query = action.query

        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()

        # create table
        cursor.execute("CREATE TABLE users(id INT, name TEXT, age INT)")
        cursor.execute("INSERT INTO users VALUES (1, 'A', 18)")

        try:
            cursor.execute(query)
            result = cursor.fetchall()
            error = None
        except Exception as e:
            result = None
            error = str(e)

        reward = grade(
            predicted=query,
            expected_query=self.task["correct_query"],
            result=result,
            expected=self.task["expected_output"],
            error=error
        )

        done = reward == 1.0

        return {
            "observation": Observation(
                broken_query=query,
                db_schema=self.task["schema"],
                difficulty=self.task["difficulty"],
                result=result,
                error=error
            ),
            "reward": reward,
            "done": done,
            "info": {}
        }