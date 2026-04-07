import sqlite3
import random
from env.tasks.easy import get_task as easy_task
from env.tasks.medium import get_task as medium_task
from env.tasks.hard import get_task as hard_task
from env.grader import grade
from env.models import Observation, Action

# -----------------------
# 🔥 NOTE: No global random.seed() here — it caused step() to always
# insert age=18, which randomly broke output matching.
# Each task's expected_output is now matched to a fixed age (see step()).
# -----------------------

class SQLRepairEnv:
    def __init__(self):
        self.task = None
        # Cycle through difficulties: easy → medium → hard → easy ...
        self.task_index = 0
        self.task_types = ["easy", "medium", "hard"]

    # -----------------------
    # 🔥 STATE
    # -----------------------
    def state(self):
        if not self.task:
            return None
        return Observation(
            broken_query=self.task["broken_query"],
            db_schema=self.task["schema"],
            difficulty=self.task["difficulty"]
        )

    # -----------------------
    # 🔥 RESET
    # -----------------------
    async def reset(self):
        task_type = self.task_types[self.task_index % len(self.task_types)]
        self.task_index += 1

        if task_type == "easy":
            self.task = easy_task()
        elif task_type == "medium":
            self.task = medium_task()
        else:
            self.task = hard_task()

        self.task["difficulty"] = task_type

        print(f"[RESET] difficulty={task_type} broken_query={self.task['broken_query']}", flush=True)

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

    # -----------------------
    # 🔥 STEP
    # -----------------------
    async def step(self, action: Action):
        query = action.query
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()

        try:
            # Create table
            cursor.execute("CREATE TABLE users(id INT, name TEXT, age INT)")

            # ✅ FIX: Use fixed age=18 always so expected_output in task files matches.
            # Previously random.choice([18,20,25]) meant age could be 20 or 25,
            # causing correct queries to get 0.8 (output mismatch) instead of 1.0.
            cursor.execute("INSERT INTO users VALUES (1, 'A', 18)")

            # Execute the fixed query
            cursor.execute(query)
            result = cursor.fetchall()
            error = None

        except Exception as e:
            result = None
            error = str(e)

        finally:
            conn.close()

        # -----------------------
        # 🔥 REWARD
        # -----------------------
        reward = grade(
            predicted=query,
            expected_query=self.task["correct_query"],
            result=result,
            expected=self.task["expected_output"],
            error=error
        )

        # ✅ FIX: Removed the wrong partial reward for syntax errors.
        # Previously: if syntax error → reward = max(reward, 0.3)
        # This gave 0.3 reward for BROKEN SQL, which is completely wrong.
        # grader.py already returns 0.0 for errors — we respect that.

        done = reward == 1.0

        print(
            f"[STEP] query={query!r} reward={reward:.2f} done={done} error={error}",
            flush=True
        )

        # -----------------------
        # 🔥 OBSERVATION
        # -----------------------
        return {
            "observation": Observation(
                broken_query=self.task["broken_query"],  # keep original broken query
                db_schema=self.task["schema"],
                difficulty=self.task["difficulty"],
                result=result,
                error=error
            ),
            "reward": reward,
            "done": done,
            "info": {}
        }
