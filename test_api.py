import requests
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

# --- CONFIGURATION ---
# Switching to the stable version that definitely has free quota
MODEL_NAME = "models/gemini-flash-latest"
URL = f"https://generativelanguage.googleapis.com/v1beta/{MODEL_NAME}:generateContent?key={api_key}"

headers = {'Content-Type': 'application/json'}
data = {
    "contents": [{
        "parts": [{"text": "Reply with 'SYSTEM OPERATIONAL' if you can hear me."}]
    }]
}

try:
    print(f"📡 Connecting to {MODEL_NAME}...")
    response = requests.post(URL, headers=headers, json=data)
    
    if response.status_code == 200:
        result = response.json()
        print("\n✅ SUCCESS! The Brain is Online.")
        try:
            print(f"🤖 AI SAYS: {result['candidates'][0]['content']['parts'][0]['text']}")
        except:
            print("Response received (Parsing detail skipped).")
    else:
        print(f"\n❌ ERROR {response.status_code}: {response.text}")

except Exception as e:
    print(f"\n❌ CRASH: {e}")