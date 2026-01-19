import os
import requests
from dotenv import load_dotenv

# Load your API Key
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    print("ERROR: API Key not found in .env file!")
    exit()

print(f"Checking availability for Key ending in: ...{API_KEY[-5:]}")

# Ask Google for the list of models
url = f"https://generativelanguage.googleapis.com/v1beta/models?key={API_KEY}"

try:
    response = requests.get(url)
    
    if response.status_code == 200:
        data = response.json()
        print("\n--- AVAILABLE MODELS FOR YOU ---")
        found_flash = False
        
        for model in data.get('models', []):
            # We only care about models that can generate text (generateContent)
            if "generateContent" in model.get("supportedGenerationMethods", []):
                print(f"✅ {model['name']}")
                if "flash" in model['name']:
                    found_flash = True

        print("--------------------------------\n")
        
        if found_flash:
            print("RECOMMENDATION: Try using the specific version like 'models/gemini-1.5-flash-001'")
        else:
            print("RECOMMENDATION: 'Gemini 1.5 Flash' is missing. Switch to 'models/gemini-pro'")
            
    else:
        print(f"Error accessing API: {response.status_code}")
        print(response.text)

except Exception as e:
    print(f"Connection Failed: {e}")