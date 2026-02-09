import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

api_key = os.getenv('GOOGLE_API_KEY')
print(f"API Key: {api_key[:20]}..." if api_key else "NO KEY")

try:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')

    response = model.generate_content("Say hello!")
    print(f"✅ Gemini works!")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"❌ Error: {e}")