import os
import google.generativeai as genai
from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=API_KEY)

gemini_model = genai.GenerativeModel("gemini-1.5-flash")
chat_sessions = {}

def chunk_text_with_langchain(text):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=5000,
        chunk_overlap=300,
        separators=["\n\n", "\n", ".", "!", "?", ",", " "]
    )
    return splitter.split_text(text)

def set_gemini_context(session_id, text):
    chunks = chunk_text_with_langchain(text)
    if session_id not in chat_sessions:
        chat_sessions[session_id] = {
            "chat": gemini_model.start_chat(history=[]),
            "context": chunks
        }
    else:
        chat_sessions[session_id]["context"] = chunks

def ask_gemini(msg, session_id="default_session"):
    if session_id not in chat_sessions:
        return "No context found. Please upload a file first."

    chat = chat_sessions[session_id]["chat"]
    context_chunks = chat_sessions[session_id]["context"]
    context_text = "\n\n".join(context_chunks[:100])  # limit context

    prompt = f"""Context:
{context_text}

User Question:
{msg}
"""
    response = chat.send_message(prompt)
    return response.text
