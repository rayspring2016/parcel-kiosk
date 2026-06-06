from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import init_db
from routers import scan, pickup, unclaimed

app = FastAPI(title="Parcel Kiosk API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产部署改为 Kiosk 实际 origin
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(scan.router)
app.include_router(pickup.router)
app.include_router(unclaimed.router)


@app.on_event("startup")
async def on_startup():
    init_db()
    from scheduler import start_scheduler
    start_scheduler()


@app.get("/health")
def health():
    try:
        from scheduler import scheduler
        jobs = [{"id": j.id, "next_run": str(j.next_run_time)} for j in scheduler.get_jobs()]
    except Exception:
        jobs = []
    return {"status": "ok", "scheduler_jobs": jobs}
