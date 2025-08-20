from django.shortcuts import render
from django.http import HttpResponse, JsonResponse,HttpResponseBadRequest

# Create your views here.

def index(request):
    return HttpResponse("Hello, you are users")