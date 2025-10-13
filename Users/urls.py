from django.urls import path
from .views import RegisterView, LoginView, LogoutView, MeView, RefreshTokenView

urlpatterns = [
    path("register/", RegisterView.as_view(), name="auth_register"),
    path("login/", LoginView.as_view(), name="auth_login"),
    path("logout/", LogoutView.as_view(), name="auth_logout"),
    path("token/refresh/", RefreshTokenView.as_view(), name="token_refresh"),
    path("me/", MeView.as_view(), name="auth_me"),
]
