# Submission Checklist

## Deliverables

- [ ] Official dataset placed in `data/` and `knowledge-base/`
- [ ] `.env` exists locally but is not tracked
- [ ] `.env.example` contains placeholders only
- [ ] `pip install -r requirements.txt` works
- [ ] `python run.py` starts API
- [ ] `/health` works
- [ ] `/dataset/status` checked
- [ ] Task 1 sample run works
- [ ] Task 2 sample run works with official account ID
- [ ] `python -m evals.run_evals` generates report
- [ ] `eval_report.json` or `eval_report.md` committed
- [ ] README complete
- [ ] `DESIGN_NOTE.md` complete
- [ ] Loom 3–6 min recorded
- [ ] No real API key committed

## Before-Push Commands

Run all of these and confirm the expected results before pushing:

```bash
python scripts/check_secrets.py
pytest
python -m compileall app evals tests ui scripts
python -m evals.run_evals
python scripts/final_validate.py
git status
git check-ignore -v .env
git ls-files .env
```

Expected:

- No `.env` tracked (`git ls-files .env` prints nothing).
- No secrets detected (`check_secrets.py` exits 0).
- Eval report exists (`eval_report.json` / `eval_report.md`).
- `.env` is ignored (`git check-ignore -v .env` shows a match).
