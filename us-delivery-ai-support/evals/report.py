"""Report generation for the Task 3 evaluation harness (JSON + Markdown)."""

from __future__ import annotations

import json
from pathlib import Path

from app.schemas import EvalReport


def model_to_dict(obj) -> dict:
    """Convert a Pydantic model (v2 or v1) or plain dict into a dict."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict") and callable(getattr(obj, "dict")):
        return obj.dict()
    if isinstance(obj, dict):
        return obj
    raise TypeError(f"Cannot convert {type(obj).__name__} to dict")


def write_json_report(report: EvalReport, path: str | Path) -> None:
    """Write *report* as pretty-printed UTF-8 JSON, creating parent dirs."""
    path = Path(path)
    if path.parent and not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
    data = model_to_dict(report)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def escape_markdown_table_cell(value) -> str:
    """Make *value* safe inside a Markdown table cell."""
    text = str(value)
    text = text.replace("|", "\\|")
    text = text.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
    return text


def write_markdown_report(report: EvalReport, path: str | Path) -> None:
    """Write *report* as a Markdown summary plus a results table."""
    path = Path(path)
    if path.parent and not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)

    data = model_to_dict(report)
    lines: list[str] = []
    lines.append("# Evaluation Report")
    lines.append("")
    lines.append(f"Generated at: {data.get('generated_at')}")
    lines.append(f"Dataset ready: {str(bool(data.get('dataset_ready'))).lower()}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---:|")
    lines.append(f"| Total cases | {data.get('total_cases')} |")
    lines.append(f"| Passed | {data.get('passed_cases')} |")
    lines.append(f"| Failed | {data.get('failed_cases')} |")
    lines.append(f"| Average score | {data.get('average_score')} |")
    lines.append("")
    lines.append("## Results")
    lines.append("")
    lines.append("| ID | Task | Name | Passed | Score | Adversarial | Notes |")
    lines.append("|---|---|---|---:|---:|---:|---|")
    for result in data.get("results", []):
        notes = "; ".join(result.get("notes", []) or [])
        lines.append(
            "| "
            + " | ".join(
                [
                    escape_markdown_table_cell(result.get("id")),
                    escape_markdown_table_cell(result.get("task")),
                    escape_markdown_table_cell(result.get("name")),
                    escape_markdown_table_cell(str(bool(result.get("passed"))).lower()),
                    escape_markdown_table_cell(result.get("score")),
                    escape_markdown_table_cell(
                        str(bool(result.get("adversarial"))).lower()
                    ),
                    escape_markdown_table_cell(notes),
                ]
            )
            + " |"
        )
    lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
