from django.urls import path
from django.contrib.auth import views as auth_views
from . import views   # <-- add this
from .views import recognize_and_reply, list_supported_languages

urlpatterns = [
    path("",views.index, name="index"),   
    path("voice/recognize-reply", recognize_and_reply, name="recognize_and_reply"),
    path("voice/languages", list_supported_languages, name="list_supported_languages"),
    
]
