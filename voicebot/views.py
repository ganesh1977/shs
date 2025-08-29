from django.shortcuts import render
from django.http import HttpResponse, JsonResponse,HttpResponseBadRequest
import asyncio, base64, json
from channels.generic.websocket import AsyncWebsocketConsumer
from google.cloud import speech_v1p1beta1 as speech
from google.cloud import texttospeech
from django.views.decorators.csrf import csrf_exempt

# Create your views here.

def index(request):
    return render(request,"index.html")

class VoiceStreamConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.lang = "en-US"
        await self.accept()
        self._stt_client = speech.SpeechClient()
        self._tts_client = texttospeech.TextToSpeechClient()
        self._requests_q = asyncio.Queue()
        self._stt_task = asyncio.create_task(self._stt_loop())

    async def disconnect(self, code):
        self._stt_task.cancel()

    async def receive(self, text_data=None, bytes_data=None):
        if text_data:
            msg = json.loads(text_data)
            if msg.get("type") == "lang":
                self.lang = msg.get("code", "en-US")
                return
        if bytes_data:
            # if client sends raw bytes, base64 it; but most send JSON base64
            await self._requests_q.put(bytes_data)
        else:
            # expecting JSON with 'audio' field in base64
            msg = json.loads(text_data)
            if "audio" in msg:
                await self._requests_q.put(base64.b64decode(msg["audio"]))

    async def _stt_loop(self):
        # GCP streaming recognize request generator
        def req_gen():
            # first message: config
            cfg = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.WEBM_OPUS,
                language_code=self.lang,
                enable_automatic_punctuation=True,
                interim_results=True,
            )
            yield speech.StreamingRecognizeRequest(streaming_config=speech.StreamingRecognitionConfig(
                config=cfg, interim_results=True, single_utterance=False
            ))
            while True:
                chunk = asyncio.run(self._requests_q.get())
                if chunk is None: break
                yield speech.StreamingRecognizeRequest(audio_content=chunk)

        # Note: speech client is not async, so run in executor
        loop = asyncio.get_running_loop()
        responses = await loop.run_in_executor(None, lambda: self._stt_client.streaming_recognize(requests=req_gen()))
        # Iterate responses in a thread; in practice, wrap for safety.

        for resp in responses:
            for result in resp.results:
                alt = result.alternatives[0].transcript
                if result.is_final:
                    await self.send(json.dumps({"event":"final", "transcript": alt}))
                    # synthesize reply
                    mp3 = self._tts(alt, self.lang)
                    await self.send(json.dumps({"event":"reply_mp3_b64", "data": base64.b64encode(mp3).decode()}))
                else:
                    await self.send(json.dumps({"event":"interim", "transcript": alt}))

    def _tts(self, text, lang):
        voice = texttospeech.VoiceSelectionParams(language_code=lang, ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL)
        audio_cfg = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3)
        inp = texttospeech.SynthesisInput(text=text or "I couldn't hear anything.")
        return self._tts_client.synthesize_speech(input=inp, voice=voice, audio_config=audio_cfg).audio_content

SUPPORTED_LANGS = {
    "en-US": "English (US)",
    "en-GB": "English (UK)",
    "hi-IN": "Hindi",
    "ta-IN": "Tamil",
    "te-IN": "Telugu",
    "bn-IN": "Bengali",
    "gu-IN": "Gujarati",
    "kn-IN": "Kannada",
    "ml-IN": "Malayalam",
    "mr-IN": "Marathi",
    "pa-IN": "Punjabi",
    # add more BCP-47 codes as desired
}

def _stt_from_webm_ogg_opus(content: bytes, language_code: str) -> str:
    client = speech.SpeechClient()
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.WEBM_OPUS,  # or OGG_OPUS if you send .ogg
        language_code=language_code,
        enable_automatic_punctuation=True,
        model="latest_long",  # or "latest_short" for < 60s clips
        # sample_rate_hertz not required for opus
    )
    audio = speech.RecognitionAudio(content=content)
    resp = client.recognize(config=config, audio=audio)
    # Concatenate best alternatives for a simple MVP
    transcript = " ".join([r.alternatives[0].transcript.strip() for r in resp.results]) if resp.results else ""
    return transcript.strip()

def _tts_to_mp3(text: str, language_code: str) -> bytes:
    tts_client = texttospeech.TextToSpeechClient()
    # Choose a neutral voice in the requested language; override voice name if you prefer.
    voice = texttospeech.VoiceSelectionParams(language_code=language_code, ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL)
    audio_cfg = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3)
    synthesis_input = texttospeech.SynthesisInput(text=text)
    resp = tts_client.synthesize_speech(input=synthesis_input, voice=voice, audio_config=audio_cfg)
    return resp.audio_content

@csrf_exempt
def recognize_and_reply(request):
    if request.method != "POST":
        return HttpResponseBadRequest("POST only")

    # Accept multipart/form-data or raw body; prefer form-data from browser
    lang = (request.POST.get("lang") or "en-US").strip()
    if lang not in SUPPORTED_LANGS:
        return HttpResponseBadRequest(f"Unsupported or missing language code: {lang}")

    # File comes as "file"
    f = request.FILES.get("file")
    if not f:
        # fallback to raw body
        if request.body:
            audio_bytes = request.body
        else:
            return HttpResponseBadRequest("No audio provided")
    else:
        audio_bytes = f.read()

    try:
        # 1) Speech to text
        transcript = _stt_from_webm_ogg_opus(audio_bytes, lang)

        # Your business logic: craft a reply (here: simple echo + language acknowledgment)
        reply_text = transcript if transcript else "I couldn't hear anything."
        # Example: add a helpful prompt or detected language marker
        if transcript:
            reply_text = f"You said: {transcript}"

        # 2) Text to speech
        mp3_bytes = _tts_to_mp3(reply_text, lang)
        mp3_b64 = base64.b64encode(mp3_bytes).decode("utf-8")

        return JsonResponse({
            "ok": True,
            "language": lang,
            "transcript": transcript,
            "reply_text": reply_text,
            "reply_mp3_base64": mp3_b64,  # play on client
        })
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)

@csrf_exempt
def list_supported_languages(request):
    # Merge STT/TTS language knowledge; here we expose our curated list for simplicity.
    return JsonResponse({"languages": [{"code": c, "name": n} for c, n in SUPPORTED_LANGS.items()]})
