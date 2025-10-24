from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    RegisterViewSet,
    LoginViewSet,
    LogoutViewSet,
    RefreshTokenViewSet,
    MeViewSet,
    CheckAuthViewSet,
)

app_name = "auth"

router = DefaultRouter()

router.register(r"register", RegisterViewSet, basename="register")
router.register(r"login", LoginViewSet, basename="login")
router.register(r"logout", LogoutViewSet, basename="logout")
router.register(r"refresh", RefreshTokenViewSet, basename="refresh")
router.register(r"me", MeViewSet, basename="me")
router.register(r"check", CheckAuthViewSet, basename="check")


urlpatterns = [
    path("", include(router.urls)),
]

# urlpatterns = [
#     # Cookie-based authentication endpoints
#     path("register/", RegisterView.as_view(), name="register"),
#     path("login/", LoginView.as_view(), name="login"),
#     path("logout/", LogoutView.as_view(), name="logout"),
#     path("refresh/", RefreshTokenView.as_view(), name="refresh"),
#     path("me/", MeView.as_view(), name="me"),
#     path("check/", CheckAuthView.as_view(), name="check"),
# ]
