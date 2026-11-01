## Summary

<!-- Explain the change and reference `Closes #<issue-number>` if this completes a roadmap item. -->

## Invariant check

- [ ] Dry-run never writes; working tree untouched until verification passes
- [ ] Every new fixable rule or verdict path is covered by `audit_patch()` and unit tests
- [ ] Offline mock evaluation (`python eval/run_eval.py --provider mock`) passes without an API key

## Local verification

```bash
ruff check .
ruff format --check .
mypy src --strict
pytest
python eval/run_eval.py --provider mock
```
