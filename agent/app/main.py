from __future__ import annotations

from fastapi import FastAPI, Request
from pydantic import BaseModel

from .auth import require_user
from .graph import build_graph

app = FastAPI(title="Agent")
graph = build_graph()


class RunReq(BaseModel):
    task: str = "whoami"


@app.post("/run")
async def run(req: RunReq, request: Request):
    sub, access_token = require_user(request)
    # Pass access_token into the graph state
    result = await graph.ainvoke({"task": req.task, "access_token": access_token})
    return {"user": sub, "result": result}
