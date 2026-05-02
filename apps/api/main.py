from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.database import init_db
from app.routers.battlecard import router as battlecard_router
from app.routers.health import router as health_router
from app.utils.logging import configure_logging


configure_logging()
app = FastAPI(title="Battlecard Generator API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    init_db()


app.include_router(health_router)
app.include_router(battlecard_router)
