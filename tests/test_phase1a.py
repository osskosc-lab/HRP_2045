from experiments.phase1a.run_phase1a import run_experiment


def test_phase1a_smoke_zero_defect_rule():
    result = run_experiment(3)
    assert result["decision"] == "NOT_FALSIFIED_PHASE1A"
    assert result["failure_count"] == 0
    assert result["endpoints"]["unauthenticated_manifest_acceptance_rate"] == 0.0
    assert result["endpoints"]["alternate_root_false_rendezvous_rate"] == 0.0
