import sqlite3
import os
import json
import requests
from fastapi import FastAPI, Request, Form, Response
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv

# --- CONFIGURATION ---
load_dotenv()
app = FastAPI()

# Setup Folders
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# AI Config (Using the one that worked!)
API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_NAME = "models/gemini-flash-latest"
AI_URL = f"https://generativelanguage.googleapis.com/v1beta/{MODEL_NAME}:generateContent?key={API_KEY}"

# Database Setup (Auto-creates user table)
DB_NAME = "contracthawk.db"
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, password TEXT)''')
    # Create a default admin user
    try:
        c.execute("INSERT INTO users VALUES ('Agent', 'Secret')")
        conn.commit()
    except:
        pass 
    conn.close()

init_db()

# --- ROUTES ---

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

# --- THE AI SCANNER ---

@app.post("/api/scan")
async def scan_contract(request: Request):
    data = await request.json()
    content = data.get("content", "")
    
    if not content:
        return {"error": "No content provided"}

    # The Prompt
    prompt = f"""
    Act as a high-stakes legal AI. Analyze this contract.
    Identify high-risk clauses, hidden fees, and privacy traps.
    
    RETURN RAW JSON ONLY (No markdown formatting):
    {{
        "risk_score": (Integer 0-100),
        "verdict": "SAFE / CAUTION / CRITICAL",
        "summary": "1 sentence executive summary.",
        "red_flags": ["Short bullet point 1", "Short bullet point 2", "Short bullet point 3"]
    }}
    
    Contract Text: {content[:10000]}
    """
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }

    try:
        # Using Direct Requests (Because it's bulletproof)
        response = requests.post(AI_URL, headers={'Content-Type': 'application/json'}, json=payload)
        
        if response.status_code == 200:
            result = response.json()
            raw_text = result['candidates'][0]['content']['parts'][0]['text']
            # Clean up potential markdown formatting from AI
            clean_text = raw_text.replace("```json", "").replace("```", "").strip()
            return json.loads(clean_text)
        else:
            return {"risk_score": 0, "verdict": "ERROR", "summary": "Neural Link Severed", "red_flags": [response.text]}
            
    except Exception as e:
        return {"risk_score": 0, "verdict": "ERROR", "summary": "System Crash", "red_flags": [str(e)]}