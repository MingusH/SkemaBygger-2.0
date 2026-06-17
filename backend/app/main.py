from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import auth, schools, teachers, rooms, subjects, classes, assignments, constraints, timeslots, schedules
from app.routers.special_events import router as special_events_router, time_bank_router
from app.routers.elective_bands import router as elective_bands_router
from app.routers.oauth_login import router as oauth_login_router
from app.mcp_server import mcp

# Serve the authenticated MCP server from this same FastAPI app (one service, one port).
# The MCP endpoint is /mcp; OAuth discovery (/.well-known/...) and the /authorize, /token,
# /register endpoints sit at the ROOT, so the app is mounted at "/" (see bottom of file).
# Its lifespan MUST be attached to FastAPI or the streamable-HTTP session manager never starts.
mcp_app = mcp.http_app(path="/mcp")

app = FastAPI(title="SkemaBygger API", version="0.1.0", lifespan=mcp_app.lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(schools.router, prefix="/api")
app.include_router(teachers.router, prefix="/api")
app.include_router(rooms.router, prefix="/api")
app.include_router(subjects.router, prefix="/api")
app.include_router(classes.router, prefix="/api")
app.include_router(assignments.router, prefix="/api")
app.include_router(constraints.router, prefix="/api")
app.include_router(timeslots.router, prefix="/api")
app.include_router(schedules.router, prefix="/api")
app.include_router(special_events_router, prefix="/api")
app.include_router(time_bank_router, prefix="/api")
app.include_router(elective_bands_router, prefix="/api")
# OAuth login page (browser-facing, not under /api).
app.include_router(oauth_login_router)


@app.get("/health")
def health():
    return {"status": "ok"}


# Mount the MCP + OAuth app LAST, at root, so its /.well-known, /authorize, /token,
# /register land at the site root (where OAuth clients discover them) and the MCP
# endpoint at /mcp. Explicit routes above are matched first; everything else falls here.
app.mount("/", mcp_app)
