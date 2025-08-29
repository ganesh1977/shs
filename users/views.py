from django.shortcuts import render
from django.http import HttpResponse, JsonResponse,HttpResponseBadRequest
from google.auth import default
import os
from google.oauth2 import service_account
from google.auth.transport.requests import Request
from google.cloud import aiplatform, speech, texttospeech
from google import genai
import requests
from rest_framework import status
from rest_framework.decorators import api_view , permission_classes
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
import io
from rest_framework.permissions import AllowAny
from pydub import AudioSegment

PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT")
LOCATION = os.getenv("VERTEX_LOCATION", "asia-south1")
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

def authenticate():
    print("AASFSD")
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
    GOOGLE_CLOUD_CREDENTIALS_FILE = os.path.join(BASE_DIR, "service-account.json")
        
    GOOGLE_CLOUD_CREDENTIALS = service_account.Credentials.from_service_account_file(
        GOOGLE_CLOUD_CREDENTIALS_FILE,
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )

    creds = GOOGLE_CLOUD_CREDENTIALS

    return creds

def credentials(request):
    try:       
        creds = authenticate()
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
    
class MyClass:
    def say_hello(self, name):
        print(f"Hello, {name}!")

@api_view(['GET'])
def ask_llm_data(request):
    try:
        creds = authenticate()

        aiplatform.init(
            project=creds.project_id,
            credentials=creds,
            location="asia-south1",
        )

        obj = MyClass()       

        chat_model = obj.say_hello("World")
        chat = chat_model.start_chat()
        resp = chat.send_message("Hello!")
        print(resp.text)

    except Exception as e:
        return JsonResponse({"error": str(e)})

@api_view(['GET'])
def genclient(request):
    try:
        creds = authenticate()

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

@api_view(['POST'])
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
    
@api_view(['POST'])
def speech_to_text(audio_file_path):

    credentials = service_account.Credentials.from_service_account_file(
        "/home/ganesh/shs/service-account.json"
    )
    client = speech.SpeechClient(credentials=credentials)

    #client = speech.SpeechClient()
    audio_file_path = "/home/ganesh/Downloads/tmpmuzil05u.mp3"
    with open(audio_file_path, "rb") as audio_file:
        content = audio_file.read()

    audio = speech.RecognitionAudio(content=content)
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        #sample_rate_hertz=44100,
        language_code="en-US",
    )

    response = client.recognize(config=config, audio=audio)
    transcript = " ".join([result.alternatives[0].transcript for result in response.results])
    return transcript

@api_view(["POST"])
@permission_classes([AllowAny])
def speechtext(request):
    audio_file = request.FILES["file"]
    file_bytes = audio_file.read()

    # Convert to mono
    audio = AudioSegment.from_file(io.BytesIO(file_bytes))
    audio = audio.set_channels(1)  # force mono
    out = io.BytesIO()
    audio.export(out, format="wav")
    out.seek(0)
    mono_bytes = out.read()

    # Google STT
    client = speech.SpeechClient.from_service_account_file(
        "/home/ganesh/shs/service-account.json"
    )
    audio = speech.RecognitionAudio(content=mono_bytes)
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        language_code="en-US",
        sample_rate_hertz=44100,  # or omit, let GCP auto-detect
    )

    response = client.recognize(config=config, audio=audio)
    transcript = " ".join([r.alternatives[0].transcript for r in response.results])

    return Response({"transcript": transcript})

@api_view(["POST"])
@permission_classes([AllowAny])
def generate_audio(request):
    text = request.data.get("text")
    if not text:
        return JsonResponse({"error": "Missing 'text' in request"}, status=400)

    # Defaults
    language_code = request.data.get("language_code", "en-US")
    gender = request.data.get("gender", "NEUTRAL").upper()
    format_type = request.data.get("format", "mp3").lower()

    # Map format to GCP encoding
    encoding_map = {
        "mp3": texttospeech.AudioEncoding.MP3,
        "wav": texttospeech.AudioEncoding.LINEAR16,
        "ogg": texttospeech.AudioEncoding.OGG_OPUS,
    }
    audio_encoding = encoding_map.get(format_type, texttospeech.AudioEncoding.MP3)

    # Map gender
    gender_map = {
        "MALE": texttospeech.SsmlVoiceGender.MALE,
        "FEMALE": texttospeech.SsmlVoiceGender.FEMALE,
        "NEUTRAL": texttospeech.SsmlVoiceGender.NEUTRAL,
    }
    ssml_gender = gender_map.get(gender, texttospeech.SsmlVoiceGender.NEUTRAL)

    client = texttospeech.TextToSpeechClient.from_service_account_file(
        "/home/ganesh/shs/service-account.json"
    )

    synthesis_input = texttospeech.SynthesisInput(text=text)
    voice = texttospeech.VoiceSelectionParams(
        language_code=language_code,
        ssml_gender=ssml_gender,
    )
    audio_config = texttospeech.AudioConfig(audio_encoding=audio_encoding)

    response = client.synthesize_speech(
        input=synthesis_input, voice=voice, audio_config=audio_config
    )

    # Decide content-type based on format
    mime_types = {
        "wav": "audio/wav",
        "ogg": "audio/ogg",
    }
    
    print(mime_types)
    content_type = mime_types.get(format_type, "audio")

    return HttpResponse(response.audio_content, content_type=content_type)