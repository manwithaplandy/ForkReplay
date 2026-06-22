"""FastAPI entrypoint for the ForkReplay control plane."""
from fastapi import FastAPI

app = FastAPI(title="ForkReplay API")


@app.get("/health")
async def health() -> dict[str, bool]:
    return {"ok": True}
