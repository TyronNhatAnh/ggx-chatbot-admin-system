import json

from google import genai
from google.oauth2 import service_account

from app.config import settings

_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]


def create_vertex_client() -> genai.Client:
    """Create a Vertex AI Gemini client using service account credentials from file."""
    with open(settings.vertex_ai_credentials_file) as f:
        config = json.load(f)
    sa_info = json.loads(config[settings.vertex_ai_sa_key])
    credentials = service_account.Credentials.from_service_account_info(
        sa_info, scopes=_SCOPES
    )
    return genai.Client(
        vertexai=True,
        project=sa_info["project_id"],
        location=settings.vertex_ai_location,
        credentials=credentials,
    )
