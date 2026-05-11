from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import analytics, auth, deposits, export_import, properties, settings, subscriptions

app = FastAPI(title="Rentivo API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(settings.router, prefix="/settings", tags=["settings"])
app.include_router(deposits.router, prefix="/deposits", tags=["deposits"])
app.include_router(subscriptions.router, prefix="/subscriptions", tags=["subscriptions"])
app.include_router(properties.router, prefix="/properties", tags=["properties"])
app.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
app.include_router(export_import.router, tags=["export/import"])


@app.get("/health")
async def health():
    return {"status": "ok"}
