import json
import os
import re
import tempfile
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import quote

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from agent import analytics_crew, get_decision, intent_crew, save_query_history
from tools import clear_runtime_caches, transcribe_audio_tool

load_dotenv()

STATIC_DIR = Path(__file__).resolve().parent / "static"
OUTPUT_DIR = Path(os.getenv("BI_OUTPUT_DIR", "outputs")).resolve()
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
MAX_AUDIO_BYTES = 25 * 1024 * 1024
ALLOWED_AUDIO = {".wav", ".mp3", ".m4a", ".mp4", ".mpeg", ".mpga", ".webm", ".ogg", ".flac"}
crew_lock = threading.Lock()  # Shared CrewAI tasks ka output state protect karta hai.


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await run_in_threadpool(clear_runtime_caches)


app = FastAPI(title="Multi-Modal Conversational BI Platform", version="1.0", lifespan=lifespan)
origins = [x.strip() for x in os.getenv("CORS_ORIGINS", "*").split(",") if x.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)


class TextQueryRequest(BaseModel):
    query: str


def _files(pattern: str) -> set[Path]:
    return set(OUTPUT_DIR.glob(pattern))


def _new_file(before: set[Path], pattern: str):
    created = [p for p in _files(pattern) - before if p.is_file()]
    return max(created, key=lambda p: p.stat().st_mtime) if created else None


def _raw(output) -> str:
    return str(getattr(output, "raw", output) or "")


def _execution_data(sql_output: str):
    decoder = json.JSONDecoder()
    for i, char in enumerate(sql_output):
        if char == "{":
            try:
                obj, _ = decoder.raw_decode(sql_output[i:])
                if isinstance(obj, dict) and any(k in obj for k in ("rows", "columns", "row_count")):
                    return obj
            except json.JSONDecodeError:
                pass
    return sql_output


def _output_file(filename: str, prefix: str, suffix: str) -> Path:
    if Path(filename).name != filename or not filename.startswith(prefix) or not filename.endswith(suffix):
        raise HTTPException(status_code=404, detail="Output file not found.")
    path = OUTPUT_DIR / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Output file not found.")
    return path


def run_pipeline(user_input: str, is_audio: bool = False) -> dict:
    """Whisper (optional) -> Intent Crew -> ALLOW gate -> Analytics Crew."""
    with crew_lock:
        query = user_input.strip()
        if not query:
            raise HTTPException(status_code=400, detail="Query is empty.")

        # STT Agent nahi: Whisper normal Python function CrewAI se pehle run hota hai.
        if is_audio:
            query = transcribe_audio_tool(query)
            if query.startswith("ERROR:"):
                raise HTTPException(status_code=400, detail=query)
            query = query.strip()

        if not query:
            raise HTTPException(status_code=400, detail="Audio mein speech detect nahi hui.")

        old_charts = _files("output_chart_*.html")
        old_audio = _files("summary_audio_*.mp3")

        # Crew 1: ALLOW / REJECT / CLARIFY
        intent_result = _raw(intent_crew.kickoff(inputs={"user_input": query}))
        decision = get_decision(intent_result)
        if decision != "ALLOW":
            reason = f"Analytics workflow skipped. Intent decision: {decision}.\n{intent_result}"
            save_query_history(query, reason, "Visualization and TTS skipped: request was not allowed.")
            raise HTTPException(status_code=400, detail=f"Query blocked by guardrail ({decision}): {intent_result}")

        # Crew 2: Text-to-SQL Task -> Visualization Task
        result = analytics_crew.kickoff(inputs={"user_input": query, "intent_result": intent_result})
        outputs = getattr(result, "tasks_output", []) or []
        sql_output = _raw(outputs[0]) if len(outputs) > 0 else "SQL task returned no output."
        summary = _raw(outputs[1]) if len(outputs) > 1 else "Visualization task returned no output."

        chart = _new_file(old_charts, "output_chart_*.html")
        audio = _new_file(old_audio, "summary_audio_*.mp3")
        save_query_history(query, sql_output, summary)

        sql_match = re.search(r"```(?:sql)?\s*(.*?)```", sql_output, re.I | re.S)
        return {
            "status": "success",
            "decision": decision,
            "query": query,
            "sql": sql_match.group(1).strip() if sql_match else sql_output,
            "data": _execution_data(sql_output),
            "summary": summary,
            "visualization": {"chart_url": f"/api/chart?file={quote(chart.name)}"} if chart else {},
            "audio": f"/api/audio?file={quote(audio.name)}" if audio else None,
        }


@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    path = STATIC_DIR / "index.html"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="static/index.html not found.")
    return FileResponse(path, media_type="text/html")


@app.get("/style.css")
async def serve_css():
    path = STATIC_DIR / "style.css"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="static/style.css not found.")
    return FileResponse(path, media_type="text/css")


@app.get("/script.js")
async def serve_js():
    path = STATIC_DIR / "script.js"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="static/script.js not found.")
    return FileResponse(path, media_type="application/javascript")


@app.get("/api/chart")
async def get_chart(file: str = Query(...)):
    return FileResponse(_output_file(file, "output_chart_", ".html"), media_type="text/html")


@app.get("/api/audio")
async def get_audio(file: str = Query(...)):
    return FileResponse(_output_file(file, "summary_audio_", ".mp3"), media_type="audio/mpeg")


@app.post("/api/query")
async def process_text_query(payload: TextQueryRequest):
    try:
        return await run_in_threadpool(run_pipeline, payload.query, False)
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)) from error


@app.post("/api/voice-query")
async def process_voice_query(file: UploadFile = File(...)):
    audio_path = None
    try:
        suffix = Path(file.filename or "recording.webm").suffix.lower() or ".webm"
        if suffix not in ALLOWED_AUDIO:
            raise HTTPException(status_code=415, detail=f"Unsupported audio format: {suffix}")

        content = await file.read(MAX_AUDIO_BYTES + 1)
        if not content:
            raise HTTPException(status_code=400, detail="Uploaded audio file is empty.")
        if len(content) > MAX_AUDIO_BYTES:
            raise HTTPException(status_code=413, detail="Audio file exceeds 25 MB limit.")

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp:
            temp.write(content)
            audio_path = temp.name
        return await run_in_threadpool(run_pipeline, audio_path, True)

    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)) from error
    finally:
        if audio_path and os.path.exists(audio_path):
            os.remove(audio_path)
        await file.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
