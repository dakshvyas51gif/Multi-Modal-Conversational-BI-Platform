import os
import whisper
from typing import Optional
from dotenv import load_dotenv
from crewai.tools import tool
import re
from supabase import create_client, Client
import sqlglot
from sqlalchemy import create_engine, text
import json
import pandas as pd
import plotly.express as px
from gtts import gTTS

load_dotenv()  # .env se keys aayengi

@tool("Audio Transcription Tool")
def transcribe_audio_tool(audio_path: str) -> str:
    """Takes the local path of an audio file (e.g., 'sample.mp3' or 'audio.wav')

    and transcribes it into text using OpenAI Whisper.
    """
    try:
        # Load the Whisper model ('tiny', 'base', 'small', 'medium', 'large')
        # 'base' or 'small' is recommended for a good balance of speed and accuracy.
        model = whisper.load_model("base")

        # Transcribe the audio file
        result = model.transcribe(audio_path)

        return result["text"]

    except Exception as e:
        return f"Error transcribing audio: {str(e)}"




@tool("Check Query Safety Tool")
def check_query_safety_tool(user_query: str) -> str:
    """Checks input user queries for suspicious inputs, prompt injection attempts,

    malicious command patterns, SQL injections, and policy violations.
    Returns whether the query is safe or flagged with specific reasons.
    """
    # 1. Patterns for Prompt Injection Attacks
    prompt_injection_patterns = [
        r"ignore (all )?previous instructions",
        r"disregard all prior instructions",
        r"you are now DAN",
        r"system prompt override",
        r"act as an unrestricted ai",
        r"jailbreak mode",
    ]

    # 2. Patterns for Malicious Commands / SQL Injection
    malicious_code_patterns = [
        r"(DROP|DELETE|TRUNCATE|ALTER)\s+TABLE",
        r"DELETE\s+FROM|INSERT\s+INTO|;\s*(DROP|UPDATE)",
        r"UNION\s+SELECT",
        r"<script.*?>.*?</script>",
        r"rm\s+-rf",
        r"sudo\s+",
        r"eval\(",
        r"exec\(",
    ]

    # 3. Policy Violations (Unsafe / Banned Content Keywords)
    policy_violation_keywords = [
        "hate speech",
        "how to build a bomb",
        "illegal access",
        "passwords dump",
        "credit card generator",
    ]

    query_lower = user_query.lower()

    # Check for Prompt Injection
    for pattern in prompt_injection_patterns:
        if re.search(pattern, user_query, re.IGNORECASE):
            return "FLAGGED: Potential Prompt Injection detected."

    # Check for Malicious Commands / Injection Code
    for pattern in malicious_code_patterns:
        if re.search(pattern, user_query, re.IGNORECASE):
            return "FLAGGED: Suspicious code or injection syntax detected."

    # Check for Policy Violations
    for keyword in policy_violation_keywords:
        if keyword in query_lower:
            return f"FLAGGED: Content policy violation detected (Keyword: '{keyword}')."

    # If all checks pass
    return "SAFE: The query passed all security and policy checks."


@tool("Supabase Query Tool")
def query_supabase_table(table_name: str) -> str:
    """Fetches records/data from a specific table in Supabase

    using the official Supabase Python client.
    """
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")

    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

        # Fetch data from the table
        response = supabase.table(table_name).select("*").limit(10).execute()

        return json.dumps(response.data, default=str)
    except Exception as e:
        return f"Error fetching data from Supabase: {str(e)}"


@tool("Get Database Schema Tool")
def get_database_schema_tool(schema_name: str = "public") -> str:
    """Reads the real database schema (tables, columns and data types)

    from PostgreSQL so SQL is generated using only existing tables and columns.
    """
    try:
        engine = create_engine(os.getenv("DB_CONNECTION_STRING"))
        query = text(
            "SELECT table_name, column_name, data_type FROM information_schema.columns "
            "WHERE table_schema = :s AND table_name <> 'user_clint' "
            "ORDER BY table_name, ordinal_position"
        )
        with engine.connect() as connection:
            rows = connection.execute(query, {"s": schema_name}).fetchall()

        schema = {}
        for table_name, column_name, data_type in rows:
            schema.setdefault(table_name, []).append(f"{column_name} ({data_type})")

        return "\n".join(f"{t}: {', '.join(c)}" for t, c in schema.items()) or "No tables found."

    except Exception as e:
        return f"Error reading database schema: {str(e)}"


