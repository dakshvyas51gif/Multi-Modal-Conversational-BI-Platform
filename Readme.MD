# Multi-Modal Conversational BI Platform

Ask questions about your data using **text or voice**. The platform converts your question into SQL, runs it on your database, and returns a **chart**, a **written summary**, and a **spoken audio explanation**.

## How it works

```
Voice/Text → Whisper (STT) → Guardrail → Text-to-SQL → Run SQL → Chart + Summary → Audio (TTS)
```

Six AI agents (built with CrewAI and Gemini) handle these steps one after another.

| Step | What it does |
|---|---|
| STT | Converts audio to text with OpenAI Whisper |
| Guardrail | Blocks unsafe or unrelated questions |
| Text-to-SQL | Writes a PostgreSQL `SELECT` query from your question |
| Execution | Runs the query (read-only) on Supabase PostgreSQL |
| Visualization | Creates a Plotly chart and bullet-point insights |
| TTS | Turns the summary into an MP3 with gTTS |

## Project structure

```
main.py        FastAPI server (API + serves the web page)
agent.py       CrewAI agents, tasks and crew
tools.py       Tools used by the agents (SQL, chart, audio, safety)
db.py          Creates the history table in Supabase
.env           Your secret keys (do not share)
static/
  index.html   Web interface
  style.css
  script.js
```

## Setup

**1. Install**

```bash
pip install crewai openai-whisper gTTS sqlglot sqlalchemy psycopg2-binary plotly pandas supabase python-dotenv fastapi uvicorn python-multipart
```

Whisper also needs [ffmpeg](https://ffmpeg.org/download.html) installed on your computer.

**2. Create a `.env` file**

```
GOOGLE_API_KEY=your-gemini-api-key
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_KEY=<service-role-key>
DB_CONNECTION_STRING=postgresql://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres
```

- `GOOGLE_API_KEY` is from Google AI Studio.
- The other three are from your Supabase dashboard (Settings → API, and Connect → Transaction pooler).
- Never upload `.env` to GitHub.

**3. Create the history table (one time)**

```bash
python db.py
```

When it asks for input, press `Ctrl+C`.

**4. Add your data**

Your Supabase database should already have your business tables (for example `sales`). The agent writes SQL only for tables that exist.

## Run

Web app:

```bash
python main.py
```

Open `http://localhost:8000`.

Terminal only (no web page):

```bash
python agent.py
```

Type a question, or an audio file path such as `sample.mp3`. Type `exit` to quit.

## API

| Endpoint | Method | Description |
|---|---|---|
| `/api/query` | POST | Send `{"query": "total sales by month"}` |
| `/api/voice-query` | POST | Upload an audio file (form field `file`) |
| `/api/chart` | GET | Latest generated chart (HTML) |
| `/api/audio` | GET | Latest generated audio (MP3) |

Response example:

```json
{
  "status": "success",
  "query": "total sales by month",
  "sql": "SELECT ...",
  "data": [{"month": "Jan", "total_sales": 55000}],
  "summary": "- Sales grow steadily ...",
  "visualization": {"chart_url": "/api/chart"},
  "audio": "/api/audio"
}
```

## Safety

- Only a single read-only `SELECT` query is allowed (no `INSERT`, `UPDATE`, `DELETE`, `DROP`).
- Unsafe questions are blocked by the guardrail agent and the safety checker.
- Every question, SQL and summary is saved in the `user_clint` table.

## Notes

- One query is processed at a time, and each query runs 6 agents, so a reply can take some time.
- AI can sometimes write a wrong query, so check important numbers.
- The web page (`script.js`) currently shows demo data. It is not yet connected to `/api/query`.