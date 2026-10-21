import pytest
from load_balancer.metrics import MetricsCollector
from load_balancer.models import WorkRequest

def test_bounded_logs_and_full_counters():
    m=MetricsCollector(["A"],2)
    for i in range(5):
        event=m.begin(WorkRequest(request_id=str(i),key="x"),"round_robin")
        m.assign(event,"A")
        m.finish(event,200)
    result=m.snapshot()
    assert len(result["logs"]) == result["p95_sample_size"] == 2
    assert result["total"] == result["success"] == 5
    assert result["backends"]["A"]["assigned"] == 5

def test_active_reset_rejected_and_error_accounted():
    m=MetricsCollector(["A"])
    e=m.begin(WorkRequest(request_id="1",key="x"),"round_robin")
    with pytest.raises(ValueError): m.reset()
    m.finish(e,503,"no backend")
    assert m.snapshot()["errors"] == 1
    assert m.snapshot()["active"] == 0
    m.reset()
    assert m.snapshot()["total"] == 0
