import os
import psycopg2
from dotenv import load_dotenv
from supabase import create_client, Client
import time

load_dotenv()

# .env file me ye 3 variables rakho
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
DB_CONNECTION_STRING = os.getenv("DB_CONNECTION_STRING")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL or SUPABASE_KEY missing in .env")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def create_supabase_table():
    if not DB_CONNECTION_STRING:
        raise ValueError("DB_CONNECTION_STRING missing in .env")

    commands = (
        """
        CREATE TABLE IF NOT EXISTS public.user_clint (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            user_query text,
            agent_repsons_for_sql text,
            agent_respons_summery text,
            data timestamptz DEFAULT now()
        );
        """,
        "ALTER TABLE public.user_clint ENABLE ROW LEVEL SECURITY;"
    )

    conn = None
    try:
        conn = psycopg2.connect(DB_CONNECTION_STRING, connect_timeout=10)
        with conn.cursor() as cur:
            for command in commands:
                cur.execute(command)
        conn.commit()
        print("Table 'user_clint' created/checked successfully; RLS enabled.")

    except Exception as error:
        if conn is not None:
            conn.rollback()
        print(f"Error creating Supabase table: {error}")
        raise

    finally:
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    create_supabase_table()

