"""
JobBuddy eval runner.
Usage: start the server (uvicorn main:app --reload), then:
    python evals/run_evals.py
"""

import json
import sys
import time
from pathlib import Path

import requests

BASE_URL = "http://localhost:8000"
CASES_PATH = Path(__file__).parent / "cases.json"


def check_analyze(result: dict, expect: dict) -> list[str]:
    """Return a list of failure messages (empty list = pass)."""
    failures = []
    score = result.get("match_score")

    if not isinstance(score, int):
        failures.append(f"match_score is not an integer: {score!r}")
        return failures  # can't do range checks without a number

    if "score_min" in expect and score < expect["score_min"]:
        failures.append(f"score {score} below expected min {expect['score_min']}")
    if "score_max" in expect and score > expect["score_max"]:
        failures.append(f"score {score} above expected max {expect['score_max']}")

    missing = " ".join(result.get("missing_skills", [])).lower()
    matching = " ".join(result.get("matching_skills", [])).lower()

    for skill in expect.get("missing_skills_must_not_include", []):
        if skill.lower() in missing:
            failures.append(f"'{skill}' wrongly listed as missing")

    wanted = expect.get("missing_skills_must_include_any", [])
    if wanted and not any(s.lower() in missing for s in wanted):
        failures.append(f"none of {wanted} found in missing_skills")

    wanted = expect.get("matching_skills_must_include_any", [])
    if wanted and not any(s.lower() in matching for s in wanted):
        failures.append(f"none of {wanted} found in matching_skills")

    return failures


def check_tailor(result: dict, expect: dict) -> list[str]:
    failures = []
    tailored = result.get("tailored_resume", "").lower()
    gaps = " ".join(result.get("honest_gaps", [])).lower()
    new_score = result.get("new_score")

    for term in expect.get("tailored_must_not_contain", []):
        if term.lower() in tailored:
            failures.append(f"FABRICATION: '{term}' appeared in tailored resume")

    wanted = expect.get("tailored_must_contain_any", [])
    if wanted and not any(t.lower() in tailored for t in wanted):
        failures.append(f"none of {wanted} found in tailored resume")

    wanted = expect.get("honest_gaps_must_include_any", [])
    if wanted and not any(g.lower() in gaps for g in wanted):
        failures.append(f"none of {wanted} found in honest_gaps")

    if "new_score_min" in expect:
        if not isinstance(new_score, int) or new_score < expect["new_score_min"]:
            failures.append(f"new_score {new_score} below expected min {expect['new_score_min']}")

    return failures


def run_case(case: dict) -> tuple[bool, list[str], float]:
    endpoint = "/tailor-resume" if case.get("endpoint") == "tailor" else "/analyze"
    payload = {"resume": case["resume"], "job_description": case["job_description"]}

    start = time.time()
    try:
        resp = requests.post(BASE_URL + endpoint, json=payload, timeout=120)
    except requests.ConnectionError:
        return False, ["cannot reach server - is uvicorn running?"], 0.0
    elapsed = time.time() - start

    if resp.status_code != 200:
        return False, [f"HTTP {resp.status_code}: {resp.text[:200]}"], elapsed

    result = resp.json()
    checker = check_tailor if case.get("endpoint") == "tailor" else check_analyze
    failures = checker(result, case["expect"])
    return len(failures) == 0, failures, elapsed


def main():
    cases = json.loads(CASES_PATH.read_text())
    passed = 0
    print(f"\nRunning {len(cases)} eval cases against {BASE_URL}\n" + "=" * 60)

    for case in cases:
        ok, failures, elapsed = run_case(case)
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {case['id']}  ({elapsed:.1f}s)")
        for f in failures:
            print(f"       - {f}")
        if ok:
            passed += 1

    print("=" * 60)
    print(f"Result: {passed}/{len(cases)} passed\n")
    sys.exit(0 if passed == len(cases) else 1)


if __name__ == "__main__":
    main()