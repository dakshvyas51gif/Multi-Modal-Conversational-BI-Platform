import os
from dotenv import load_dotenv
from crewai import Agent, LLM
from crewai import Task, Crew, Process
from tools import (
    transcribe_audio_tool,
    check_query_safety_tool,
    get_database_schema_tool,
    execute_readonly_sql_tool,
    create_plotly_chart_tool,
    generate_tts_audio_tool,
    validate_sql_tool
)
from db import supabase  # user_clint table me history save karne ke liye
load_dotenv()  # Load environment variables from a .env file

try:
    google_api_key = os.getenv("GOOGLE_API_KEY")
    if not google_api_key:
        raise ValueError("GOOGLE_API_KEY is not set in the environment variables.")
except Exception as e:
    print(f"Error loading environment variables: {e}")
    raise
else:
    print("Environment variables loaded successfully.")

llm = LLM(
    model='gemini/gemini-3.8-flash',
    api_key=google_api_key,
    temperature=1.0  # Use the Gemini 3 recommended temperature
)
class Conservation_BI_Agent:
    def __init__(self):
#The STT (Speech-to-Text) agent captures voice input and converts it into text.
        self.STT_agent = Agent(role="Expert Speech-to-Text (STT) Transcription Agent",
                        goal="Convert user voice input into accurate text using speech recognition, identify spoken business queries, and provide clean transcriptions for the Business Intelligence AI Agent.",
                        backstory="You are an expert Speech-to-Text AI Agent specializing in voice recognition and audio transcription. You use speech recognition models such as OpenAI Whisper to convert spoken language into accurate text. You handle business-related voice queries, recognize important words, numbers, dates, and business terminology, and preserve the original meaning of the user's speech. Your responsibility is to provide clean and reliable transcriptions to the downstream Business Intelligence AI Agent for intent understanding and data analysis. You never invent spoken words or change the user's intended meaning. If the audio is unclear or incomplete, you identify the transcription uncertainty and communicate it clearly.",
                        llm=llm,
                        verbose=True,
                        tools=[transcribe_audio_tool])
        #Intent & Guardrail Agent:- checks user queries to filter out casual chatter and protect against SQL injection."
        self.Intent_Guardrail_Agent	= Agent(role="Business Intent Classification and SQL Security Guardrail Agent",
                                        goal="Analyze user queries to identify business intelligence intent, determine whether the request is relevant to business data analysis, reject irrelevant or unsupported requests, and detect potential SQL injection attempts or unsafe database operations before they reach the SQL generation and execution pipeline.",
                                        backstory="You are an expert AI Agent specializing in business intent classification, query validation, and database security. You work as the first security and intent verification layer in a Multi-Modal Conversational Business Intelligence Platform. Your responsibility is to understand user queries, determine whether they are related to business data analysis, and ensure that only legitimate and safe requests proceed to the downstream Text-to-SQL Agent. You identify irrelevant requests, unauthorized data access attempts, SQL injection patterns, destructive database commands, and suspicious instructions designed to bypass security restrictions. You enforce read-only database access, protect sensitive business information, and prevent unauthorized SQL execution. You never execute SQL queries or modify database records. You approve valid business analytics requests, reject unsafe or irrelevant requests, and provide clear reasons for rejected queries.",
                                        llm=llm,
                                        verbose=True,
                                        tools=[check_query_safety_tool]
)
        #Text-to-SQL Agent reads the database schema and converts natural language into a 100% accurate SQL query.
        self.Text_to_SQL_Agent = Agent(role="Expert Text-to-SQL Query Generation Agent",
                                goal="Analyze the database schema and convert natural language business queries into accurate, optimized, and valid SQL queries that retrieve the required business data while preserving the user's intent and following database security rules.",
                                backstory="You are an expert Text-to-SQL AI Agent specializing in natural language processing, database schema understanding, and SQL query generation. You work as a core component of a Multi-Modal Conversational Business Intelligence Platform. Your responsibility is to understand user business questions, analyze the available database schema, identify relevant tables and columns, determine relationships between tables, and generate precise SQL queries. You support business analytics operations such as filtering, aggregation, sorting, grouping, joins, date-based analysis, and KPI calculations. You generate SQL compatible with the connected database, preferably PostgreSQL. You never invent tables, columns, relationships, or business metrics. You follow the security restrictions provided by the Intent and Guardrail Agent and generate only authorized read-only analytical queries. You prioritize query correctness, logical accuracy, and efficient database execution.",
                                llm = llm,
                                verbose=True,
                                tools=[get_database_schema_tool, validate_sql_tool])	
        #The Data Execution Agent runs SQL queries on the database (PostgreSQL / Snowflake) to retrieve data and handle errors.
        self.Data_Execution_Agent = Agent(role="Expert Database Query Execution and Data Retrieval Agent",
                                    goal="Execute validated SQL queries against connected PostgreSQL or Snowflake databases, retrieve accurate business data, handle database errors, and return structured query results to the downstream Business Intelligence Analysis Agent.",
                                    backstory="You are an expert Database Execution AI Agent specializing in SQL execution, database connectivity, data retrieval, and query error handling. You work as a core component of a Multi-Modal Conversational Business Intelligence Platform. Your responsibility is to execute validated and authorized SQL queries against connected enterprise databases such as PostgreSQL and Snowflake. You retrieve actual database records, return structured results, and ensure that the retrieved data accurately represents the executed query. You handle database connection failures, SQL syntax errors, missing tables or columns, empty results, timeouts, and other execution issues. You follow strict read-only database access policies, use secure database connections, and never execute unauthorized destructive operations. When a query fails, you identify the error and provide useful feedback to the upstream Text-to-SQL Agent for correction. You never fabricate database results or claim successful execution when an error occurs. Your primary objective is to deliver accurate, reliable, and structured data for downstream business analysis and visualization.",
                                    llm = llm ,
                                    verbose=True,
                                    tools=[execute_readonly_sql_tool]

)
        #The Visualization & Summary Agent selects and creates the best chart (using Plotly) based on the data and writes key insights in 3-4 bullet points.
        self.Visualization_Summary_Agent	= Agent(role="Expert Business Data Visualization and Insight Summarization Agent",
                                            goal="Analyze the retrieved business data, automatically select the most suitable chart type, generate interactive Plotly visualizations, and summarize the most important business insights in 3-4 concise bullet points to support data-driven decision-making.",
                                            backstory="You are an expert Business Data Visualization and Insight Summarization AI Agent specializing in data analysis, interactive visualization, and business intelligence. You work as a core component of a Multi-Modal Conversational Business Intelligence Platform. Your responsibility is to analyze structured data retrieved from enterprise databases, identify important business trends, patterns, comparisons, and performance metrics, and select the most appropriate visualization based on the dataset and user's query. You use Plotly to generate interactive charts such as bar charts, line charts, pie charts, scatter plots, and other suitable visualizations. You ensure that every chart is based on actual retrieved data, uses meaningful titles, appropriate labels, and accurate values. You also generate 3-4 concise bullet points highlighting the most important business insights, significant changes, and relevant performance findings. You avoid unsupported assumptions, misleading visualizations, and fabricated conclusions. Your primary objective is to transform raw business data into clear, interactive, and actionable insights that help users understand their business performance and make informed decisions.",
                                            llm = llm,
                                            verbose=True,
                                            tools=[create_plotly_chart_tool]
)
        #The TTS (Text-to-Speech) Agent converts written summary points into natural audio voice.
        self.TTS_agent = Agent (role="Expert Text-to-Speech (TTS) Audio Generation Agent",
                    goal="Convert business intelligence summaries and key insights into natural, clear, and professional spoken audio using Text-to-Speech models, ensuring accurate pronunciation of business metrics, numbers, and terminology.",
                    backstory="You are an expert Text-to-Speech AI Agent specializing in natural voice generation and audio communication. You work as a core component of a Multi-Modal Conversational Business Intelligence Platform. Your responsibility is to convert textual business summaries, analytical findings, and key insights generated by the Visualization and Summary Agent into high-quality spoken audio using TTS models such as OpenAI TTS. You ensure that the generated speech sounds natural, clear, and professional. You handle business terminology, numerical values, percentages, currency amounts, and technical terms with appropriate pronunciation. You preserve the original meaning of the summary and never add unsupported information. You generate concise audio explanations suitable for executives and non-technical users. You return the generated audio in a supported format for playback in the BI dashboard. If audio generation fails, you report the error and ensure that the original text summary remains available.",
                    llm = llm ,
                    verbose=True,
                    tools=[generate_tts_audio_tool]
)
bi_agent_object = Conservation_BI_Agent()



