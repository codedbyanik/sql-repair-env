from env.grader import grade

def get_task():
    tasks = [
        {"broken_query": "SELECT name age FROM users",  "correct_query": "SELECT name, age FROM users", "expected_output": [('A', 18)]},
        {"broken_query": "SELECT * FORM users",         "correct_query": "SELECT * FROM users",         "expected_output": [(1, 'A', 18)]},
        {"broken_query": "SELCET name FROM users",      "correct_query": "SELECT name FROM users",      "expected_output": [('A',)]},
        {"broken_query": "SELECT age FORM users",       "correct_query": "SELECT age FROM users",       "expected_output": [(18,)]},
        {"broken_query": "SELECT id name FROM users",   "correct_query": "SELECT id, name FROM users",  "expected_output": [(1, 'A')]},
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