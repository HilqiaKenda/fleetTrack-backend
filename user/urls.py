from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    BranchAssignmentViewSet,
    BranchManagerViewSet,
    BranchStatisticsViewSet,
    BranchViewSet,
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
router.register("branches", BranchViewSet, basename="branch")
router.register("branch-managers", BranchManagerViewSet, basename="branch-manager")
router.register(
    "branch-assignments", BranchAssignmentViewSet, basename="branch-assignment"
)
router.register(
    "branch-statistics", BranchStatisticsViewSet, basename="branch-statistics"
)


urlpatterns = [
    path("", include(router.urls)),
]
