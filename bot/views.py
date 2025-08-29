from django.shortcuts import render
import json, os, requests
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
import ollama  # Alla
import speech_recognition as sr

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


