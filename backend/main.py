# backend/main.py
import os
from dotenv import load_dotenv
load_dotenv()  # Load .env BEFORE any google-adk/genai imports read env vars

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from pydantic import BaseModel
from google.adk.runners import Runner
from google.adk.sessions import VertexAiSessionService
from google.adk.memory import InMemoryMemoryService
from google.genai import types
from agent import github_card_agent

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Services
session_service = VertexAiSessionService()
memory_service = InMemoryMemoryService()

runner = Runner(
    app_name="github-card-generator",
    agent=github_card_agent,
    session_service=session_service,
    memory_service=memory_service,
)

# Use absolute path — matches the absolute path save_card uses in mcp_server.py
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
CARDS_DIR = os.path.join(BACKEND_DIR, "static", "cards")
os.makedirs(CARDS_DIR, exist_ok=True)

class GenerateRequest(BaseModel):
    username: str
    force_refresh: bool = False

@app.post("/generate")
async def generate_card(req: GenerateRequest):
    try:
        # ✅ Cache check — skip Gemini if card already exists (unless forced)
        card_path = os.path.join(CARDS_DIR, f"{req.username}.html")
        if not req.force_refresh and os.path.exists(card_path):
            return {"card_url": f"/card/{req.username}", "message": "Card loaded from cache."}

        session = await session_service.create_session(
            app_name="github-card-generator", user_id=req.username
        )
        content = types.Content(role="user", parts=[types.Part(text=f"Generate a dev card for {req.username}")])
        final_response = ""
        async for event in runner.run_async(
            user_id=req.username, session_id=session.id, new_message=content
        ):
            if event.is_final_response() and event.content:
                final_response = event.content.parts[0].text
        return {"card_url": f"/card/{req.username}", "message": final_response}
    except Exception as e:
        err = str(e)
        if "429" in err or "RESOURCE_EXHAUSTED" in err or "quota" in err.lower():
            return JSONResponse(status_code=429, content={
                "detail": "⚠️ Gemini API free tier quota exceeded (20 req/day). Wait a few minutes or get a paid API key at aistudio.google.com"
            })
        return JSONResponse(status_code=500, content={"detail": err})

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/card/{username}")
async def serve_card(username: str):
    """Serve a saved dev card HTML file."""
    card_path = os.path.join(CARDS_DIR, f"{username}.html")
    if not os.path.exists(card_path):
        return JSONResponse(status_code=404, content={"detail": f"No card found for '{username}'. Generate one first."})
    return FileResponse(card_path, media_type="text/html")

@app.get("/")
async def serve_root():
    """Root endpoint — returns API info (frontend is a separate Cloud Run service)."""
    return HTMLResponse("""
    <html><head><title>GitHub Card Generator API</title>
    <style>body{font-family:sans-serif;background:#0d1117;color:#58a6ff;padding:40px;}
    a{color:#79c0ff;} code{background:#161b22;padding:3px 8px;border-radius:4px;}</style>
    </head><body>
    <h1>&#x1F4BB; GitHub Card Generator — Backend API</h1>
    <p>&#x2705; Server is running on Google Cloud Run</p>
    <ul>
      <li><a href="/health">/health</a> — health check</li>
      <li><code>POST /generate</code> — generate a dev card</li>
      <li><code>GET /card/{username}</code> — fetch a saved card</li>
    </ul>
    </body></html>
    """)
