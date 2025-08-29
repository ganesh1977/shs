from django.urls import path
from .views import telegram_webhook
from . import views

urlpatterns = [
    path("telegram/<str:secret>/getMe", telegram_webhook),
    path("chat/", views.chat_with_model, name="chat"),
]