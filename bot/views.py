from django.shortcuts import render
import json, os, requests
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
import ollama  # Alla
import speech_recognition as sr
import pyttsx3

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
print(TELEGRAM_API)
WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET", "devsecret")
# Create your views here.

@csrf_exempt
def telegram_webhook(request, secret: str):
    print(secret)
    """if secret != WEBHOOK_SECRET:
        return HttpResponseForbidden("Bad secret")"""

    if request.method == "POST":
        data = json.loads(request.body.decode("utf-8"))
        print("DATAID:",data)
        chat_id = data.get("message", {}).get("chat", {}).get("id")
        print("chat ID:",chat_id)
        text = data.get("message", {}).get("text", "")
        print("TEXT MESSAGE",text)

        reply = "Hello, world!" if text == "/start" else f"Echo: {text}"
        print("REPLAY::::::",reply)
        if chat_id:
            Res = requests.post(f"{TELEGRAM_API}/sendMessage",
                          json={"chat_id": chat_id, "text": reply})
            print("TESTSTS",Res)
    return JsonResponse({"ok": True})

def chat_with_model(request):
    query = request.GET.get("q", "hello")
    response = ollama.chat(model="llama3.2", messages=[{"role": "user", "content": query}])
    print(response)
    #return JsonResponse({"response": response['message']})
    content = response['message'].content  

    return JsonResponse({"response": content})

def listen_and_ask(request):
    recognizer = sr.Recognizer()
    mic = sr.Microphone()

    try:
        with mic as source:
            print("🎤 Speak now...")
            recognizer.adjust_for_ambient_noise(source)
            audio = recognizer.listen(source)

        # Speech to text
        query = recognizer.recognize_google(audio)

        # Send to Ollama
        response = ollama.chat(
            model="llama3.2",
            messages=[{"role": "user", "content": query}]
        )
        answer = response['message'].content

        return JsonResponse({"query": query, "response": answer})

    except sr.UnknownValueError:
        return JsonResponse({"error": "Could not understand audio"}, status=400)

    except sr.RequestError as e:
        return JsonResponse({"error": f"Speech recognition request failed: {e}"}, status=500)

    except Exception as e:
        # Catch *any* other error so Django never returns None
        return JsonResponse({"error": str(e)}, status=500)
    
def hospital_chat(request):
    query = request.GET.get("q", "")

    if not query:
        return JsonResponse({"error": "No query provided"}, status=400)

    # Example system prompt to guide the model
    system_prompt = """
    You are an AI assistant for a hospital call center.
    - Greet politely
    - Help with appointments, doctor info, visiting hours
    - Do NOT give medical diagnosis
    - Always suggest speaking with a doctor for medical concerns
    """

    response = ollama.chat(
        model="llama3.2",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query}
        ]
    )

    answer = response['message'].content
    return JsonResponse({"response": answer})

def voice_chat(request):
    recognizer = sr.Recognizer()
    mic = sr.Microphone()

    # Initialize text-to-speech
    tts = pyttsx3.init()

    while True:
        try:
            with mic as source:
                print("🎤 Speak now (say 'exit' to quit)...")
                recognizer.adjust_for_ambient_noise(source)
                audio = recognizer.listen(source)

            # Step 1: Convert voice → text
            query = recognizer.recognize_google(audio)
            print(f"🗣 You: {query}")

            if query.lower() in ["exit", "quit", "stop"]:
                print("👋 Exiting voice assistant.")
                break

            # Step 2: Send to Ollama
            response = ollama.chat(
                model="llama3.2",
                messages=[{"role": "user", "content": query}]
            )
            answer = response['message'].content
            print(f"🤖 Ollama: {answer}")

            # Step 3: Speak the response
            tts.say(answer)
            tts.runAndWait()

        except sr.UnknownValueError:
            print("❌ Could not understand audio")
        except Exception as e:
            print(f"⚠️ Error: {e}")