# 1. STT Task
stt_task = Task(
    description="""
Transcribe the provided audio input into text.

Identify the spoken language and preserve business terms,
numbers, dates, currencies, and metric names accurately.

Do not add explanations or modify the user's intent.
Mark unclear portions when reliable transcription is not
possible.
Input: {user_input}
If the input is plain text and not an audio file path, return it unchanged as the transcribed text.
""",
expected_output="""
A structured transcription result containing:
- Transcribed text
- Detected language, when available
- Unclear or uncertain portions, if any
- Transcription status

Do not fabricate missing speech.
""",
agent=bi_agent_object.STT_agent
)

# 2. Intent & Guardrail Task
intent_task = Task(
    description="""
Evaluate the user's query for business relevance, clarity,
authorization, and security risks.

Classify the request as ALLOW, REJECT, or CLARIFY.

Allow valid analytics requests that comply with platform
policies. Reject unauthorized or unsafe requests and explain
the reason.

Do not generate or execute SQL.
""",
expected_output="""
A structured result containing:
- Decision: ALLOW, REJECT, or CLARIFY
- Original user query
- Normalized business query, if allowed
- Reason for the decision
- Identified security risks, if any

Only ALLOW requests should proceed to Text-to-SQL.
""",
agent=bi_agent_object.Intent_Guardrail_Agent,
    context=[stt_task]
)

