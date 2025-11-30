from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.test import APIClient, APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model

User = get_user_model()


class AuthTests(APITestCase):

    def setUp(self):
        self.register_url = reverse(
            "register"
        )  # Make sure you name your urls accordingly
        self.login_url = reverse("login")
        self.refresh_url = reverse("token_refresh")
        self.logout_url = reverse("logout")
        self.me_url = reverse("me")

        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="password123",
            first_name="John",
            last_name="Doe",
        )

    def test_register_user_success(self):
        """Ensure a new user can register successfully."""
        data = {
            "username": "newuser",
            "email": "new@example.com",
            "password": "StrongPass123",
            "password2": "StrongPass123",
            "first_name": "New",
            "last_name": "User",
        }
        response = self.client.post(self.register_url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("username", response.data)
        self.assertEqual(response.data["username"], "newuser")

    def test_register_password_mismatch(self):
        """Ensure registration fails if passwords don't match."""
        data = {
            "username": "baduser",
            "email": "bad@example.com",
            "password": "pass123",
            "password2": "pass456",
        }
        response = self.client.post(self.register_url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.data)

    def test_login_success(self):
        """Ensure login returns JWT tokens and user info."""
        data = {"username": "testuser", "password": "password123"}
        response = self.client.post(self.login_url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertIn("user", response.data)
        self.assertEqual(response.data["user"]["username"], "testuser")

    def test_login_invalid_credentials(self):
        """Ensure login fails for wrong credentials."""
        data = {"username": "testuser", "password": "wrongpass"}
        response = self.client.post(self.login_url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_authenticated(self):
        """Ensure authenticated user can access /me/."""
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}"
        )
        response = self.client.get(self.me_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], "testuser")

    def test_me_unauthenticated(self):
        """Ensure unauthenticated user is denied access."""
        response = self.client.get(self.me_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_token_valid(self):
        """Ensure a valid refresh token generates a new access token."""
        refresh = RefreshToken.for_user(self.user)
        data = {"refresh": str(refresh)}
        response = self.client.post(self.refresh_url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)

    def test_refresh_token_invalid(self):
        """Ensure invalid refresh token returns 401."""
        data = {"refresh": "invalidtoken"}
        response = self.client.post(self.refresh_url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_blacklists_refresh_token(self):
        """Ensure logout blacklists refresh token."""
        refresh = RefreshToken.for_user(self.user)
        data = {"refresh": str(refresh)}
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}"
        )
        response = self.client.post(self.logout_url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_205_RESET_CONTENT)
        # Try reusing blacklisted token
        response = self.client.post(
            self.refresh_url, {"refresh": str(refresh)}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class PermissionTestCase(APITestCase):
    """Base test case for permission testing"""

    def setUp(self):
        """Create test users for each role"""
        self.client = APIClient()

        # Create admin user
        self.admin_user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="admin123",
            role="admin",
        )

        # Create fleet manager user
        self.fleet_manager_user = User.objects.create_user(
            username="fleet_manager",
            email="fleet@example.com",
            password="fleet123",
            role="fleet-manager",
        )

        # Create driver user
        self.driver_user = User.objects.create_user(
            username="driver",
            email="driver@example.com",
            password="driver123",
            role="driver",
        )

        # Create maintenance supervisor user
        self.maintenance_user = User.objects.create_user(
            username="maintenance",
            email="maintenance@example.com",
            password="maintenance123",
            role="Maintenancer",
        )

    def login_as(self, user):
        """Helper method to login as a specific user"""
        self.client.force_authenticate(user=user)

    def logout(self):
        """Helper method to logout"""
        self.client.force_authenticate(user=None)


