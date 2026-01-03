from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    BranchAssignmentViewSet,
    BranchManagerViewSet,
    BranchStatisticsViewSet,
    BranchViewSet,
    DriverDashboardViewSet,
    DriverRegisterViewSet,
    DriverViewSet,
    OrganizationDashboardViewSet,
    OrganizationRegisterViewSet,
    OrganizationViewSet,
    RegisterViewSet,
    LoginViewSet,
    LogoutViewSet,
    RefreshTokenViewSet,
    MeViewSet,
    SessionAuthViewSet,
)

app_name = "auth"

router = DefaultRouter()
router.register(r"signup", RegisterViewSet, basename="signup")
router.register(r"login", LoginViewSet, basename="login")
router.register(r"logout", LogoutViewSet, basename="logout")
router.register(r"refresh", RefreshTokenViewSet, basename="refresh")
router.register(r"me", MeViewSet, basename="me")
router.register(r"session", SessionAuthViewSet, basename="session")
router.register(r"register-organization", OrganizationRegisterViewSet, basename="register-organization")
router.register(r"organization", OrganizationViewSet, basename="organization")
router.register(r"admin", OrganizationDashboardViewSet, basename="admin-dash")
router.register(r"branches", BranchViewSet, basename="branch")
router.register(r"branch-managers", BranchManagerViewSet, basename="branch-manager")
router.register(r"branch-assignments", BranchAssignmentViewSet, basename="branch-assignment")
router.register(r"branch-statistics", BranchStatisticsViewSet, basename="branch-statistics")
router.register(r"driver-register", DriverRegisterViewSet, basename="driver-register")
router.register(r"drivers", DriverViewSet, basename="driver")
router.register(r"drivers", DriverDashboardViewSet, basename="driver-dash")


urlpatterns = [
    path("", include(router.urls)),
]
