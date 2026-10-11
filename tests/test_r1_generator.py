from __future__ import annotations

from scripts.generate_r1_instance import build_candidate
from jev_rbp.r1_design_checker import check_instance


def test_structured_candidate_passes_static_design_gate(tmp_path):
    candidate = tmp_path / "candidate"
    build_candidate(seed=20261009, output=candidate)

    report = check_instance(candidate, include_dynamic=False)

    assert report.status == "PASS", [
        (check.name, check.status, check.message)
        for check in report.checks
        if check.status != "PASS"
    ]
    checks = {check.name: check for check in report.checks}
    assert checks["demand_market_structure"].details["competing_hub_demands"] >= 4
    assert checks["direct_only_demands"].status == "PASS"


def test_full_checker_keeps_dynamic_evidence_as_a_separate_gate(tmp_path):
    candidate = tmp_path / "candidate"
    build_candidate(seed=20261009, output=candidate)

    report = check_instance(candidate)

    assert report.status == "INCOMPLETE"
    assert {f"P{i}" for i in range(1, 8)}.issubset(
        {check.name for check in report.checks}
    )
