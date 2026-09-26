import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from dotenv import load_dotenv

from .database import engine
from .routes import events, cameras, vehicles, traffic, alerts

load_dotenv()

app = FastAPI(title="IDAHR API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(events.router)
app.include_router(cameras.router)
app.include_router(vehicles.router)
app.include_router(traffic.router)
app.include_router(alerts.router)

@app.on_event("startup")
async def startup_event():
    async with engine.begin() as conn:
        result = await conn.execute(text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema='public' AND table_name='cameras')"))
        exists = result.scalar()
        if not exists:
            schema_path = Path(__file__).resolve().parent.parent.parent / 'db_schema.sql'
            if schema_path.exists():
                sql = schema_path.read_text()
                for statement in sql.split(';'):
                    statement = statement.strip()
                    if statement:
                        await conn.execute(text(statement))
