"""Reviewed project data for the shared Workspace flow."""
from pathlib import Path

from .workspace import ImportProject, PlanDraft


ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "workspace"


def inventory_case(stock, order, ok, after):
    return {"input": {"stock": stock, "order": order}, "expected": {"ok": ok, "stock": after}}


def log_case(lines, start, end, info, warn, error, invalid):
    return {"input": {"lines": lines, "start": start, "end": end},
            "expected": {"counts": {"INFO": info, "WARN": warn, "ERROR": error}, "invalid": invalid}}


SAMPLES = {
    "inventory": ("inventory.py", "rules.py",
                  "Validate positive quantities and aggregate duplicate SKUs. Reject invalid or insufficient orders "
                  "without changing any stock. Reject negative stock. Return ok and the resulting stock.",
                  [inventory_case({"a": 3, "b": 0}, [["a", 1], ["b", 1]], False, {"a": 3, "b": 0}),
                   inventory_case({"a": 5}, [["a", 1], ["a", 2]], True, {"a": 2})],
                  [inventory_case({"a": 4, "b": -1}, [["a", 1]], False, {"a": 4, "b": -1}),
                   inventory_case({"a": 8}, [["a", -1]], False, {"a": 8}),
                   inventory_case({"a": 2, "b": 5}, [["a", 1], ["b", 2], ["a", 2]], False, {"a": 2, "b": 5})]),
    "logs": ("logs.py", "format_rules.py",
             "Count only the parsed log level inside [start, end). Count malformed lines separately. "
             "Always return INFO, WARN and ERROR counts, including zeros.",
             [log_case(["10 INFO contains ERROR", "20 ERROR end"], 10, 20, 1, 0, 0, 0),
              log_case(["broken", "11 WARN notice"], 10, 20, 0, 1, 0, 1)],
             [log_case(["0 ERROR early", "1 ERROR real", "4 INFO late", "2 DEBUG unknown"], 1, 4, 0, 0, 1, 1),
              log_case(["1 WARN one", "2 WARN two"], 1, 1, 0, 0, 0, 0)]),
}


def sample(sample_id):
    entry, helper, goal, public, acceptance = SAMPLES[sample_id]
    root = ROOT / sample_id
    project = ImportProject(files=[{"path": name, "content": (root / name).read_text(encoding="utf-8")}
                                   for name in (entry, helper, "README.md")])
    plan = PlanDraft(revision=0, goal=goal, entrypoint=f"{entry}:solve", allowed_write_paths=[entry],
                     public_cases=public, acceptance_cases=acceptance, reference_profile=sample_id,
                     implementation=["Inspect the entry function against the reference rule", "Fix the allowed file and run distinct acceptance cases"],
                     constraints=["Only change the approved entry file; no network or new dependencies"],
                     risks=["Boundary inputs must agree with the independent registered reference"],
                     acceptance_basis="Expected values are derived from the registered reference profile: " + sample_id)
    return project, plan, {entry: (root / "fixed.txt").read_text(encoding="utf-8")}
