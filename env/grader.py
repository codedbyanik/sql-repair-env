def normalize(query):
    return query.lower().replace(" ", "").replace(";", "")


def grade(predicted, expected_query, result, expected, error=None):
    if error:
        return 0.0  # syntax error

    # ✅ Exact query match
    if normalize(predicted) == normalize(expected_query):
        return 1.0

    # ✅ Correct output match
    if result == expected:
        return 0.8

    # ✅ Partial signal (structure)
    if "select" in predicted.lower():
        return 0.3

    return 0.0
