import asyncio
import httpx
import pytest
from load_balancer.proxy import forward_request, ProxyError
from load_balancer.models import Backend, WorkRequest

B=Backend("A","http://backend")
R=WorkRequest(request_id="req-1",key="user-1")

def execute(handler):
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await forward_request(client,B,R,.1)
    return asyncio.run(scenario())

def test_forward_real_payload_contract():
    def handler(request):
        assert request.method == "POST" and request.url.path == "/work"
        return httpx.Response(200,json={**R.model_dump(),"backend_id":"A","processing_ms":100})
    assert execute(handler)["backend_id"] == "A"

@pytest.mark.parametrize("kind,status", [("timeout",504),("connect",502),("upstream",502),("malformed",502),("wrong_id",502)])
def test_failures_no_retry(kind,status):
    calls=[]
    def handler(request):
        calls.append(request)
        if kind == "timeout": raise httpx.ReadTimeout("timeout")
        if kind == "connect": raise httpx.ConnectError("refused")
        if kind == "upstream": return httpx.Response(503)
        if kind == "malformed": return httpx.Response(200,text="not json")
        return httpx.Response(200,json={**R.model_dump(),"backend_id":"B","processing_ms":1})
    with pytest.raises(ProxyError) as err:
        execute(handler)
    assert err.value.status == status
    assert len(calls) == 1

def test_total_deadline():
    async def handler(request):
        await asyncio.sleep(.2)
        return httpx.Response(200,json={**R.model_dump(),"backend_id":"A","processing_ms":1})
    with pytest.raises(ProxyError) as err:
        execute(handler)
    assert err.value.status == 504
