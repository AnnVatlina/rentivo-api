from fastapi import FastAPI

from app.routers import analytics, auth, deposits, export_import, subscriptions

app = FastAPI(title="Rentivo API", version="1.0.0")

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(deposits.router, prefix="/deposits", tags=["deposits"])
app.include_router(subscriptions.router, prefix="/subscriptions", tags=["subscriptions"])
app.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
app.include_router(export_import.router, tags=["export/import"])


@app.get("/health")
async def health():
    return {"status": "ok"}
