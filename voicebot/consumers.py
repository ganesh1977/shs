import asyncio, base64, json
from channels.generic.websocket import AsyncWebsocketConsumer
from google.cloud import speech_v1p1beta1 as speech
from google.cloud import texttospeech

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
