from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import os
import pytesseract
from PIL import Image
import fitz 
import requests
from deep_translator import GoogleTranslator
from werkzeug.utils import secure_filename
from chatbot import ask_gemini, set_gemini_context, chat_sessions
from langchain_text_splitters import RecursiveCharacterTextSplitter


app = Flask(__name__)
app.secret_key = "super_secret_key"
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

ELEVENLABS_API_KEY = os.getenv("Eleven_labs_API_key")
print(f"LOADED API KEY: {ELEVENLABS_API_KEY}")

voice_map = {
    "Rachel (EN)": "21m00Tcm4TlvDq8ikWAM",
    "Domi (EN)": "AZnzlk1XvdvUeBnXmlld",
    "Bella (EN)": "EXAVITQu4vr4xnSDxMaL"
}

language_map = {
    "en": "english",
    "hi": "hindi",
    "fr": "french",
    "es": "spanish",
    "de": "german",
    "ja": "japanese"
}

@app.route("/home")
def home():
    return render_template("home.html")

@app.route("/")
def home_redirect():
    return redirect(url_for('home'))

def get_active_content():
    if session.get('manual_text_input'):
        return session['manual_text_input'].strip(), None

    filepath = session.get('last_uploaded_file')
    if filepath and os.path.exists(filepath):
        ext = filepath.lower().split(".")[-1]
        if ext == "pdf":
            with fitz.open(filepath) as doc:
                return " ".join([page.get_text() for page in doc]), None
        elif ext in ["jpg", "jpeg", "png"]:
            image = Image.open(filepath)
            return pytesseract.image_to_string(image), None
        elif ext == "txt":
            with open(filepath, "r", encoding="utf-8") as f:
                return f.read(), None
        else:
            return None, "❌ Unsupported file type."

    return None, "❌ No input provided."

# ✅ Upload or Text Input
@app.route("/project", methods=["GET", "POST"])
def index():
    message = None  # Initialize message to pass into the template

    if request.method == "POST":
        file = request.files.get("file")
        manual_text = request.form.get("manual_text", "").strip()

        if manual_text:
            session['manual_text_input'] = manual_text
            session.pop('last_uploaded_file', None)
            chat_sessions.pop("chatbot_session", None)
            set_gemini_context("chatbot_session", manual_text)
            message = "✅ Your text has been submitted successfully!"

        elif file and file.filename != "":
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file.save(filepath)
            session['last_uploaded_file'] = filepath
            session.pop('manual_text_input', None)
            chat_sessions.pop("chatbot_session", None)
            content, _ = get_active_content()
            if content:
                set_gemini_context("chatbot_session", content)
            message = "✅ Your file has been uploaded successfully!"

        else:
            return render_template("index.html",
                                   voices=voice_map.keys(),
                                   languages=language_map,
                                   voice_map=voice_map,
                                   error="❌ Please upload a file or enter text.")

    return render_template("index.html",
                           voices=voice_map.keys(),
                           languages=language_map,
                           voice_map=voice_map,
                           message=message)  # Pass message always


@app.route("/generate_audio", methods=["POST"])
def generate_audio():
    text, error = get_active_content()
    if error:
        return error
    
    voice_name = request.form.get("voice")
    voice_id = voice_map.get(voice_name, list(voice_map.values())[0])
    target_lang = request.form.get("language", "en")

    if target_lang != "en":
        text = GoogleTranslator(source='auto', target=target_lang).translate(text)

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {"xi-api-key": ELEVENLABS_API_KEY, "Content-Type": "application/json"}
    payload = {
        "text": text[:40000],
        "model_id": "eleven_monolingual_v1",
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}
    }

    response = requests.post(url, json=payload, headers=headers)

    if response.status_code == 200:
        audio_path = os.path.join("static", "output.mp3")
        with open(audio_path, "wb") as f:
            f.write(response.content)
        return render_template("preview.html", audio_file=audio_path, raw_text=text)
    else:
        print("❌ ElevenLabs API Error:", response.status_code, response.text)
        return "❌ Failed to generate audio."


@app.route("/generate_quiz", methods=["POST"])
def generate_quiz():
    text, error = get_active_content()
    if error:
        return error

    num_questions = request.form.get("num_questions", "5")
    try:
        num_questions = int(num_questions)
    except:
        num_questions = 5

    prompt = f"""
Generate {num_questions} multiple choice questions from the content below.

Q1. Your question here?
A. Option A
B. Option B
C. Option C
D. Option D
Answer: C

NO explanations. Strictly follow format.

CONTENT:
{text[:10000000]}
"""

    session_id = "quiz_session"
    set_gemini_context(session_id, text)
    raw = ask_gemini(prompt, session_id)

    questions_raw = raw.strip().split("\n\n")
    quiz_data = []
    for block in questions_raw:
        lines = [line.strip() for line in block.strip().split("\n") if line.strip()]
        if len(lines) >= 6 and lines[0].startswith("Q") and lines[-1].lower().startswith("answer"):
            quiz_data.append({
                "question": lines[0],
                "options": lines[1:5],
                "answer": lines[-1].replace("Answer:", "").strip()
            })

    if not quiz_data:
        return "❌ Failed to parse quiz. Try again."

    return render_template("quiz.html", quiz=quiz_data)


@app.route("/generate_summary", methods=["GET"])
def generate_summary():
    text, error = get_active_content()
    if error:
        return error

    session_id = "summary_session"
    set_gemini_context(session_id, text)

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=5000, chunk_overlap=300)
    chunks = text_splitter.split_text(text)

    summaries = []
    for idx, chunk in enumerate(chunks):
        part_summary = ask_gemini(f"Summarize part {idx + 1}:\n\n{chunk}", session_id)
        summaries.append(part_summary)

    final_summary = ask_gemini("Combine these summaries:\n\n" + "\n\n".join(summaries), session_id)

    return render_template("summary.html", summary=final_summary, original=text)


@app.route("/chat", methods=["POST"])
def chat():
    user_message = request.json.get("message")
    session_id = "chatbot_session"
    if not user_message:
        return jsonify({"response": "No message provided."}), 400

    try:
        reply = ask_gemini(user_message, session_id)
        return jsonify({"response": reply})
    except Exception as e:
        return jsonify({"response": f"AI error: {str(e)}"})


if __name__ == "__main__":
    print("🔥 Server running on http://localhost:5000")
    app.run(debug=True)
