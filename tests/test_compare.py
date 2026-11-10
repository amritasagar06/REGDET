from regdet.compare import check_drift, compare, sign_test_p
from regdet.models import CaseResult, RunRecord


def make_run(passes: list[bool], rid="r") -> RunRecord:
    cats = ["billing", "technical", "account", "general"]
    rs = [CaseResult(case_id=f"c{i}", expected_category=cats[i % 4], predicted_category="x", passed=p)
          for i, p in enumerate(passes)]
    return RunRecord(run_id=rid, prompt_version="v", model="m", provider="mock",
                     dataset_version="1", timestamp="t", results=rs)


def test_identical_runs_pass():
    c = compare(make_run([True] * 50), make_run([True] * 50))
    assert c.status == "pass" and not c.regressions


def test_small_drop_warns():
    base = make_run([True] * 100)
    cur = make_run([False] * 5 + [True] * 95)   # -5% -> warning (3% < 5% <= 8%)
    assert compare(cur, base).status == "warning"


def test_big_drop_is_critical_and_lists_regressions():
    base = make_run([True] * 50)
    cur = make_run([False] * 10 + [True] * 40)  # -20%
    c = compare(cur, base)
    assert c.status == "critical" and len(c.regressions) == 10


def test_improvements_detected():
    c = compare(make_run([True] * 10), make_run([False] * 5 + [True] * 5))
    assert len(c.improvements) == 5 and c.status == "pass"


def test_thresholds_configurable():
    base, cur = make_run([True] * 100), make_run([False] * 5 + [True] * 95)
    assert compare(cur, base, warn=0.10, crit=0.20).status == "pass"


def test_sign_test():
    assert sign_test_p(0, 0) == 1.0
    assert sign_test_p(10, 0) < 0.01
    assert sign_test_p(3, 3) == 1.0


def test_drift():
    assert not check_drift([0.9] * 3, window=7)["enough_data"]
    assert check_drift([0.8] * 7, window=7, floor=0.85)["warning"]
    assert not check_drift([0.95] * 7, window=7, floor=0.85)["warning"]
