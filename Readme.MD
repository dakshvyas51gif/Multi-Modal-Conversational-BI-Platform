# Multi-Modal Conversational BI Platform

A voice- and text-driven Business Intelligence application. Users can ask business questions in natural language, have the request checked, generate and execute read-only PostgreSQL SQL, and receive a chart, written insights, and an audio explanation.

> **Project status:** Development / integration-testing stage. The code includes the main workflow, but live Gemini, Whisper, PostgreSQL/Supabase, browser microphone, and deployment checks must still be completed in your own environment. Do not treat this as a production-authenticated multi-user service yet.

## Features

- **Text queries:** Ask questions about the connected business database.
- **Voice queries:** Upload a browser-recorded audio clip; OpenAI Whisper transcribes it before the CrewAI workflow starts.
- **Intent and safety gate:** The first CrewAI workflow classifies a request as `ALLOW`, `REJECT`, or `CLARIFY`. The analytics workflow starts only when the decision is explicitly `ALLOW`.
- **Text-to-SQL:** A CrewAI agent inspects the PostgreSQL schema, generates a query, validates it with SQLGlot, and executes it through a read-only SQLAlchemy transaction.
- **Visualization and insights:** A CrewAI agent reads the exact structured SQL result, creates a Plotly chart, writes concise insights, and requests an audio explanation from gTTS.
- **History:** Query, SQL, and summary are saved to the Supabase `public.user_clint` table.
- **Output housekeeping:** Generated chart/audio files have unique names and old output files are removed based on a configurable retention period.

## Architecture

The project has **3 LLM agents across 2 CrewAI crews**. STT, database execution, and TTS are handled as a normal Python function or CrewAI tools—not as separate LLM agents.

```text
Text query ─────────────────────────────────────────────┐
                                                        │
Voice recording → FastAPI upload → Whisper STT ─────────┤
                                                        ▼
                                            Intent & Guardrail Crew
                                            (ALLOW / REJECT / CLARIFY)
                                                        │
                                       ALLOW only ──────┘
                                            │
                                            ▼
                                         Analytics Crew
                                            │
                           ┌────────────────┴─────────────────┐
                           ▼                                  ▼
                  Text-to-SQL Agent              Visualization & Summary Agent
                  - Read DB schema                - Read exact SQL result
                  - Generate SQL                  - Create Plotly chart
                  - Validate SQL                  - Write insights
                  - Execute read-only SQL         - Generate gTTS audio
                           │                                  │
                           ▼                                  ▼
                    PostgreSQL                         outputs/*.html
                    (Supabase DB)                      outputs/*.mp3
                           │
                           ▼
                   Supabase query history

FastAPI returns SQL, structured rows, insights, chart URL, and audio URL
                         │
                         ▼
                 HTML / CSS / JavaScript dashboard
```

### Main project files

```text
Multi-Modal-BI/
├── agent.py                 # 3 CrewAI agents, tasks, and 2 crews
├── tools.py                 # Whisper, safety, schema, SQL, Plotly, and TTS tools
├── db.py                    # Supabase client and query-history table setup
├── main.py                  # FastAPI backend and API endpoints
├── requirements.txt         # Python dependencies
├── .env                     # Local secrets/configuration (do not commit)
├── .gitignore
├── README.md
├── static/
│   ├── index.html
│   ├── script.js
│   └── style.css
└── outputs/                 # Generated charts/audio (created automatically)
```

## Requirements

- **Python 3.11 is recommended.** CrewAI supports Python 3.10 to below 3.14, while the OpenAI Whisper README documents compatibility through Python 3.11. Python 3.11 is the overlap safest for this project's current stack.
- PostgreSQL database (the current SQL tools use PostgreSQL syntax and connection strings).
- Supabase project for query history.
- Google Gemini API key.
- FFmpeg installed and available on `PATH` for Whisper audio decoding.
- Internet access for Gemini API calls, initial Whisper model download, and gTTS audio generation.

## Setup on Windows (PowerShell)

Open a terminal in the project root—the folder containing `main.py`.

### 1. Create and activate a virtual environment

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

If PowerShell blocks environment activation, use Command Prompt and run:

```bat
.venv\Scripts\activate.bat
```

### 2. Install Python packages

```powershell
pip install -r requirements.txt
```

### 3. Install FFmpeg

For Windows with `winget`:

```powershell
winget install -e --id Gyan.FFmpeg
```

Close and reopen the terminal after installation, then verify:

```powershell
ffmpeg -version
```

### 4. Configure environment variables

Create a file named `.env` in the same folder as `main.py`. Add your own values; do not commit this file.

```dotenv
# Required: Google Gemini
GOOGLE_API_KEY=replace_with_your_google_api_key

# Required: Supabase project (server-side key only)
SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
SUPABASE_KEY=replace_with_your_supabase_service_role_key

# Required: PostgreSQL connection string
DB_CONNECTION_STRING=postgresql+psycopg2://USER:PASSWORD@HOST:5432/DATABASE

# Application settings
APP_ENV=development
BI_API_KEY=
CORS_ORIGINS=
LOG_LEVEL=INFO

# Optional settings (defaults shown)
WHISPER_MODEL=base
BI_OUTPUT_DIR=outputs
OUTPUT_TTL_SECONDS=86400
API_RATE_LIMIT=10
API_RATE_WINDOW_SECONDS=60
```

Notes:

