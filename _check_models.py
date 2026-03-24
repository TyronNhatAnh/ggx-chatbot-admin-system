from app.llm.vertex_credentials import create_vertex_client

import json
import google.genai as genai_pkg
from google import genai
from google.oauth2 import service_account
from app.config import settings

print(f"google-genai version: {genai_pkg.__version__}\n")

_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]
with open(settings.vertex_ai_credentials_file) as f:
    config = json.load(f)
sa_info = json.loads(config[settings.vertex_ai_sa_key])
credentials = service_account.Credentials.from_service_account_info(sa_info, scopes=_SCOPES)

candidates = [
    "gemini-3-flash",
    "gemini-3-pro",
    "gemini-3-flash-preview",
    "gemini-3-pro-preview",
]

for location in [
    "global",
    "us-central1",         # Iowa
]:
    print(f"=== {location} ===")
    client = genai.Client(vertexai=True, project=sa_info["project_id"], location=location, credentials=credentials)
    for name in candidates:
        try:
            m = client.models.get(model=name)
            print(f"  OK : {name}")
        except Exception as e:
            code = str(e)[:20]
            print(f"  ERR: {name} ({code}...)")
    print()


