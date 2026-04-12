def normalize(query):
    return query.lower().replace(" ", "").replace(";", "")

class grade:
    def grade(self, submission=None, predicted=None, expected_query=None,
              result=None, expected=None, error=None, **kwargs):
        if submission is None and predicted is None:
            return 0.5
        if error:
            return 0.05
        if predicted and expected_query:
            if normalize(str(predicted)) == normalize(str(expected_query)):
                return 0.95
        if result is not None and expected is not None:
            if result == expected:
                return 0.8
        if predicted and "select" in str(predicted).lower():
            return 0.3
        return 0.05
