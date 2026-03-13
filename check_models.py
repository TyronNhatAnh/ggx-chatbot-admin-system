import google.generativeai as genai
import os
from dotenv import load_dotenv

# Load key từ file .env
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

genai.configure(api_key=api_key)

print("Các model bạn có thể sử dụng:")
for m in genai.list_models():
    if 'generateContent' in m.supported_generation_methods:
        print(f"- Tên model: {m.name}")
        print(f"  Mô tả: {m.description}")
        print("-" * 30)