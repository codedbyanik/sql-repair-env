## 🧠 Environment Specification

### Observation
- broken_query: incorrect SQL query
- db_schema: database schema
- difficulty: easy / medium / hard
- result: execution output
- error: error message

### Action
- query: corrected SQL query

### Reward
- 1.0 → exact match
- 0.8 → correct output
- 0.3 → partial fix
- 0.0 → incorrect