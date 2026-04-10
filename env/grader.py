def normalize(query: str) -> str:
    """Normalize SQL for comparison: lowercase, strip spaces and semicolons."""
    return query.lower().strip().replace(" ", "").replace(";", "")


def grade(predicted: str, expected_query: str, result, expected, error=None) -> float:
    """
    Score a predicted SQL query against the expected query and output.
    Reward tiers:
        1.0  — Exact query match (normalized)
        0.8  — Output rows match expected (semantically correct)
        0.3  — Valid SELECT structure but wrong output
        0.0  — Syntax error or no SELECT present
    """
    # Syntax error → immediate 0
    if error:
        return 0.0

    # Tier 1: Exact query match
    if normalize(predicted) == normalize(expected_query):
        return 1.0

    # Tier 2: Output matches expected (semantically correct even if phrased differently)
    if result is not None and result == expected:
        return 0.8

    # Tier 3: At least a structurally valid SELECT (partial credit)
    if predicted and "select" in predicted.lower():
        return 0.3

    return 0.0