- `SUPABASE_KEY` is a **server-side service-role key**. Never put it in `static/script.js`, HTML, CSS, or a public repository.
- `DB_CONNECTION_STRING` must be a PostgreSQL connection string. The code uses it for schema inspection and read-only SQL execution.
- `WHISPER_MODEL` defaults to `base`. Smaller models such as `tiny` are faster but generally less accurate; larger models need more RAM/compute.
- `CORS_ORIGINS` is a comma-separated list of trusted frontend origins, with no wildcard. When the frontend is served by this same FastAPI app, it can normally remain empty for local development.
- In `APP_ENV=production`, `BI_API_KEY` must be set to a non-empty value. See the **Security notes** below: this is not a substitute for full user authentication.

### 5. Initialize the query-history table

Run this once after configuring the Supabase and database credentials:

```powershell
python db.py
```

This creates `public.user_clint` if it does not exist and enables Row Level Security (RLS). The setup connection needs sufficient database privileges to create the table and grant the backend role access.

**Important database-permission recommendation:** The current `DB_CONNECTION_STRING` is also used by the runtime SQL tools. For stronger least-privilege security, use an administrator-capable connection only for the one-time table setup, then configure the runtime `DB_CONNECTION_STRING` with a dedicated PostgreSQL user that has only `CONNECT`, schema `USAGE`, and `SELECT` permissions on the business tables needed for analytics. Do not run arbitrary analytics queries using a database owner or superuser account.

### 6. Start the FastAPI server

```powershell
uvicorn main:app --reload
```

Open the dashboard:

- App: <http://127.0.0.1:8000>
- Interactive API docs: <http://127.0.0.1:8000/docs>

Use `--reload` for local development only. Do not use the development reload server as a production deployment command.

## API endpoints

| Method | Endpoint | Request | Purpose |
|---|---|---|---|
| `GET` | `/` | — | Serves `static/index.html` |
| `GET` | `/style.css` | — | Serves the dashboard stylesheet |
| `GET` | `/script.js` | — | Serves the dashboard JavaScript |
| `POST` | `/api/query` | JSON: `{"query": "show monthly sales"}` | Runs a text query |
| `POST` | `/api/voice-query` | `multipart/form-data`, file field `file` | Transcribes and processes an audio query |
| `GET` | `/api/chart?file=...` | Generated chart filename | Serves a generated Plotly HTML file |
| `GET` | `/api/audio?file=...` | Generated audio filename | Serves a generated MP3 file |

The text query is limited to 2,000 characters. Audio uploads are limited to 25 MB and accepted extensions are configured in `main.py`.

A successful query response includes the normalized query, SQL text, structured SQL execution result (`status`, `columns`, `row_count`, `truncated`, and `rows`), summary, and optional chart/audio URLs. Query results are capped at 500 rows by the SQL execution tool.

## Runtime configuration reference

| Variable | Required | Default / meaning |
|---|---:|---|
| `GOOGLE_API_KEY` | Yes | Gemini API key used by CrewAI |
| `SUPABASE_URL` | Yes | Supabase project URL |
| `SUPABASE_KEY` | Yes | Backend-only Supabase service-role key |
| `DB_CONNECTION_STRING` | Yes for database features | PostgreSQL connection string |
| `APP_ENV` | No | `development`; use `production` for production-mode checks |
| `BI_API_KEY` | Production | Must be set when `APP_ENV=production`; not full user authentication |
| `CORS_ORIGINS` | No | Comma-separated allowed origins; wildcard is rejected |
| `WHISPER_MODEL` | No | `base` |
| `BI_OUTPUT_DIR` | No | `outputs` |
| `OUTPUT_TTL_SECONDS` | No | `86400` (24 hours; code enforces a minimum of 600 seconds) |
| `API_RATE_LIMIT` | No | `10` requests per IP per window |
| `API_RATE_WINDOW_SECONDS` | No | `60` seconds |
| `LOG_LEVEL` | No | `INFO` |

## Security notes and current limitations

- SQL validation permits a single read-only `SELECT`/`UNION` query and the execution transaction sets PostgreSQL to read-only with a 15-second statement timeout. This parser and transaction protection are defense-in-depth, not a replacement for a dedicated read-only database role.
- The query safety tool uses pattern checks and an LLM decision; it is not a complete prompt-injection or authorization system. Enforce user/table/row permissions in the database.
- The API rate limiter is in-memory and per process. It resets on restart and is not shared across multiple workers or machines.
- `BI_API_KEY` is checked for requests without an `Origin` header. The current same-origin browser flow does not provide a full login/session authentication mechanism. Add proper authentication and authorization before exposing the app publicly.
- RLS is enabled on the history table, but the project currently uses a backend service-role key for server-side inserts. Keep that key private and do not create broad public RLS policies.
- History is stored in Supabase, but the dashboard's History, Data Sources, and Settings navigation items are still placeholders unless separately implemented.
- The configured Gemini model identifier is in `agent.py`. Confirm that it is available to your Google API project; update it there if your account/provider does not support it.
- The current platform is PostgreSQL/Supabase oriented. Snowflake support is described in the original project vision but is not implemented by these current database tools.

## Suggested smoke-test sequence

1. Run `python db.py` and confirm that the `user_clint` table setup succeeds.
2. Start the API with `uvicorn main:app --reload` and open `/docs`.
3. Submit a simple text analytics query against a table that exists in your database.
4. Confirm the response contains `decision: ALLOW`, the generated SQL, structured rows, and a summary.
5. Confirm the chart opens from the returned `visualization.chart_url` and the MP3 plays from the returned `audio` URL.
6. Record a short voice query and confirm Whisper transcribes it and the same flow completes.
7. Submit an unsafe or non-analytics query and confirm that the analytics Crew does not run.
8. Verify that the query history row appears in Supabase.

If a step fails, use the terminal traceback and FastAPI `/docs` response to isolate whether the issue is the Gemini provider/model, database credentials/permissions, FFmpeg/Whisper, gTTS connectivity, or frontend request handling.
