import os

import streamlit as st
from dotenv import load_dotenv
from langchain_core.messages import AIMessage, ToolMessage

from src.agent.graph import MAX_ITERATIONS, MODEL_NAME, run_agent
from src.eval.harness import extract_last_successful_query

load_dotenv()

GROQ_MODEL = "openai/gpt-oss-120b"
LOCAL_LABEL = f"Local ({MODEL_NAME})"
HOSTED_LABEL = f"Hosted ({GROQ_MODEL} via Groq)"

EXAMPLE_QUESTIONS = [
    "Which artist has the most albums?",
    "What genre is the track \"Balls to the Wall\"?",
    "Which customer has spent the most money in total?",
    "How many tracks are in the playlist named \"Classical\"?",
]

st.set_page_config(page_title="Chinook Text-to-SQL Agent", page_icon="🎵")
st.title("🎵 Chinook Text-to-SQL Agent")
st.caption(
    "Ask a question about the Chinook music store database in plain English. "
    "The agent explores the schema, writes SQL, runs it on a read-only connection, "
    "and self-corrects on errors."
)

backend = st.selectbox("Model backend", [LOCAL_LABEL, HOSTED_LABEL], index=0)

if backend == HOSTED_LABEL:
    st.caption(
        "⚠️ Requires internet and Groq's free-tier API. Your question and the "
        "database schema leave this machine and are sent to Groq. This is a "
        "comparison option — the local model above is this project's primary, "
        "offline pipeline."
    )

with st.expander("Try an example question"):
    for eq in EXAMPLE_QUESTIONS:
        if st.button(eq):
            st.session_state["question"] = eq

question = st.text_input("Your question", key="question")
submit = st.button("Ask", type="primary")

if submit and question:
    with st.spinner("Thinking..."):
        try:
            if backend == HOSTED_LABEL:
                if not os.getenv("GROQ_API_KEY"):
                    raise RuntimeError(
                        "GROQ_API_KEY is not set. Add it to a local .env file to use "
                        "the hosted backend."
                    )
                from langchain_groq import ChatGroq

                llm = ChatGroq(model=GROQ_MODEL, temperature=0)
                result = run_agent(question, llm=llm)
            else:
                result = run_agent(question)
        except Exception as e:
            st.error(
                f"The {backend} backend failed: {e}\n\n"
                "Try switching to the Local backend, which runs fully offline and "
                "has no external dependency."
            )
            st.stop()

    messages = result["messages"]

    st.subheader("Tool-call trace")
    for msg in messages:
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tc in msg.tool_calls:
                st.code(f"{tc['name']}({tc['args']})", language="text")
        elif isinstance(msg, ToolMessage):
            content = str(msg.content)
            st.text(content if len(content) < 400 else content[:400] + " ...")

    sql, _ = extract_last_successful_query(messages)
    if sql:
        st.subheader("Final SQL")
        st.code(sql, language="sql")

    st.subheader("Answer")
    final_message = messages[-1]
    st.write(getattr(final_message, "content", ""))

    st.caption(f"Used {result['iterations']}/{MAX_ITERATIONS} agent iterations.")
