import os
import re
import json
from functools import lru_cache
from pathlib import Path
from typing import Optional
from uuid import uuid4

import whisper
import sqlglot
from sqlglot import exp
import pandas as pd
import plotly.express as px
from gtts import gTTS
from dotenv import load_dotenv
from crewai.tools import tool
from sqlalchemy import create_engine, text

load_dotenv()


# -------------------- Shared resources --------------------

@lru_cache(maxsize=1)
def _get_whisper_model():
    """Whisper model ko ek baar load karke reuse karta hai."""
    model_name = os.getenv("WHISPER_MODEL", "base")
    return whisper.load_model(model_name)


@lru_cache(maxsize=1)
def _get_database_engine():
    """Database engine ko reuse karta hai."""
    connection_string = os.getenv("DB_CONNECTION_STRING")
    if not connection_string:
        raise ValueError("DB_CONNECTION_STRING .env mein set nahi hai.")

    return create_engine(
        connection_string,
        pool_pre_ping=True,
        pool_recycle=1800,
    )


def _unique_output_path(default_name: str, requested_name: Optional[str] = None) -> Path:
    """Har chart/audio output ke liye unique filename banata hai."""
    output_dir = Path(os.getenv("BI_OUTPUT_DIR", "outputs"))
    output_dir.mkdir(parents=True, exist_ok=True)

    safe_name = Path(requested_name or default_name).name
    requested_path = Path(safe_name)
    suffix = requested_path.suffix or Path(default_name).suffix
    unique_name = f"{requested_path.stem}_{uuid4().hex[:8]}{suffix}"
    return output_dir / unique_name


# -------------------- Normal Python function (STT) --------------------
# Ye CrewAI Agent nahi hai aur @tool bhi nahi hai.
# Audio input milne par agent.py se Crew start hone se pehle call hota hai.

def transcribe_audio_tool(audio_path: str) -> str:
    """Local audio file ko Whisper library se text mein convert karta hai."""
    try:
        path = Path(audio_path).expanduser()
        if not path.is_file():
            return f"ERROR: Audio file nahi mili: {audio_path}"

        result = _get_whisper_model().transcribe(str(path))
        transcript = result.get("text", "").strip()
        if not transcript:
            return "ERROR: Audio se koi speech transcribe nahi hui."
        return transcript

    except Exception as e:
        return f"ERROR: Audio transcription failed: {e}"


# -------------------- CrewAI Tools --------------------

@tool("Check Query Safety Tool")
def check_query_safety_tool(user_query: str) -> str:
    """User query mein common prompt-injection aur unsafe command patterns check karta hai."""
    prompt_injection_patterns = [
        r"ignore (all )?previous instructions",
        r"disregard all prior instructions",
        r"you are now DAN",
        r"system prompt override",
        r"act as an unrestricted ai",
        r"jailbreak mode",
    ]

    malicious_code_patterns = [
        r"\b(DROP|DELETE|TRUNCATE|ALTER)\s+TABLE\b",
        r"\bDELETE\s+FROM\b|\bINSERT\s+INTO\b|;\s*\b(DROP|UPDATE)\b",
        r"\bUNION\s+SELECT\b",
        r"<script.*?>.*?</script>",
        r"\brm\s+-rf\b",
        r"\bsudo\s+",
        r"\beval\s*\(",
        r"\bexec\s*\(",
    ]

    policy_violation_keywords = [
        "hate speech",
        "how to build a bomb",
        "illegal access",
        "passwords dump",
        "credit card generator",
    ]

    for pattern in prompt_injection_patterns:
        if re.search(pattern, user_query, re.IGNORECASE):
            return "FLAGGED: Potential prompt injection detected."

    for pattern in malicious_code_patterns:
        if re.search(pattern, user_query, re.IGNORECASE):
            return "FLAGGED: Suspicious code or SQL injection syntax detected."

    query_lower = user_query.lower()
    for keyword in policy_violation_keywords:
        if keyword in query_lower:
            return f"FLAGGED: Policy violation keyword detected: {keyword}."

    return "SAFE: Query passed the basic security checks."


@tool("Get Database Schema Tool")
def get_database_schema_tool(schema_name: str = "public") -> str:
    """PostgreSQL schema se tables, columns aur data types read karta hai."""
    try:
        query = text(
            "SELECT table_name, column_name, data_type "
            "FROM information_schema.columns "
            "WHERE table_schema = :schema_name AND table_name <> 'user_clint' "
            "ORDER BY table_name, ordinal_position"
        )

        with _get_database_engine().connect() as connection:
            rows = connection.execute(query, {"schema_name": schema_name}).fetchall()

        schema = {}
        for table_name, column_name, data_type in rows:
            schema.setdefault(table_name, []).append(f"{column_name} ({data_type})")

        return "\n".join(
            f"{table}: {', '.join(columns)}" for table, columns in schema.items()
        ) or "No tables found."

    except Exception as e:
        return f"Error reading database schema: {e}"


