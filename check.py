import requests
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("❌ Key missing in .env")
    exit()

# Ask Google: "List all your models"
url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"

try:
    print("SEARCHING FOR AVAILABLE MODELS...")
    response = requests.get(url)
    
    if response.status_code == 200:
        data = response.json()
        print("\n✅ YOUR AVAILABLE MODELS:")
        for m in data.get('models', []):
            # Only show models that can write text (generateContent)
            if 'generateContent' in m.get('supportedGenerationMethods', []):
                print(f" -> {m['name']}")
    else:
        print(f"❌ ERROR: {response.text}")

except Exception as e:
    print(f"❌ CRASH: {e}")