# 3. Text-to-SQL Task
sql_task = Task(
    description="""
Read the approved business query and inspect the database
schema using the available tools.

Generate SQL compatible with the configured database dialect:
PostgreSQL or Snowflake.

Validate that the query uses existing schema elements,
preserves the user's intended metric and filters, and complies
with read-only security policies.

Return the validated SQL for the Data Execution Agent.
If essential schema information is missing or the SQL
cannot be validated, clearly report the issue.
If the previous decision is REJECT or CLARIFY, do not generate SQL; pass that message forward instead.
""",
expected_output="""
A structured result containing:
- Generated SQL query
- Database dialect
- Tables and columns referenced
- Validation status
- Assumptions, if any
- Error or clarification message, if needed

Never claim that SQL is valid unless the required
validation checks have passed.
""",
agent= bi_agent_object.Text_to_SQL_Agent,
    context=[intent_task]
)

# 4. Data Execution Task
execution_task = Task(
    description="""
Execute the validated SQL query produced by the Text-to-SQL
Agent against the configured database.

Enforce server-side read-only restrictions and query limits.
Return the actual data with column names and row counts.

Handle execution errors and empty results explicitly.
Never modify database records or invent missing data.
""",
expected_output="""
A structured execution result containing:
- Execution status
- Column names
- Actual returned rows or a supported result reference
- Row count
- Database error details, if any

If execution fails, clearly report the failure.
Do not generate fictional results.
""",
agent=bi_agent_object.Data_Execution_Agent,
    context=[sql_task]
)

# 5. Visualization & Summary Task
visualization_task = Task(
    description="""
Analyze the actual results returned by the Data Execution
Agent.

Select an appropriate chart type based on the user's question,
available columns, data types, and number of records.

Create an interactive Plotly visualization and write
three to four concise business insight bullet points.

Every reported value and finding must be supported by
the retrieved data. If the data is insufficient, explain
the limitation instead of guessing.
""",
expected_output="""
A structured visualization and analysis result containing:
- Chart type and title
- Axis labels and units, where applicable
- Plotly figure, JSON, or dashboard-compatible HTML
- Three to four data-backed business insights
- Limitations or warnings, if applicable

Do not report insights that cannot be verified from
the supplied results.
""",
agent=bi_agent_object.Visualization_Summary_Agent,
    context=[execution_task]
)

# 6. TTS Task
tts_task = Task(
    description="""
Convert the approved business summary and key insights into
natural spoken audio using the configured Text-to-Speech
engine.

Preserve the meaning of every finding and use appropriate
pronunciation for numbers, percentages, currencies, and
business terminology.

Generate a dashboard-compatible audio file and report
its location and generation status.
""",
expected_output="""
A structured result containing:
- Audio generation status
- Generated audio file path or supported audio reference
- Audio format
- Text used for speech generation
- Error details, if generation fails

The original text summary must remain available even
if audio generation fails.
""",
agent=bi_agent_object.TTS_agent,
    context=[visualization_task]
)

# Sequential workflow for a voice query
crew = Crew(
    agents=[
        bi_agent_object.STT_agent,
        bi_agent_object.Intent_Guardrail_Agent,
        bi_agent_object.Text_to_SQL_Agent,
        bi_agent_object.Data_Execution_Agent,
        bi_agent_object.Visualization_Summary_Agent,
        bi_agent_object.TTS_agent 
    ],
    tasks=[
        stt_task,
        intent_task,
        sql_task,
        execution_task,
        visualization_task,
        tts_task
    ],
    process=Process.sequential,
    verbose=True
)
if __name__ == "__main__":  # import hone pe loop na chale (main.py agent.py import karti hai)
    while True:
        user = input("enter your query (text or audio file path, 'exit' to quit): ")
        if user.strip().lower() == "exit":
            break
        result = crew.kickoff(inputs={"user_input": user})
        print(result)

        # query + SQL + summary Supabase (user_clint) me save
        try:
            supabase.table("user_clint").insert({
                "user_query": user,
                "agent_repsons_for_sql": sql_task.output.raw,
                "agent_respons_summery": visualization_task.output.raw,
            }).execute()
        except Exception as e:
            print(f"Failed to store query: {e}")