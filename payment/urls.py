# urls.py
from django.urls import path
from .views import deposit_view

urlpatterns = [
    path("payments/deposit/", deposit_view, name="deposit"),
]
