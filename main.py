from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
import os
import re
import json
import time
import tempfile
import threading


# agent.py me 6 alag functions nahi, ek crew hai (6 agents + 6 tasks), isliye crew import hoti hai
from agent import crew
from db import supabase

app = FastAPI(title="Multi-Modal Conversational BI Platform", version="1.0")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


os.makedirs("template", exist_ok=True)  # folder na ho to server start hote hi crash na ho
app.mount("/template", StaticFiles(directory="template"), name="template")

CHART_FILE = "output_chart.html"    # tools.py chart yahan save karta hai
AUDIO_FILE = "summary_audio.mp3"    # tools.py audio yahan save karta hai
crew_lock = threading.Lock()        # crew ek hi hai, isliye ek time pe ek hi query chalegi


class TextQueryRequest(BaseModel):
    query: str


def parse_json(text):
    """Execution agent ka output JSON ho to list/dict bana deta hai, warna text hi wapas."""
    try:
        return json.loads(text)
    except Exception:
        match = re.search(r"\[.*\]", text, re.S)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass
    return text


def run_pipeline(user_input: str, is_audio: bool = False) -> dict:
    """STT -> Guardrail -> Text-to-SQL -> Execution -> Visualization -> TTS (agent.py ki crew)."""
    with crew_lock:
        # purani query ki chart/audio file naye response me na aa jaye
        for f in (CHART_FILE, AUDIO_FILE):
            if os.path.exists(f):
                os.remove(f)

        result = crew.kickoff(inputs={"user_input": user_input})

    outputs = [t.raw for t in result.tasks_output]
    if len(outputs) < 6:
        raise RuntimeError("Pipeline incomplete: expected 6 task outputs.")
    stt_out, intent_out, sql_out, data_out, viz_out, tts_out = outputs[:6]

    # voice ho to transcribed text, text ho to user ka original query
    user_query = user_input
    if is_audio:
        match = re.search(r"transcribed text\W*\s*(.+)", stt_out, re.I)
        user_query = (match.group(1) if match else stt_out).strip().strip('"*')

    # Guardrail decision (ALLOW / REJECT / CLARIFY)
    match = re.search(r"decision\W+(allow|reject|clarify)", intent_out, re.I)
    if match:
        decision = match.group(1).upper()
    elif re.search(r"\breject\b", intent_out, re.I) and not re.search(r"\ballow\b", intent_out, re.I):
        decision = "REJECT"
    else:
        decision = "ALLOW"
    if decision != "ALLOW":
        raise HTTPException(status_code=400, detail=f"Query blocked by guardrail ({decision}): {intent_out}")

    sql_query = re.sub(r"```(?:sql)?", "", sql_out).strip()
    summary_text = viz_out or "No summary generated."
    stamp = int(time.time())

    # history Supabase (user_clint) me save, fail ho to bhi response chalega
    try:
        supabase.table("user_clint").insert({
            "user_query": user_query,
            "agent_repsons_for_sql": sql_query,
            "agent_respons_summery": summary_text,
        }).execute()
    except Exception as e:
        print(f"Failed to store query: {e}")

    return {
        "status": "success",
        "query": user_query,
        "sql": sql_query,
        "data": parse_json(data_out),
        "summary": summary_text,
        "visualization": {"chart_url": f"/api/chart?t={stamp}"} if os.path.exists(CHART_FILE) else {},
        "audio": f"/api/audio?t={stamp}" if os.path.exists(AUDIO_FILE) else None,
    }


@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    html_path = os.path.join("static", "index.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>index.html not found in 'static' folder!</h1>"


# index.html me <link href="style.css"> aur <script src="script.js"> relative hain,
# isliye ye dono root pe bhi serve hone chahiye (warna 404)
@app.get("/style.css")
async def serve_css():
    return FileResponse(os.path.join("static", "style.css"), media_type="text/css")


@app.get("/script.js")
async def serve_js():
    return FileResponse(os.path.join("static", "script.js"), media_type="application/javascript")


@app.get("/api/chart")
async def get_chart():
    if not os.path.exists(CHART_FILE):
        raise HTTPException(status_code=404, detail="No chart generated yet.")
    return FileResponse(CHART_FILE, media_type="text/html")


@app.get("/api/audio")
async def get_audio():
    if not os.path.exists(AUDIO_FILE):
        raise HTTPException(status_code=404, detail="No audio generated yet.")
    return FileResponse(AUDIO_FILE, media_type="audio/mpeg")


@app.post("/api/query")
async def process_text_query(payload: TextQueryRequest):
    try:
        user_query = payload.query.strip()
        if not user_query:
            raise HTTPException(status_code=400, detail="Query is empty.")

        # crew.kickoff blocking hai, isliye threadpool me (warna poora server ruk jata)
        return await run_in_threadpool(run_pipeline, user_query)
    except HTTPException:
        raise  # 400 ko 500 me mat badlo
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/voice-query")
async def process_voice_query(file: UploadFile = File(...)):
    audio_path = None
    try:
        audio_bytes = await file.read()

        # Whisper tool ko file path chahiye, bytes nahi -> temp file banao
        suffix = os.path.splitext(file.filename or "")[1] or ".webm"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(audio_bytes)
            audio_path = tmp.name

        return await run_in_threadpool(run_pipeline, audio_path, True)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if audio_path and os.path.exists(audio_path):
            os.remove(audio_path)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)