def _validate_readonly_select(sql_query: str) -> Optional[str]:
    """Only one PostgreSQL SELECT/UNION statement allow karta hai."""
    if not sql_query or not sql_query.strip():
        return "SQL query is empty."

    try:
        statements = [s for s in sqlglot.parse(sql_query, read="postgres") if s is not None]
        if len(statements) != 1:
            return "Only one SQL statement is allowed."

        parsed = statements[0]
        if not isinstance(parsed, (exp.Select, exp.Union)):
            return "Only read-only SELECT queries are allowed."

        if parsed.args.get("into") is not None:
            return "SELECT INTO is not allowed."
        if parsed.args.get("locks"):
            return "Row-locking SELECT queries are not allowed."

        return None

    except Exception as e:
        return f"Invalid SQL syntax: {e}"


@tool("Validate SQL Tool")
def validate_sql_tool(sql_query: str) -> str:
    """SQL ko parse karke single read-only SELECT check karta hai."""
    validation_error = _validate_readonly_select(sql_query)
    if validation_error:
        return f"INVALID: {validation_error}"
    return "VALID: Single read-only SELECT query passed parser validation."


@tool("Execute Readonly SQL Tool")
def execute_readonly_sql_tool(sql_query: str) -> str:
    """SQL validate karke PostgreSQL read-only transaction mein execute karta hai."""
    validation_error = _validate_readonly_select(sql_query)
    if validation_error:
        return f"VIOLATION: {validation_error}"

    try:
        engine = _get_database_engine()
        with engine.connect() as connection:
            with connection.begin():
                # Transaction-level protection. DB credentials should also be read-only.
                connection.execute(text("SET TRANSACTION READ ONLY"))
                connection.execute(text("SET LOCAL statement_timeout = '15000ms'"))

                result = connection.execute(text(sql_query))
                columns = list(result.keys())
                rows = [dict(row) for row in result.mappings().fetchmany(501)]
                truncated = len(rows) > 500
                if truncated:
                    rows = rows[:500]

                return json.dumps(
                    {
                        "status": "success",
                        "columns": columns,
                        "row_count": len(rows),
                        "truncated": truncated,
                        "rows": rows,
                    },
                    default=str,
                )

    except Exception as e:
        return f"ERROR: SQL execution failed: {e}"


@tool("Create PowerBI Style Chart Tool")
def create_plotly_chart_tool(
    data_json: str,
    x_col: str,
    y_col: str,
    chart_type: str = "bar",
    title: str = "PowerBI Dashboard",
    size_col: Optional[str] = None,
) -> str:
    """Data se interactive Plotly chart banakar unique HTML file mein save karta hai."""
    try:
        data = json.loads(data_json) if isinstance(data_json, str) else data_json
        df = pd.DataFrame(data)
        if df.empty:
            return "ERROR: Dataset is empty; chart was not created."

        required_columns = [x_col, y_col]
        if chart_type.lower() == "bubble" and size_col:
            required_columns.append(size_col)
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            return f"ERROR: Missing chart columns: {', '.join(missing_columns)}"

        chart = chart_type.lower()
        if chart in ["bar", "column"]:
            fig = px.bar(df, x=x_col, y=y_col, title=title)
        elif chart == "line":
            fig = px.line(df, x=x_col, y=y_col, title=title)
        elif chart == "area":
            fig = px.area(df, x=x_col, y=y_col, title=title)
        elif chart == "pie":
            fig = px.pie(df, names=x_col, values=y_col, title=title)
        elif chart == "donut":
            fig = px.pie(df, names=x_col, values=y_col, title=title, hole=0.4)
        elif chart == "scatter":
            fig = px.scatter(df, x=x_col, y=y_col, title=title)
        elif chart == "bubble":
            fig = px.scatter(df, x=x_col, y=y_col, size=size_col or y_col, title=title)
        elif chart == "treemap":
            fig = px.treemap(df, path=[x_col], values=y_col, title=title)
        elif chart == "funnel":
            fig = px.funnel(df, x=x_col, y=y_col, title=title)
        else:
            return f"ERROR: Unsupported chart type: {chart_type}"

        fig.update_layout(
            template="plotly_white",
            title_font=dict(size=18, family="Segoe UI, sans-serif"),
            margin=dict(t=50, b=50, l=50, r=50),
        )

        output_file = _unique_output_path("output_chart.html")
        fig.write_html(str(output_file))
        return f"SUCCESS: Chart generated: {output_file.as_posix()}"

    except Exception as e:
        return f"ERROR: Chart generation failed: {e}"


@tool("Generate TTS Audio Tool")
def generate_tts_audio_tool(
    text_content: str,
    output_filename: Optional[str] = None,
    lang: str = "en",
) -> str:
    """gTTS se summary ka MP3 banata hai aur unique filename mein save karta hai."""
    try:
        if not text_content or not text_content.strip():
            return "ERROR: TTS text is empty."

        output_file = _unique_output_path("summary_audio.mp3", output_filename)
        gTTS(text=text_content, lang=lang, slow=False).save(str(output_file))
        return f"SUCCESS: Audio generated: {output_file.as_posix()}"

    except Exception as e:
        return f"ERROR: TTS generation failed: {e}"


def clear_runtime_caches():
    """Application shutdown par cached database connection pool release karta hai."""
    if _get_database_engine.cache_info().currsize:
        _get_database_engine().dispose()
    _get_database_engine.cache_clear()
    _get_whisper_model.cache_clear()
