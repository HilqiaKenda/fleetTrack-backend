from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from django.contrib.auth import authenticate
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import User, Carrier, Driver, Branch, BranchManager, BranchAssignment, User


class UserSerializer(serializers.ModelSerializer):
    """Basic user serializer for general use"""

    class Meta:
        model = User
        fields = ["id", "username", "email", "role", "is_active", "created_at"]
        read_only_fields = ["id", "created_at"]


class RegisterSerializer(serializers.ModelSerializer):
    """Unified registration serializer with password confirmation"""

    password = serializers.CharField(
        write_only=True, required=True, validators=[validate_password]
    )
    password2 = serializers.CharField(
        write_only=True, required=True, label="Confirm Password"
    )

    class Meta:
        model = User
        fields = ["id", "username", "email", "role", "password", "password2"]
        extra_kwargs = {
            "email": {"required": True},
            "username": {"required": True},
        }

    def validate(self, attrs):
        if attrs.get("password") != attrs.get("password2"):
            raise serializers.ValidationError(
                {"password": "Password fields didn't match."}
            )
        return attrs

    def create(self, validated_data):
        validated_data.pop("password2")
        password = validated_data.pop("password")

        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            role=validated_data.get("role", "Maintenancer"),
            password=password,
        )
        return user


class LoginSerializer(serializers.Serializer):
    """Unified login serializer"""

    username = serializers.CharField(required=True)
    password = serializers.CharField(
        write_only=True, required=True, style={"input_type": "password"}
    )

    def validate(self, attrs):
        username = attrs.get("username")
        password = attrs.get("password")

        user = authenticate(username=username, password=password)

        if not user:
            raise serializers.ValidationError(
                {
                    "detail": "Invalid credentials. Please check your username and password."
                }
            )

        if not user.is_active:
            raise serializers.ValidationError({"detail": "User account is disabled."})

        attrs["user"] = user
        return attrs


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Custom token serializer with additional user claims"""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        # Add custom claims
        token["username"] = user.username
        token["email"] = user.email
        token["role"] = user.role
        return token


class EmptySerializer(serializers.Serializer):
    pass


class UserProfileSerializer(serializers.ModelSerializer):
    """Detailed user profile serializer"""

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "role",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class UpdateUserProfileSerializer(serializers.ModelSerializer):
    """Serializer for updating user profile"""

    class Meta:
        model = User
        fields = ["username", "email", "role"]
        extra_kwargs = {
            "username": {"required": False},
            "email": {"required": False},
        }

    def validate_email(self, value):
        user = self.instance
        if User.objects.exclude(pk=user.pk).filter(email=value).exists():
            raise serializers.ValidationError("This email is already in use.")
        return value

    def validate_username(self, value):
        user = self.instance
        if User.objects.exclude(pk=user.pk).filter(username=value).exists():
            raise serializers.ValidationError("This username is already taken.")
        return value


class BranchSerializer(serializers.ModelSerializer):
    """Basic branch serializer"""

    vehicle_count = serializers.SerializerMethodField()
    active_vehicle_count = serializers.SerializerMethodField()
    driver_count = serializers.SerializerMethodField()
    is_at_capacity = serializers.SerializerMethodField()

    class Meta:
        model = Branch
        fields = [
            "id",
            "name",
            "code",
            "address",
            "city",
            "region",
            "country",
            "phone_number",
            "email",
            "latitude",
            "longitude",
            "status",
            "capacity",
            # "vehicle_count",
            # "active_vehicle_count",
            "driver_count",
            "is_at_capacity",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_vehicle_count(self, obj):
        return obj.get_vehicle_count()

    def get_active_vehicle_count(self, obj):
        return obj.get_active_vehicle_count()

    def get_driver_count(self, obj):
        return obj.get_driver_count()

    def get_is_at_capacity(self, obj):
        return obj.is_at_capacity()


class BranchListSerializer(serializers.ModelSerializer):
    """Lightweight branch serializer for lists"""

    class Meta:
        model = Branch
        fields = [
            "id",
            "name",
            "code",
            "city",
            "region",
            "status",
        ]


class BranchDetailSerializer(serializers.ModelSerializer):
    """Detailed branch serializer with related data"""

    managers = serializers.SerializerMethodField()
    statistics = serializers.SerializerMethodField()

    class Meta:
        model = Branch
        fields = [
            "id",
            "name",
            "code",
            "address",
            "city",
            "region",
            "country",
            "phone_number",
            "email",
            "latitude",
            "longitude",
            "status",
            "capacity",
            "managers",
            "statistics",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_managers(self, obj):
        managers = obj.branch_managers.filter(is_active=True)
        return BranchManagerSerializer(managers, many=True).data

    def get_statistics(self, obj):
        return {
            "total_vehicles": obj.get_vehicle_count(),
            "active_vehicles": obj.get_active_vehicle_count(),
            "total_drivers": obj.get_driver_count(),
            "capacity_usage": (
                f"{(obj.get_vehicle_count() / obj.capacity * 100):.1f}%"
                if obj.capacity > 0
                else "N/A"
            ),
        }


class BranchManagerSerializer(serializers.ModelSerializer):
    """Branch manager serializer"""

    user_details = serializers.SerializerMethodField()
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    branch_code = serializers.CharField(source="branch.code", read_only=True)

    class Meta:
        model = BranchManager
        fields = [
            "id",
            "user",
            "user_details",
            "branch",
            "branch_name",
            "branch_code",
            "role",
            "can_approve_trips",
            "can_assign_drivers",
            "can_manage_vehicles",
            "can_approve_maintenance",
            "can_view_reports",
            "assigned_date",
            "is_primary",
            "is_active",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "assigned_date", "created_at", "updated_at"]

    def get_user_details(self, obj):
        return {
            "id": obj.user.id,
            "username": obj.user.username,
            "email": obj.user.email,
            "role": obj.user.role,
        }

    def validate(self, data):
        """Validate branch manager data"""
        user = data.get("user")

        if user and user.role not in [
            "fleet-manager",
            "Maintenancer",
            "branch-manager",
        ]:
            raise serializers.ValidationError(
                {
                    "user": "Only Fleet Managers, Maintenance Supervisors, or Branch Managers can be assigned to branches."
                }
            )

        return data


class CreateBranchManagerSerializer(serializers.ModelSerializer):
    """Serializer for creating branch managers"""

    class Meta:
        model = BranchManager
        fields = [
            "user",
            "branch",
            "role",
            "can_approve_trips",
            "can_assign_drivers",
            "can_manage_vehicles",
            "can_approve_maintenance",
            "can_view_reports",
            "is_primary",
            "notes",
        ]

    def validate(self, data):
        user = data.get("user")
        branch = data.get("branch")

        # Check if user already manages this branch
        if BranchManager.objects.filter(user=user, branch=branch).exists():
            raise serializers.ValidationError(
                "This user is already assigned as a manager to this branch."
            )

        # Validate user role
        if user.role not in ["fleet-manager", "Maintenancer", "branch-manager"]:
            raise serializers.ValidationError(
                {
                    "user": "Only Fleet Managers, Maintenance Supervisors, or Branch Managers can be assigned."
                }
            )

        return data


class BranchAssignmentSerializer(serializers.ModelSerializer):
    """Branch assignment serializer"""

    user_details = serializers.SerializerMethodField()
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    is_current = serializers.SerializerMethodField()

    class Meta:
        model = BranchAssignment
        fields = [
            "id",
            "user",
            "user_details",
            "branch",
            "branch_name",
            "assignment_type",
            "start_date",
            "end_date",
            "is_active",
            "is_current",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_user_details(self, obj):
        return {
            "id": obj.user.id,
            "username": obj.user.username,
            "email": obj.user.email,
            "role": obj.user.role,
        }

    def get_is_current(self, obj):
        return obj.is_current()

    def validate(self, data):
        """Validate assignment dates"""
        start_date = data.get("start_date")
        end_date = data.get("end_date")

        if end_date and start_date and start_date > end_date:
            raise serializers.ValidationError(
                {"end_date": "End date must be after start date."}
            )

        return data


class UserBranchSerializer(serializers.ModelSerializer):
    """Serializer to show user's branch relationships"""

    primary_branch = BranchListSerializer(read_only=True)
    managed_branches = serializers.SerializerMethodField()
    assigned_branches = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "role",
            "primary_branch",
            "managed_branches",
            "assigned_branches",
        ]

    def get_managed_branches(self, obj):
        if obj.role in ["fleet-manager", "Maintenancer", "branch-manager"]:
            managers = obj.managed_branches.filter(is_active=True)
            return [
                {
                    "id": bm.branch.id,
                    "name": bm.branch.name,
                    "code": bm.branch.code,
                    "role": bm.role,
                    "is_primary": bm.is_primary,
                }
                for bm in managers
            ]
        return []

    def get_assigned_branches(self, obj):
        assignments = obj.branch_assignments.filter(is_active=True)
        return [
            {
                "id": assignment.branch.id,
                "name": assignment.branch.name,
                "code": assignment.branch.code,
                "assignment_type": assignment.assignment_type,
                "start_date": assignment.start_date,
                "end_date": assignment.end_date,
            }
            for assignment in assignments
        ]


class BranchStatisticsSerializer(serializers.Serializer):
    """Serializer for branch statistics"""

    branch_id = serializers.IntegerField()
    branch_name = serializers.CharField()
    active_vehicles = serializers.IntegerField()
    inactive_vehicles = serializers.IntegerField()
    total_drivers = serializers.IntegerField()
    active_trips = serializers.IntegerField()
    completed_trips = serializers.IntegerField()
    maintenance_pending = serializers.IntegerField()
    capacity_usage = serializers.CharField()


class DriverSerializer(serializers.ModelSerializer):
    """Driver profile serializer"""

    user_username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = Driver
        fields = [
            "id",
            "user",
            "user_username",
            "driver_initial",
            "full_name",
            "license_number",
            "phone_number",
            "email",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class CarrierSerializer(serializers.ModelSerializer):
    """Carrier/Company serializer"""

    vehicles_count = serializers.SerializerMethodField()

    class Meta:
        model = Carrier
        fields = [
            "id",
            "name",
            "dot_number",
            "mc_number",
            "address",
            "phone",
            "vehicles_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_vehicles_count(self, obj):
        return obj.vehicles.count() if hasattr(obj, "vehicles") else 0
