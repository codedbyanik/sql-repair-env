def get_task():
    """
    Easy tasks: single-clause errors — missing comma, typo in keyword,
    wrong keyword (FORM vs FROM), missing column alias comma.
    All expected_output values assume table: users(1, 'A', 18).
    """
    tasks = [
        # Missing comma between columns
        {
            "broken_query":   "SELECT name age FROM users",
            "correct_query":  "SELECT name, age FROM users",
            "expected_output": [("A", 18)],
        },
        # Typo: FORM instead of FROM
        {
            "broken_query":   "SELECT * FORM users",
            "correct_query":  "SELECT * FROM users",
            "expected_output": [(1, "A", 18)],
        },
        # Typo: SELCET instead of SELECT
        {
            "broken_query":   "SELCET name FROM users",
            "correct_query":  "SELECT name FROM users",
            "expected_output": [("A",)],
        },
        # Stray comma after column, before FROM
        {
            "broken_query":   "SELECT age, FORM users",
            "correct_query":  "SELECT age FROM users",
            "expected_output": [(18,)],
        },
        # Missing comma between id and name
        {
            "broken_query":   "SELECT id name FROM users",
            "correct_query":  "SELECT id, name FROM users",
            "expected_output": [(1, "A")],
        },
        # Wrong table keyword: FORM users
        {
            "broken_query":   "SELECT id age FORM users",
            "correct_query":  "SELECT id, age FROM users",
            "expected_output": [(1, 18)],
        },
        # Missing comma between three columns
        {
            "broken_query":   "SELECT id name age FROM users",
            "correct_query":  "SELECT id, name, age FROM users",
            "expected_output": [(1, "A", 18)],
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