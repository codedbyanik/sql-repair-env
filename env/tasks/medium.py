def get_task():
    """
    Medium tasks: incomplete clauses — truncated WHERE, ORDER BY without column,
    missing value in condition, incomplete LIMIT.
    All expected_output values assume table: users(1, 'A', 18).
    """
    tasks = [
        # Truncated WHERE clause (no value)
        {
            "broken_query":   "SELECT name FROM users WHERE age >",
            "correct_query":  "SELECT name FROM users WHERE age > 18",
            "expected_output": [],
        },
        # ORDER BY with no column
        {
            "broken_query":   "SELECT age FROM users ORDER",
            "correct_query":  "SELECT age FROM users ORDER BY age",
            "expected_output": [(18,)],
        },
        # WHERE value missing for string column
        {
            "broken_query":   "SELECT * FROM users WHERE name =",
            "correct_query":  "SELECT * FROM users WHERE name = 'A'",
            "expected_output": [(1, "A", 18)],
        },
        # COUNT with incomplete WHERE
        {
            "broken_query":   "SELECT COUNT(*) FROM users WHERE age >",
            "correct_query":  "SELECT COUNT(*) FROM users WHERE age > 10",
            "expected_output": [(1,)],
        },
        # ORDER BY name missing column
        {
            "broken_query":   "SELECT name FROM users ORDER",
            "correct_query":  "SELECT name FROM users ORDER BY name",
            "expected_output": [("A",)],
        },
        # Missing LIMIT value
        {
            "broken_query":   "SELECT * FROM users LIMIT",
            "correct_query":  "SELECT * FROM users LIMIT 1",
            "expected_output": [(1, "A", 18)],
        },
        # WHERE with wrong operator spacing
        {
            "broken_query":   "SELECT name FROM users WHERE age =",
            "correct_query":  "SELECT name FROM users WHERE age = 18",
            "expected_output": [("A",)],
        },
    ]

    if not hasattr(get_task, "index"):
        get_task.index = 0

    task = tasks[get_task.index % len(tasks)]
    get_task.index += 1

    return {
        "broken_query":   task["broken_query"],
        "correct_query":  task["correct_query"],
        "expected_output": task["expected_output"],
        "schema": "users(id INT, name TEXT, age INT)",
    }