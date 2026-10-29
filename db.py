import os
import psycopg2
from dotenv import load_dotenv
from supabase import create_client, Client
import time

load_dotenv()

# .env file me ye 3 cheezein rakho (code me hardcode mat karo)
SUPABASE_URL = os.getenv("SUPABASE_URL")                      # https://<project-ref>.supabase.co
SUPABASE_KEY = os.getenv("SUPABASE_KEY")                      # service-role key
DB_CONNECTION_STRING = os.getenv("DB_CONNECTION_STRING")      # dashboard se connection string

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def create_supabase_table():
    commands = (
        """
            CREATE TABLE IF NOT EXISTS user_clint(
            id bigint generated always as identity primary key,
            user_query text,
            agent_repsons_for_sql text,
            agent_respons_summery text,
            data timestamptz default now() );
        """,
        """
        -- Strongly recommended: Enable Row Level Security (RLS) for safety
        ALTER TABLE user_clint ENABLE ROW LEVEL SECURITY;
        """
    )

    conn = None
    try:
        # Connect to the Supabase PostgreSQL database
        conn = psycopg2.connect(DB_CONNECTION_STRING)
        cur = conn.cursor()

        # Execute each SQL command
        for command in commands:
            cur.execute(command)

        # Close communication with the PostgreSQL database server
        cur.close()
        # Commit the changes
        conn.commit()
        print("Table 'user_clint' created successfully with RLS enabled!")

    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error: {error}")
    finally:
        if conn is not None:
            conn.close()


if __name__ == '__main__':
    create_supabase_table()

    #data insert
    i = 0
    while True:
        user_query = input("enter your query")
        agent_repsons_for_sql = input("enter sql response")
        agent_respons_summery = input("enter summary response")
        i += 1

        try:
            response = supabase.table("user_clint").insert({
                "user_query": user_query,
                "agent_repsons_for_sql": agent_repsons_for_sql,
                "agent_respons_summery": agent_respons_summery,
            }).execute()

            # Thoda gap dene ke liye (optional)
            time.sleep(0.5)

        except Exception as e:
            print(f"Failed to store user_v{i}: {e}")
