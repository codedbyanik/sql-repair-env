from env.grader import grade

def get_task():
    tasks = [
        {"broken_query": "SELECT COUNT(*) FROM users WHERE age >",         "correct_query": "SELECT COUNT(*) FROM users WHERE age > 10",                  "expected_output": [(1,)]},
        {"broken_query": "SELECT name FROM users GROUP BY age HAVING",     "correct_query": "SELECT name FROM users GROUP BY age HAVING COUNT(*) > 0",    "expected_output": [("A",)]},
        {"broken_query": "SELECT name FROM users WHERE age > AND name =",  "correct_query": "SELECT name FROM users WHERE age > 10 AND name = 'A'",       "expected_output": [("A",)]},
        {"broken_query": "SELECT * FROM users WHERE age BETWEEN",          "correct_query": "SELECT * FROM users WHERE age BETWEEN 10 AND 20",            "expected_output": [(1, "A", 18)]},
        {"broken_query": "SELECT COUNT(*) FROM users GROUP BY age HAVING", "correct_query": "SELECT COUNT(*) FROM users GROUP BY age HAVING COUNT(*) > 0","expected_output": [(1,)]},
        {"broken_query": "SELECT name FROM users WHERE id IN",             "correct_query": "SELECT name FROM users WHERE id IN (1)",                     "expected_output": [("A",)]},
        {"broken_query": "SELECT * FROM users ORDER BY age DESC LIMIT",    "correct_query": "SELECT * FROM users ORDER BY age DESC LIMIT 1",              "expected_output": [(1, "A", 18)]},
    ]
    if not hasattr(get_task, "index"):
        get_task.index = 0
    task = tasks[get_task.index % len(tasks)]
    get_task.index += 1
    return {
        "broken_query":    task["broken_query"],
        "correct_query":   task["correct_query"],
        "expected_output": task["expected_output"],
        "schema":          "users(id INT, name TEXT, age INT)",
        "grader":          grade,
    }