@tool("Validate SQL Tool")
def validate_sql_tool(sql_query: str) -> str:
    """Validates PostgreSQL queries using sqlglot and ensures they are strictly read-only (SELECT only)."""
    try:
        # Parse query as PostgreSQL
        statements = sqlglot.parse(sql_query, read="postgres")

        # Sirf ek statement allowed (SELECT 1; DROP TABLE x bypass na ho)
        if len(statements) != 1:
            return "VIOLATION: Only a single SQL statement is allowed."

        # Check if it's a SELECT statement (WITH/CTE aur UNION bhi allowed)
        parsed = statements[0]
        if not isinstance(parsed, (sqlglot.exp.Select, sqlglot.exp.Union)):
            return "VIOLATION: Only read-only SELECT queries are allowed."

        return "VALID: Query is safe and syntactically correct."

    except Exception as e:
        return f"INVALID SYNTAX: {str(e)}"


@tool("Execute Readonly SQL Tool")
def execute_readonly_sql_tool(sql_query: str) -> str:
    """Executes a validated read-only SQL query on the Supabase PostgreSQL

    database and returns the result rows as a string.
    """
    try:
        engine = create_engine(os.getenv("DB_CONNECTION_STRING"))
        with engine.connect() as connection:
            result = connection.execute(text(sql_query))
            rows = [dict(row._mapping) for row in result]

            if not rows:
                return "Query executed successfully, but returned 0 rows."

            return json.dumps(rows, default=str)

    except Exception as e:
        return f"Error executing SQL query: {str(e)}"


@tool("Create PowerBI Style Chart Tool")
def create_plotly_chart_tool(
    data_json: str,
    x_col: str,
    y_col: str,
    chart_type: str = "bar",
    title: str = "PowerBI Dashboard",
    size_col: Optional[str] = None,
) -> str:
    """Creates interactive Power BI style charts (Bar, Column, Line, Area,

    Pie, Donut, Scatter, Bubble, Treemap, Funnel) and saves as 'output_chart.html'.
    """
    try:
        # Load data into DataFrame
        data = json.loads(data_json) if isinstance(data_json, str) else data_json
        df = pd.DataFrame(data)

        c_type = chart_type.lower()

        # Map Power BI chart types to Plotly
        if c_type in ["bar", "column"]:
            fig = px.bar(df, x=x_col, y=y_col, title=title)
        elif c_type == "line":
            fig = px.line(df, x=x_col, y=y_col, title=title)
        elif c_type == "area":
            fig = px.area(df, x=x_col, y=y_col, title=title)
        elif c_type == "pie":
            fig = px.pie(df, names=x_col, values=y_col, title=title)
        elif c_type == "donut":
            fig = px.pie(df, names=x_col, values=y_col, title=title, hole=0.4)
        elif c_type == "scatter":
            fig = px.scatter(df, x=x_col, y=y_col, title=title)
        elif c_type == "bubble":
            fig = px.scatter(
                df, x=x_col, y=y_col, size=size_col or y_col, title=title
            )
        elif c_type == "treemap":
            fig = px.treemap(df, path=[x_col], values=y_col, title=title)
        elif c_type == "funnel":
            fig = px.funnel(df, x=x_col, y=y_col, title=title)
        else:
            fig = px.bar(df, x=x_col, y=y_col, title=title)  # Default fallback

        # Apply clean, Power BI-like layout styling
        fig.update_layout(
            template="plotly_white",
            title_font=dict(size=18, family="Segoe UI, sans-serif"),
            margin=dict(t=50, b=50, l=50, r=50),
        )

        output_file = "output_chart.html"
        fig.write_html(output_file)

        return (
            f"Success: Power BI style '{c_type}' chart generated and saved as"
            f" '{output_file}'."
        )

    except Exception as e:
        return f"Error creating chart: {str(e)}"

@tool("Generate TTS Audio Tool")
def generate_tts_audio_tool(
    text_content: str, output_filename: str = "summary_audio.mp3", lang: str = "en"
) -> str:
    """Converts a text summary or content into an audio file (MP3)

    using Google Text-to-Speech (gTTS). Supports languages like 'en', 'hi', etc.
    """
    try:
        # Generate audio from text
        tts = gTTS(text=text_content, lang=lang, slow=False)

        # Save audio file locally
        tts.save(output_filename)

        return f"Success: Audio successfully generated and saved as '{output_filename}'."

    except Exception as e:
        return f"Error generating TTS audio: {str(e)}"