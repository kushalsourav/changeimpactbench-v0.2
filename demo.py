#!/usr/bin/env python3
"""Local grader walk-through using a reference answer and invented WRONG answer.

Never present this as an AI-model experiment; it makes no API calls.
"""

import json
from tasks import load_cases
from oracle import reference_answer, reference_audit
from grader import grade

case = load_cases({"T05"})[0]
truth = reference_answer(case)
print("OFFLINE DEMONSTRATION (not a model result)")
print("CASE:", case["id"], case["title"])
print("Reference:", json.dumps(truth, indent=2))
print("Reference grade:", json.dumps(grade(json.dumps(truth), truth), indent=2))
wrong = dict(truth)
wrong["fix_id"] = "A01"  # tempting global rollback breaks healthy east sensors
print("Deliberately wrong answer:", json.dumps(wrong, indent=2))
print("Wrong grade:", json.dumps(grade(json.dumps(wrong), truth), indent=2))
print("Counterfactual action audit:", json.dumps(reference_audit(case)["actions"], indent=2))
