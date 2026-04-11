def normalize(query):
    return query.lower().replace(" ", "").replace(";", "")


def grade(predicted=None, expected_query=None, result=None, expected=None, error=None, **kwargs):
    if error:
        return 0.05

    if predicted and expected_query:
        if normalize(predicted) == normalize(expected_query):
            return 0.95

    if result is not None and expected is not None:
        if result == expected:
            return 0.8

    if predicted and "select" in str(predicted).lower():
        return 0.3

    return 0.05