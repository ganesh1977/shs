from django.urls import re_path
from voice.consumers import VoiceStreamConsumer

websocket_urlpatterns = [
    re_path(r"ws/voice$", VoiceStreamConsumer.as_asgi()),
]
