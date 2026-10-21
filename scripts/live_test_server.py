"""Helper dành cho verify_live.py, dừng uvicorn có trật tự qua stop file."""
import asyncio
from pathlib import Path
import sys
import uvicorn

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

async def main():
    server=uvicorn.Server(uvicorn.Config("load_balancer.app:app",host="127.0.0.1",
        port=int(sys.argv[1]),log_level="warning",access_log=False))
    async def monitor():
        while not Path(sys.argv[2]).exists():
            await asyncio.sleep(.1)
        server.should_exit=True
    monitor_task=asyncio.create_task(monitor())
    try:
        await server.serve()
    finally:
        monitor_task.cancel()

if __name__=="__main__":
    asyncio.run(main())
