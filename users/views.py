from django.shortcuts import render
from django.http import HttpResponse, JsonResponse,HttpResponseBadRequest
from google.auth import default
import os
from google.oauth2 import service_account
from google.auth.transport.requests import Request
from google.cloud import aiplatform
from google import genai
import requests
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.conf import settings
from django.core.cache import cache
from vertexai.generative_models import GenerativeModel
import vertexai
from django.views.decorators.csrf import csrf_exempt
from google.auth.transport.requests import AuthorizedSession
from django.views.decorators.http import require_POST
import json
from vertexai.language_models import ChatModel

PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT")
LOCATION = os.getenv("VERTEX_LOCATION", "us-central1")
MODEL = os.getenv("VERTEX_MODEL", "gemini-1.5-pro")

cache.clear()

def index(request):
    return HttpResponse("Hello, you are users")

def _authed_session():
    creds = service_account.Credentials.from_service_account_file(
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"],
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    return AuthorizedSession(creds)

def credentials(request):
    try:
        
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        GOOGLE_CLOUD_CREDENTIALS_FILE = os.path.join(BASE_DIR, "service-account.json")
        
        GOOGLE_CLOUD_CREDENTIALS = service_account.Credentials.from_service_account_file(
            GOOGLE_CLOUD_CREDENTIALS_FILE,
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        
        creds = GOOGLE_CLOUD_CREDENTIALS

        creds.refresh(Request())
        
        return JsonResponse({
            "project_id": creds.project_id,
            "credentials_type": type(creds).__name__,
            "valid": creds.valid,
            "token_present": bool(creds.token),
            "token": creds.token
        })
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
    
def ask_llm_data(request):
    try:

        BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        GOOGLE_CLOUD_CREDENTIALS_FILE = os.path.join(BASE_DIR, "service-account.json")
        
        GOOGLE_CLOUD_CREDENTIALS = service_account.Credentials.from_service_account_file(
            GOOGLE_CLOUD_CREDENTIALS_FILE,
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        
        creds = GOOGLE_CLOUD_CREDENTIALS

        aiplatform.init(
            project=creds.project_id,
            credentials=GOOGLE_CLOUD_CREDENTIALS,
            location="asia-south1",
        )
        chat_model = ChatModel.from_pretrained("chat-bison")
        chat = chat_model.start_chat()
        resp = chat.send_message("Hello!")
        print(resp.text)

    except Exception as e:
        return JsonResponse({"error": str(e)})
    
def genclient(request):
    print("Abccdd")
    try:
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        GOOGLE_CLOUD_CREDENTIALS_FILE = os.path.join(BASE_DIR, "service-account.json")

        # Load service account credentials
        creds = service_account.Credentials.from_service_account_file(
            GOOGLE_CLOUD_CREDENTIALS_FILE,
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )

        # Initialize Vertex AI with credentials + region
        vertexai.init(
            project=creds.project_id,
            location="asia-south1",
            credentials=creds,
        )

        # Use Gemini model
        model = GenerativeModel("gemini-1.5-flash")
        response = model.generate_content("Explain AI in simple words")

        return JsonResponse({"text": response.text})

    except Exception as e:
        # Return error so you see what went wrong instead of generic 500
        return JsonResponse({"error": str(e)}, status=500)

@require_POST
def chat(request):
    try:
        body = json.loads(request.body.decode("utf-8"))
        user_msg = body.get("message", "").strip()
        if not user_msg:
            return HttpResponseBadRequest("message is required")

        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": user_msg}],
                }
            ],
            # Optional safety/params:
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 1024,
                "topP": 0.95,
                "topK": 40,
            },
        }

        session = _authed_session()
        resp = session.post(GEN_URL, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()

        # Parse first candidate text safely:
        text = ""
        try:
            parts = data["candidates"][0]["content"]["parts"]
            # Concatenate any text parts:
            text = "".join(p.get("text", "") for p in parts if "text" in p)
        except Exception:
            text = json.dumps(data)  # fallback for debugging

        return JsonResponse({"reply": text})
    except requests.HTTPError as e:
        return JsonResponse({"error": f"Vertex error: {e.response.text}"}, status=502)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