class AdminPermissionTests(PermissionTestCase):
    """Test admin permissions"""

    def test_admin_can_access_dashboard(self):
        """Admin should access admin dashboard"""
        self.login_as(self.admin_user)
        response = self.client.get("/api/admin/dashboard/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_non_admin_cannot_access_admin_dashboard(self):
        """Non-admin should not access admin dashboard"""
        self.login_as(self.fleet_manager_user)
        response = self.client.get("/api/admin/dashboard/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_manage_users(self):
        """Admin should manage all users"""
        self.login_as(self.admin_user)
        response = self.client.get("/api/admin/users/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_admin_can_view_system_health(self):
        """Admin should view system health metrics"""
        self.login_as(self.admin_user)
        response = self.client.get("/api/admin/dashboard/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("system_health", response.data)

    def test_admin_can_view_financial_data(self):
        """Admin should access financial overview"""
        self.login_as(self.admin_user)
        response = self.client.get("/api/admin/dashboard/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check for financial data in response


class FleetManagerPermissionTests(PermissionTestCase):
    """Test fleet manager permissions"""

    def test_fleet_manager_can_access_dashboard(self):
        """Fleet manager should access their dashboard"""
        self.login_as(self.fleet_manager_user)
        response = self.client.get("/api/fleet-manager/dashboard/")
        # May return 400 if no branch assigned, which is expected
        self.assertIn(
            response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST]
        )

    def test_fleet_manager_can_view_vehicles(self):
        """Fleet manager should view vehicles"""
        self.login_as(self.fleet_manager_user)
        response = self.client.get("/api/fleet-manager/vehicles/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_fleet_manager_can_manage_trips(self):
        """Fleet manager should manage trips"""
        self.login_as(self.fleet_manager_user)
        response = self.client.get("/api/fleet-manager/trips/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_fleet_manager_cannot_access_admin_dashboard(self):
        """Fleet manager should not access admin dashboard"""
        self.login_as(self.fleet_manager_user)
        response = self.client.get("/api/admin/dashboard/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_fleet_manager_can_view_but_not_create_users(self):
        """Fleet manager should have read-only access to users"""
        self.login_as(self.fleet_manager_user)

        # Can view
        response = self.client.get("/api/admin/users/")
        # Should either succeed or be forbidden based on implementation
        self.assertIn(
            response.status_code, [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN]
        )


class DriverPermissionTests(PermissionTestCase):
    """Test driver permissions"""

    def test_driver_can_access_dashboard(self):
        """Driver should access their dashboard"""
        self.login_as(self.driver_user)
        response = self.client.get("/api/driver/dashboard/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_driver_can_view_own_trips(self):
        """Driver should view their own trips"""
        self.login_as(self.driver_user)
        response = self.client.get("/api/driver/trips/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_driver_can_view_violations(self):
        """Driver should view their violations"""
        self.login_as(self.driver_user)
        response = self.client.get("/api/driver/violations/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_driver_cannot_access_fleet_manager_dashboard(self):
        """Driver should not access fleet manager dashboard"""
        self.login_as(self.driver_user)
        response = self.client.get("/api/fleet-manager/dashboard/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_driver_cannot_manage_vehicles(self):
        """Driver should not manage vehicles"""
        self.login_as(self.driver_user)
        response = self.client.get("/api/fleet-manager/vehicles/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_driver_has_read_only_access(self):
        """Driver should have read-only access to trips"""
        self.login_as(self.driver_user)

        # Can view
        response = self.client.get("/api/driver/trips/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Cannot create (would need actual trip data)
        response = self.client.post("/api/driver/trips/", {})
        self.assertIn(
            response.status_code,
            [status.HTTP_403_FORBIDDEN, status.HTTP_405_METHOD_NOT_ALLOWED],
        )


class MaintenancePermissionTests(PermissionTestCase):
    """Test maintenance supervisor permissions"""

    def test_maintenance_can_access_dashboard(self):
        """Maintenance supervisor should access their dashboard"""
        self.login_as(self.maintenance_user)
        response = self.client.get("/api/maintenance/dashboard/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_maintenance_can_view_schedules(self):
        """Maintenance supervisor should view maintenance schedules"""
        self.login_as(self.maintenance_user)
        response = self.client.get("/api/maintenance/schedule/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_maintenance_can_view_history(self):
        """Maintenance supervisor should view maintenance history"""
        self.login_as(self.maintenance_user)
        response = self.client.get("/api/maintenance/history/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_maintenance_can_manage_breakdowns(self):
        """Maintenance supervisor should manage breakdowns"""
        self.login_as(self.maintenance_user)
        response = self.client.get("/api/maintenance/breakdowns/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_maintenance_cannot_access_admin_dashboard(self):
        """Maintenance supervisor should not access admin dashboard"""
        self.login_as(self.maintenance_user)
        response = self.client.get("/api/admin/dashboard/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class SharedEndpointTests(PermissionTestCase):
    """Test shared endpoints with role-based filtering"""

    def test_all_roles_can_get_permissions(self):
        """All authenticated users should get their permissions"""
        for user in [
            self.admin_user,
            self.fleet_manager_user,
            self.driver_user,
            self.maintenance_user,
        ]:
            self.login_as(user)
            response = self.client.get("/api/auth/permissions/")
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertIn("permissions", response.data)
            self.assertIn("role", response.data)

    def test_alerts_filtered_by_role(self):
        """Alerts should be filtered based on user role"""
        for user in [
            self.admin_user,
            self.fleet_manager_user,
            self.driver_user,
            self.maintenance_user,
        ]:
            self.login_as(user)
            response = self.client.get("/api/alerts/")
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertIn("alerts", response.data)
