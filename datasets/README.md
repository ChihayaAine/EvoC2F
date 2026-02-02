# Datasets

Place evaluation datasets and processed traces here. This keeps training and
evaluation data separate from core framework logic.

Suggested layout:
- `raw/`: downloaded or original datasets
- `processed/`: normalized jsonl with `task`, `input`, `output`
- `traces/`: execution traces for skill mining/verification

Each jsonl line should include:
```
{"task": "...", "input": {...}, "output": {...}, "metadata": {...}}
```

