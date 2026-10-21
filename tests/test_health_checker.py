import asyncio
import httpx
from load_balancer.models import Backend
from load_balancer.registry import BackendRegistry
from load_balancer.health_checker import check_once

def test_thresholds_and_recovery():
    reg=BackendRegistry([Backend("A","http://A")],2,2)
    assert not reg.healthy_backends()
    reg.record("A",True)
    assert not reg.healthy_backends()
    reg.record("A",True)
    assert len(reg.healthy_backends()) == 1
    reg.record("A",False)
    assert len(reg.healthy_backends()) == 1
    reg.record("A",False)
    assert not reg.healthy_backends()
    reg.record("A",True)
    assert not reg.healthy_backends()
    reg.record("A",True)
    assert len(reg.healthy_backends()) == 1

def test_failure_resets_success_streak():
    reg=BackendRegistry([Backend("A","http://A")],2,2)
    for success in [True,False,True]:
        reg.record("A",success)
    assert reg.states["A"]["status"] == "unknown"

def test_http_health_validates_identity_and_timeout():
    async def scenario():
        reg=BackendRegistry([Backend(x,f"http://{x}") for x in "ABC"],1,1)
        def handler(request):
            if request.url.host.lower() == "a":
                return httpx.Response(200,json={"backend_id":"A","status":"healthy"})
            if request.url.host.lower() == "b":
                return httpx.Response(200,json={"backend_id":"WRONG","status":"healthy"})
            raise httpx.ReadTimeout("timeout")
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await check_once(reg,client,.1)
        assert [b.id for b in reg.healthy_backends()] == ["A"]
        assert reg.states["C"]["last_error"] == "ReadTimeout"
    asyncio.run(scenario())
