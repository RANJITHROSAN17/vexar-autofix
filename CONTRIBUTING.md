# Contributing to vexar-autofix

Every open task in this repository comes from [`.github/roadmap.json`](.github/roadmap.json), which mirrors [`ROADMAP.md`](ROADMAP.md). When an issue closes, the **Roadmap Curator Bot** automatically opens the next queued item.

## Local setup & gates

```bash
python -m pip install -e ".[dev]"
ruff check .
ruff format --check .
mypy src --strict
pytest
python eval/run_eval.py --provider mock
```

No live LLM API key is required for unit tests or offline evaluation (`--provider mock`).

## Seven invariants that must never regress

1. A dry run never writes to disk.
2. A rule with no mechanical remedy is refused, never attempted.
3. Every finding receives a verdict and a bucket.
4. A patch that trades one finding for another is rejected.
5. Moving a sink to a new line is not counted as a fix.
6. Line-number shifts are never misread as new findings.
7. The working tree stays untouched until verification passes.
