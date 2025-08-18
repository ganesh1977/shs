from django.urls import path
from django.contrib.auth import views as auth_views
from . import views   # <-- add this

urlpatterns = [
    path("",views.index, name="index"),
    path("checkgcp", views.credentials, name="check_gcp_credentials"),
    path("llminfo", views.ask_llm_data, name="check_gcp_llm"),    
    path("genclient", views.genclient, name="check_gcp_genclient"),
    path("chat", views.genclient, name="chatinfo"),
]
