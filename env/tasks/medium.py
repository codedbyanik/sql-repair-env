import random

def get_task():
    tasks = [
        {
            "broken_query": "SELECT name FROM users WHERE age >",
            "correct_query": "SELECT name FROM users WHERE age > 18",
            "expected_output": [],
        },
        {
            "broken_query": "SELECT age FROM users ORDER",
            "correct_query": "SELECT age FROM users ORDER BY age",
            "expected_output": [(18,)],
        },
        {
            "broken_query": "SELECT * FROM users WHERE name =",
            "correct_query": "SELECT * FROM users WHERE name = 'A'",
            "expected_output": [(1, 'A', 18)],
        },
        {
            "broken_query": "SELECT COUNT(*) FROM users WHERE age >",
            "correct_query": "SELECT COUNT(*) FROM users WHERE age > 10",
            "expected_output": [(1,)],
        },
        {
            "broken_query": "SELECT name FROM users ORDER",
            "correct_query": "SELECT name FROM users ORDER BY name",
            "expected_output": [('A',)],
        }
    ]

    if not hasattr(get_task, "index"):

        get_task.index = 0

    task = tasks[get_task.index % len(tasks)]
    get_task.index += 1

    return {
        "broken_query": task["broken_query"],
        "correct_query": task["correct_query"],
        "expected_output": task["expected_output"],
        "schema": "users(id INT, name TEXT, age INT)"
    }