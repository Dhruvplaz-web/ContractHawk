import sqlite3
import os
import json
import requests
import io
from fastapi import FastAPI, Request, Form, Response, File, UploadFile
from fastapi.responses import RedirectResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
from PyPDF2 import PdfReader
from docx import Document
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import simpleSplit

load_dotenv()
app = FastAPI()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# --- CONFIGURATION ---
API_KEY = os.getenv("GEMINI_API_KEY")

# --- FIX: USING THE "LATEST" ALIAS (Guaranteed Free Tier Access) ---
# This alias points to the stable production Flash model which has quota.
MODEL_NAME = "models/gemini-flash-latest" 
AI_URL = f"https://generativelanguage.googleapis.com/v1beta/{MODEL_NAME}:generateContent?key={API_KEY}"

# --- SAFETY OVERRIDE (Allows analysis of legal threats) ---
SAFETY_SETTINGS = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
]

DB_NAME = "contracthawk.db"
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, password TEXT)''')
    try:
        c.execute("INSERT INTO users VALUES ('Agent', 'Secret')")
        conn.commit()
    except:
        pass 
    conn.close()

init_db()

@app.get("/", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/auth/register")
async def register(request: Request, username: str = Form(...), password: str = Form(...)):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("INSERT INTO users VALUES (?, ?)", (username, password))
        conn.commit()
        return templates.TemplateResponse("login.html", {"request": request, "msg": "ID CREATED. PROCEED TO LOGIN.", "msg_color": "text-green-500"})
    except:
        return templates.TemplateResponse("login.html", {"request": request, "msg": "ERROR: ID ALREADY EXISTS", "msg_color": "text-red-500"})

@app.post("/auth/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
    user = c.fetchone()
    if user:
        response = RedirectResponse(url="/dashboard", status_code=303)
        response.set_cookie(key="agent_id", value=username)
        return response
    else:
        return templates.TemplateResponse("login.html", {"request": request, "msg": "ACCESS DENIED", "msg_color": "text-red-500"})

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    user = request.cookies.get("agent_id")
    if not user:
        return RedirectResponse(url="/")
    return templates.TemplateResponse("dashboard.html", {"request": request, "user": user})

@app.get("/logout")
async def logout(response: Response):
    response = RedirectResponse(url="/")
    response.delete_cookie("agent_id")
    return response

# --- FILE UPLOAD ROUTE ---
@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    try:
        print(f"Received file: {file.filename}") 
        contents = await file.read()
        text = ""
        filename = file.filename.lower()

        if filename.endswith(".pdf"):
            reader = PdfReader(io.BytesIO(contents))
            for page in reader.pages:
                text += page.extract_text() + "\n"
        elif filename.endswith(".docx"):
            doc = Document(io.BytesIO(contents))
            for para in doc.paragraphs:
                text += para.text + "\n"
        elif filename.endswith(".txt"):
            text = contents.decode("utf-8")
        else:
            return {"error": "Invalid file format. Only PDF, DOCX, TXT allowed."}

        return {"text": text}

    except Exception as e:
        print(f"CRITICAL UPLOAD ERROR: {e}")
        return {"error": "Decryption Failed. Check Server Terminal."}

# --- 1. NEUTRALIZE AGENT (The Rewriter) ---
@app.post("/api/neutralize")
async def neutralize_contract(request: Request):
    data = await request.json()
    content = data.get("content", "")
    red_flags = data.get("red_flags", [])

    if not content:
        return {"error": "No content to fix."}

    prompt = f"""
    Act as a professional lawyer. 
    The following contract has these issues: {json.dumps(red_flags)}.
    
    YOUR TASK:
    Rewrite the contract to be FAIR and SAFE. 
    1. Remove or modify the predatory clauses (e.g., change 10-year non-competes to 6 months, remove IP theft).
    2. Keep the standard/safe parts exactly as they are.
    3. Return the FULL corrected contract text.
    
    Contract Text: {content[:15000]}
    """
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "safetySettings": SAFETY_SETTINGS
    }

    try:
        response = requests.post(AI_URL, headers={'Content-Type': 'application/json'}, json=payload)
        if response.status_code == 200:
            result = response.json()
            fixed_text = result['candidates'][0]['content']['parts'][0]['text']
            return {"fixed_text": fixed_text}
        else:
            print(f"API ERROR: {response.text}") 
            return {"fixed_text": "Error: Could not neutralize threats."}
    except Exception as e:
        return {"fixed_text": f"System Failure: {str(e)}"}

# --- 2. PDF GENERATOR ROUTE ---
@app.post("/api/download_pdf")
async def download_pdf(request: Request):
    data = await request.json()
    text = data.get("text", "")

    # Create PDF in memory
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    
    c.setFont("Helvetica-Bold", 16)
    c.drawString(72, height - 72, "SECURE CONTRACT // SAFE VERSION")
    
    c.setFont("Helvetica", 12)
    y = height - 100
    margin = 72
    
    # Simple text wrapping
    for line in text.split('\n'):
        wrapped_lines = simpleSplit(line, "Helvetica", 12, width - 2*margin)
        for wrapped_line in wrapped_lines:
            if y < 72: # New page
                c.showPage()
                y = height - 72
            c.drawString(margin, y, wrapped_line)
            y -= 14
            
    c.save()
    buffer.seek(0)
    
    return StreamingResponse(
        buffer, 
        media_type="application/pdf", 
        headers={"Content-Disposition": "attachment; filename=Safe_Contract.pdf"}
    )

# --- 3. INTERROGATOR AGENT (Chat) ---
@app.post("/api/ask")
async def ask_contract(request: Request):
    data = await request.json()
    content = data.get("content", "")
    question = data.get("question", "")

    if not content or not question:
        return {"answer": "Error: Missing data context."}

    prompt = f"""
    Act as a legal expert. The user is asking about the following contract.
    
    CONTRACT CONTEXT:
    {content[:15000]}
    
    USER QUESTION:
    "{question}"
    
    INSTRUCTIONS:
    - Answer based ONLY on the contract text provided.
    - Be concise, professional, and direct.
    - If the contract doesn't mention it, say "The contract does not specify this."
    """
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "safetySettings": SAFETY_SETTINGS
    }

    try:
        response = requests.post(AI_URL, headers={'Content-Type': 'application/json'}, json=payload)
        if response.status_code == 200:
            result = response.json()
            answer = result['candidates'][0]['content']['parts'][0]['text']
            return {"answer": answer}
        else:
            print(f"CHAT API ERROR: {response.text}") 
            return {"answer": "Connection jammed. check terminal for error."}
    except Exception as e:
        return {"answer": f"System Error: {str(e)}"}

# --- SCANNER AGENT ---
@app.post("/api/scan")
async def scan_contract(request: Request):
    data = await request.json()
    content = data.get("content", "")
    
    if not content:
        return {"error": "No content provided"}

    prompt = f"""
    Act as a highly experienced legal consultant. 
    Analyze this contract. Distinguish between Standard (Safe) and Predatory (Risky).
    
    SCORING:
    - 0-30: Standard terms.
    - 31-70: Cautionary.
    - 71-100: Predatory/Critical.

    RETURN RAW JSON ONLY:
    {{
        "risk_score": (Integer 0-100),
        "verdict": "SAFE / CAUTION / CRITICAL",
        "summary": "1 sentence executive summary.",
        "red_flags": ["Short bullet point 1", "Short bullet point 2"]
    }}
    
    Contract Text: {content[:15000]}
    """
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "safetySettings": SAFETY_SETTINGS
    }

    try:
        response = requests.post(AI_URL, headers={'Content-Type': 'application/json'}, json=payload)
        
        if response.status_code == 200:
            result = response.json()
            raw_text = result['candidates'][0]['content']['parts'][0]['text']
            clean_text = raw_text.replace("```json", "").replace("```", "").strip()
            return json.loads(clean_text)
        else:
            print(f"SCAN API ERROR: {response.text}") # Debug print
            return {"risk_score": 0, "verdict": "ERROR", "summary": "Neural Link Severed", "red_flags": []}
    except Exception as e:
        return {"risk_score": 0, "verdict": "ERROR", "summary": f"System Crash: {e}", "red_flags": []}