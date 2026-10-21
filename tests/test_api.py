import asyncio
import copy
import json
from pathlib import Path
import httpx
from load_balancer.app import create_app

CONFIG=json.loads((Path(__file__).resolve().parents[1]/"config.json").read_text())
def test_api_full_flow_and_controls():
    async def scenario():
        def upstream(request):
            backend = {9001:"A",9002:"B",9003:"C"}[request.url.port]
            if request.url.path == "/health":
                return httpx.Response(200,json={"backend_id":backend,"status":"healthy"})
            if request.url.path == "/admin/delay":
                return httpx.Response(200,json={"backend_id":backend,"delay_ms":2000})
            data=json.loads(request.content)
            return httpx.Response(200,json={**data,"backend_id":backend,"processing_ms":1})
        app=create_app(copy.deepcopy(CONFIG),False,httpx.MockTransport(upstream))
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test") as client:
                for b in "ABC":
                    app.state.registry.record(b,True);app.state.registry.record(b,True)
                results=[await client.post("/api/work",json={"request_id":str(i),"key":"same"}) for i in range(12)]
                assert [r.json()["backend_id"] for r in results] == list("ABC"*4)
                metrics=(await client.get("/api/metrics")).json()
                assert metrics["success"] == 12 and metrics["active"] == 0
                assert all(b["assigned"] == 4 for b in metrics["backends"].values())
                assert (await client.put("/api/algorithm",json={"algorithm":"consistent_hash","virtual_nodes":100})).status_code == 200
                results=[await client.post("/api/work",json={"request_id":str(i),"key":"same"}) for i in range(5)]
                assert len({r.json()["backend_id"] for r in results}) == 1
                assert (await client.get("/api/hash-ring")).json()["nodes"]
                assert (await client.get("/api/mapping-comparison")).json()["keys"] == 1000
                assert (await client.post("/api/backends/A/delay",json={"delay_ms":2000})).status_code == 200
                assert (await client.post("/api/backends/A/process/stop")).status_code == 409
                assert (await client.post("/api/work",json={})).status_code == 422
                assert (await client.post("/api/metrics/reset",headers={"origin":"https://evil.example"})).status_code == 403
                for b in "ABC":
                    app.state.registry.record(b,False);app.state.registry.record(b,False)
                response=await client.post("/api/work",json={"request_id":"empty","key":"same"})
                assert response.status_code == 503
                assert (await client.get("/api/metrics")).json()["active"] == 0
    asyncio.run(scenario())

def test_reset_and_algorithm_change_rejected_during_work():
    async def scenario():
        entered, release = asyncio.Event(), asyncio.Event()
        async def upstream(request):
            if request.url.path=="/health":
                return httpx.Response(200,json={"backend_id":"A","status":"healthy"})
            entered.set()
            await release.wait()
            return httpx.Response(200,json={**json.loads(request.content),"backend_id":"A","processing_ms":1})
        app=create_app(copy.deepcopy(CONFIG),False,httpx.MockTransport(upstream))
        async with app.router.lifespan_context(app):
            app.state.registry.record("A",True);app.state.registry.record("A",True)
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test") as client:
                task=asyncio.create_task(client.post("/api/work",json={"request_id":"1","key":"key"}))
                await entered.wait()
                assert (await client.post("/api/metrics/reset")).status_code == 409
                assert (await client.put("/api/algorithm",json={"algorithm":"round_robin"})).status_code == 409
                release.set()
                assert (await task).status_code == 200
    asyncio.run(scenario())
