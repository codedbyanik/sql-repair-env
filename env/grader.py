def normalize(query):
    return query.lower().replace(" ", "").replace(";", "")


def grade(predicted, expected_query, result, expected, error=None):
    if error:
        return 0.05  # syntax error — low but not 0.0

    # Exact query match
    if normalize(predicted) == normalize(expected_query):
        return 0.95  # perfect fix — high but not 1.0

    # Correct output match (semantically correct)
    if result == expected:
        return 0.8

    # Partial signal (has SELECT structure)
    if "select" in predicted.lower():
        return 0.3

    return 0.05  # completely wrong but not 0.0