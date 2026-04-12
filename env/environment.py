import sqlite3
from env.models import Observation, Action
from env.grader import grade


TASKS = [
    {
        "id": "easy",
        "broken_query": "SELCET name FROM users",
        "expected_query": "SELECT name FROM users",
        "expected_output": [("A",)],
        "grader": grade,
    },
    {
        "id": "medium",
        "broken_query": "SELECT name FROM users WHERE age >",
        "expected_query": "SELECT name FROM users WHERE age > 18",
        "expected_output": [],
        "grader": grade,
    },
    {
        "id": "hard",
        "broken_query": "SELECT name FROM users GROUP BY age HAVING",
        "expected_query": "SELECT name FROM users GROUP BY age HAVING COUNT(*) > 0",
        "expected_output": [("A",)],
        "grader": grade,
    },
]

class SQLRepairEnv:
    def __init__(self):   # ✅ FIXED
        self.task       = None
        self.task_index = 0
        self.task_types = ["easy", "medium", "hard"]

    # ✅ REQUIRED for validator
    @property
    def task_ids(self):
        return self.task_types

    # (optional, harmless)
    @property
    def tasks(self):
        return TASKS

    def state(self):
        if not self.task:
            return Observation(
                broken_query="",
                db_schema="users(id INT, name TEXT, age INT)",
                difficulty="easy"
            )
        return Observation(
            broken_query=self.task["broken_query"],
            db_schema=self.task["schema"],
            difficulty=self.task["difficulty"]
        )

    # ✅ FIXED: supports task_id
    async def reset(self, task_id=None):
        if task_id is None:
            task_type = self.task_types[self.task_index % len(self.task_types)]
            self.task_index += 1
        else:
            task_type = task_id

        if task_type == "easy":
            self.task = easy_task()
        elif task_type == "medium":
            self.task = medium_task()
        elif task_type == "hard":
            self.task = hard_task()
        else:
            raise ValueError(f"Unknown task_id: {task_type}")

        self.task["difficulty"] = task_type
        self.task["id"] = task_type

        print(f"[RESET] difficulty={task_type} query={self.task['broken_query']}", flush=True)

        return {
            "observation": Observation(
                broken_query=self.task["broken_query"],
                db_schema=self.task["schema"],
                difficulty=self.task["difficulty"]
            ),
            "reward": 0.0,
            "done": False,
            "info": {
                "task_id": self.task["id"],
                "grader": "env.grader:grade"
            }
        }

    async def step(self, action: Action):
        query  = action.query
        conn   = sqlite3.connect(":memory:")
        cursor = conn.cursor()

        try:
            cursor.execute("CREATE TABLE users(id INT, name TEXT, age INT)")
            cursor.execute("INSERT INTO users VALUES (1, 'A', 18)")
            cursor.execute(query)
            result = cursor.fetchall()
            error  = None
        except Exception as e:
            result = None
            error  = str(e)
        finally:
            conn.close()

        grader = self.task.get("grader", grade)
        reward = grader(
            predicted=query,
            expected_query=self.task.get("expected_query", self.task.get("correct_query")),
            result=result,
            expected=self.task.get("expected_output"),
            error=error
        )

        done = reward >= 0.95

        print(f"[STEP] query={query!r} reward={reward:.2f} done={done} error={error}", flush=True)

        return {
            "observation": Observation(
                broken_query=self.task["broken_query"],
                db_schema=self.task["schema"],
                difficulty=self.task["difficulty"],
                result=result,
                error=error
            ),
            "reward": reward,
            "done": done,
            "info": {
                "task_id": self.task.get("id", "unknown") if self.task else "unknown",
                "grader": "env.grader:grade",
                "grader_score": float(reward)   # ✅ CRITICAL
            }
        }

    async def close(self):
        self.task = None
        print("[CLOSE] Environment closed.", flush=True)
