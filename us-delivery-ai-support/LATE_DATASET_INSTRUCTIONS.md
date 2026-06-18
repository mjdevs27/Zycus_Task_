# Late Dataset Instructions

Follow these steps once the official starter-repo dataset becomes available.

1. Copy official `tickets.json` to `data/tickets.json`.
2. Copy official `accounts.json` to `data/accounts.json`.
3. Copy official Markdown KB docs into `knowledge-base/`.
4. Run `python -m evals.run_evals`.
5. Run `python scripts/final_validate.py --strict`.
6. Run the API and test Task 1 / Task 2 with actual IDs.
7. Update the README sample account ID **only** if it comes from the official dataset.
8. Re-record the Loom if needed.

## Rules

- Do not create replacement data.
- Do not use external data.
- Do not commit `.env`.

Until the official files are present, data-dependent features return clear
dataset-readiness errors and the eval report shows `dataset_ready=false`. This is
intended behavior, not a bug.
