import sqlite3
import random
from env.models import Observation, Action
from env.grader import grade

TASKS = [
    # EASY
    {"id": "easy", "broken_query": "SELCET name FROM users", "expected_query": "SELECT name FROM users", "expected_output": [("A",)]},
    {"id": "easy", "broken_query": "SELECT * FORM users", "expected_query": "SELECT * FROM users", "expected_output": [(1, "A", 18)]},
    {"id": "easy", "broken_query": "SELECT name age FROM users", "expected_query": "SELECT name, age FROM users", "expected_output": [("A", 18)]},
    # MEDIUM
    {"id": "medium", "broken_query": "SELECT name FROM users WHERE age >", "expected_query": "SELECT name FROM users WHERE age > 18", "expected_output": []},
    {"id": "medium", "broken_query": "SELECT age FROM users ORDER", "expected_query": "SELECT age FROM users ORDER BY age", "expected_output": [(18,)]},
    {"id": "medium", "broken_query": "SELECT * FROM users WHERE name =", "expected_query": "SELECT * FROM users WHERE name = 'A'", "expected_output": [(1, "A", 18)]},
    # HARD
    {"id": "hard", "broken_query": "SELECT name FROM users GROUP BY age HAVING", "expected_query": "SELECT name FROM users GROUP BY age HAVING COUNT(*) > 0", "expected_output": [("A",)]},
    {"id": "hard", "broken_query": "SELECT * FROM users WHERE age BETWEEN", "expected_query": "SELECT * FROM users WHERE age BETWEEN 10 AND 20", "expected_output": [(1, "A", 18)]},
    {"id": "hard", "broken_query": "SELECT name FROM users WHERE age > AND name =", "expected_query": "SELECT name FROM users WHERE age > 10 AND name = 'A'", "expected_output": [("A",)]},
]


class SQLRepairEnv:
    def __init__(self):
        self.task       = None
        self.task_index = 0
        self.task_types = ["easy", "medium", "hard"]

    @property
    def task_ids(self):
        return self.task_types

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

    async def reset(self, task_id=None):
        if task_id is None:
            task_type = self.task_types[self.task_index % len(self.task_types)]
            self.task_index += 1
        else:
            task_type = task_id

        # ✅ Random choice from matching tasks
        self.task = random.choice([t for t in TASKS if t["id"] == task_type]).copy()

        self.task["schema"]     = "users(id INT, name TEXT, age INT)"
        self.task["difficulty"] = self.task["id"]
        self.task["grader"]     = grade

        print(f"[RESET] difficulty={self.task['id']} query={self.task['broken_query']}", flush=True)

        return {
            "observation": Observation(
                broken_query=self.task["broken_query"],
                db_schema=self.task["schema"],
                difficulty=self.task["difficulty"]
            ),
            "reward": 0.0,
            "done":   False,
            "info": {
                "task_id": self.task["id"],
                "grader":  "env.grader:grade"
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

        grader_cls = self.task.get("grader", grade)
        grader     = grader_cls()
        reward     = grader.grade(
            predicted=query,
            expected_query=self.task.get("expected_query"),
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
            "done":   done,
            "info": {
                "task_id":      self.task.get("id", "unknown"),
                "grader":       "env.grader:grade",
                "grader_score": float(reward)
            }
        }

    async def close(self):
        self.task = None
        print("[CLOSE] Environment closed.", flush=True)
