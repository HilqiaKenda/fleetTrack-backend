from rest_framework import status, mixins, viewsets
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.response import Response
from user.utilities.auth import CookieJWTAuthentication
from .models import User
from .serializers import (
    LoginSerializer,
    RegisterSerializer,
    UpdateUserProfileSerializer,
    UserProfileSerializer,
    UserSerializer,
)
from rest_framework.permissions import IsAuthenticated

from rest_framework_simplejwt.exceptions import TokenError
from rest_framework.response import Response
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken


class RegisterViewSet(mixins.CreateModelMixin, viewsets.GenericViewSet):
    """
    Register a new user and set JWT tokens in HTTP-only cookies.
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    serializer_class = RegisterSerializer

    def create(self, request, *args, **kwargs):
        # Validate and save user
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)

        # Create response
        response = Response(
            {
                "user": UserSerializer(user).data,
                "message": "User registered successfully",
            },
            status=status.HTTP_201_CREATED,
        )

        # Set access token in HTTP-only cookie
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            secure=True,
            samesite="Strict",
            max_age=3600,  # 1 hour
            path="/",
        )

        # Set refresh token in HTTP-only cookie
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=True,
            samesite="Strict",
            max_age=86400 * 7,  # 7 days
            path="/",
        )

        return response


class LoginViewSet(mixins.CreateModelMixin, viewsets.GenericViewSet):
    """
    Authenticate user and set JWT tokens in HTTP-only cookies
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    serializer_class = LoginSerializer

    def create(self, request, *args, **kwargs):
        # Validate and authenticate user
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]

        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)

        # Create response
        response = Response(
            {
                "user": UserSerializer(user).data,
                "message": "Login successful",
            },
            status=status.HTTP_200_OK,
        )

        # Set access token in HTTP-only cookie
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            secure=True,
            samesite="Strict",
            max_age=3600,  # 1 hour
            path="/",
        )

        # Set refresh token in HTTP-only cookie
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=True,
            samesite="Strict",
            max_age=86400 * 7,  # 7 days
            path="/",
        )

        return response


class LogoutViewSet(viewsets.ViewSet):
    """
    Logout user by blacklisting refresh token and clearing cookies.
    """

    authentication_classes = [CookieJWTAuthentication]
    # permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        refresh_token = request.COOKIES.get("refresh_token")

        if refresh_token:
            try:
                token = RefreshToken(refresh_token)
                token.blacklist()
            except Exception as e:
                # Continue with logout even if token is invalid or blacklisted
                pass

        response = Response(
            {"message": "Successfully logged out"},
            status=status.HTTP_200_OK,
        )

        response.delete_cookie("access_token", path="/")
        response.delete_cookie("refresh_token", path="/")

        return response


class RefreshTokenViewSet(mixins.CreateModelMixin, viewsets.GenericViewSet):
    """
    Refresh access token using refresh token from cookie.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        refresh_token = request.COOKIES.get("refresh_token")

        if not refresh_token:
            return Response(
                {"detail": "Refresh token not found in cookies."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            token = RefreshToken(refresh_token)

            # Check if token is blacklisted
            jti = token.get("jti")
            if BlacklistedToken.objects.filter(token__jti=jti).exists():
                response = Response(
                    {"detail": "Token has been blacklisted. Please login again."},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
                # Clear cookies since token is invalid
                response.delete_cookie("access_token", path="/")
                response.delete_cookie("refresh_token", path="/")
                return response

            access_token = str(token.access_token)

            response = Response(
                {"message": "Token refreshed successfully"},
                status=status.HTTP_200_OK,
            )

            response.set_cookie(
                key="access_token",
                value=access_token,
                httponly=True,
                secure=True,
                samesite="Strict",
                max_age=3600,  # 1 hour
                path="/",
            )

            return response

        except TokenError as e:
            response = Response(
                {"detail": f"Invalid or expired refresh token. Please login again."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
            # Clear cookies since token is invalid
            response.delete_cookie("access_token", path="/")
            response.delete_cookie("refresh_token", path="/")
            return response


class MeViewSet(
    mixins.RetrieveModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet
):
    """
    Get or update current authenticated user profile.
    """

    authentication_classes = [CookieJWTAuthentication]
    # permission_classes = [IsAuthenticated]
    serializer_class = UserProfileSerializer

    def retrieve(self, request, *args, **kwargs):
        """Get current user profile"""
        return super().retrieve(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        """Update current user profile"""
        partial = kwargs.pop("partial", False)
        serializer = UpdateUserProfileSerializer(
            request.user, data=request.data, partial=partial
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {
                "user": UserProfileSerializer(request.user).data,
                "message": "Profile updated successfully",
            },
            status=status.HTTP_200_OK,
        )


class CheckAuthViewSet(mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """
    Check if user is authenticated.
    """

    authentication_classes = [CookieJWTAuthentication]
    # permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer

    def retrieve(self, request, *args, **kwargs):
        return Response({"authenticated"})


# from rest_framework import status
# from rest_framework.response import Response
# from rest_framework.views import APIView
# from rest_framework.permissions import AllowAny, IsAuthenticated
# from rest_framework_simplejwt.tokens import RefreshToken
# from rest_framework_simplejwt.exceptions import TokenError
# from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken

# from .models import User
# from .serializers import (
#     RegisterSerializer,
#     LoginSerializer,
#     UserSerializer,
#     UserProfileSerializer,
#     UpdateUserProfileSerializer,
# )
# from user.utilities.auth import CookieJWTAuthentication


# class RegisterView(APIView):
#     """
#     Register a new user and set JWT tokens in HTTP-only cookies

#     POST /api/auth/register/
#     Body: {
#         "username": "string",
#         "email": "string",
#         "password": "string",
#         "password2": "string",
#         "role": "string" (optional, defaults to "Driver")
#     }
#     """

#     authentication_classes = []
#     permission_classes = [AllowAny]

#     def post(self, request):
#         serializer = RegisterSerializer(data=request.data)
#         serializer.is_valid(raise_exception=True)
#         user = serializer.save()

#         # Generate JWT tokens
#         refresh = RefreshToken.for_user(user)
#         access_token = str(refresh.access_token)
#         refresh_token = str(refresh)

#         response = Response(
#             {
#                 "user": UserSerializer(user).data,
#                 "message": "User registered successfully",
#             },
#             status=status.HTTP_201_CREATED,
#         )

#         # Set access token in HTTP-only cookie
#         response.set_cookie(
#             key="access_token",
#             value=access_token,
#             httponly=True,
#             secure=True,  # Set to True in production with HTTPS
#             samesite="Strict",
#             max_age=3600,  # 1 hour
#             path="/",
#         )

#         # Set refresh token in HTTP-only cookie
#         response.set_cookie(
#             key="refresh_token",
#             value=refresh_token,
#             httponly=True,
#             secure=True,
#             samesite="Strict",
#             max_age=86400 * 7,  # 7 days
#             path="/",
#         )

#         return response


# class LoginView(APIView):
#     """
#     Authenticate user and set JWT tokens in HTTP-only cookies

#     POST /api/auth/login/
#     Body: {
#         "username": "string",
#         "password": "string"
#     }
#     """

#     authentication_classes = []
#     permission_classes = [AllowAny]

#     def post(self, request):
#         serializer = LoginSerializer(data=request.data)
#         serializer.is_valid(raise_exception=True)

#         user = serializer.validated_data["user"]

#         # Generate JWT tokens
#         refresh = RefreshToken.for_user(user)
#         access_token = str(refresh.access_token)
#         refresh_token = str(refresh)

#         response = Response(
#             {
#                 "user": UserSerializer(user).data,
#                 "message": "Login successful",
#             },
#             status=status.HTTP_200_OK,
#         )

#         # Set access token in HTTP-only cookie
#         response.set_cookie(
#             key="access_token",
#             value=access_token,
#             httponly=True,
#             secure=True,
#             samesite="Strict",
#             max_age=3600,  # 1 hour
#             path="/",
#         )

#         # Set refresh token in HTTP-only cookie
#         response.set_cookie(
#             key="refresh_token",
#             value=refresh_token,
#             httponly=True,
#             secure=True,
#             samesite="Strict",
#             max_age=86400 * 7,  # 7 days
#             path="/",
#         )

#         return response


# class LogoutView(APIView):
#     """
#     Logout user by blacklisting refresh token and clearing cookies

#     POST /api/auth/logout/
#     """

#     authentication_classes = [CookieJWTAuthentication]
#     permission_classes = [IsAuthenticated]

#     def post(self, request):
#         refresh_token = request.COOKIES.get("refresh_token")

#         # Try to blacklist the refresh token if it exists
#         if refresh_token:
#             try:
#                 token = RefreshToken(refresh_token)
#                 token.blacklist()
#             except TokenError as e:
#                 # Token might already be blacklisted or invalid
#                 # Continue with logout anyway
#                 pass
#             except Exception as e:
#                 # Log the error but continue with logout
#                 pass

#         response = Response(
#             {"message": "Successfully logged out"},
#             status=status.HTTP_200_OK,
#         )

#         # Clear both cookies
#         response.delete_cookie("access_token", path="/")
#         response.delete_cookie("refresh_token", path="/")

#         return response


# class RefreshTokenView(APIView):
#     """
#     Refresh access token using refresh token from cookie

#     POST /api/auth/refresh/
#     """

#     authentication_classes = []
#     permission_classes = [AllowAny]

#     def post(self, request):
#         refresh_token = request.COOKIES.get("refresh_token")

#         if not refresh_token:
#             return Response(
#                 {"detail": "Refresh token not found in cookies."},
#                 status=status.HTTP_400_BAD_REQUEST,
#             )

#         try:
#             token = RefreshToken(refresh_token)

#             # Check if token is blacklisted
#             jti = token.get("jti")
#             if BlacklistedToken.objects.filter(token__jti=jti).exists():
#                 response = Response(
#                     {"detail": "Token has been blacklisted. Please login again."},
#                     status=status.HTTP_401_UNAUTHORIZED,
#                 )
#                 # Clear cookies since token is invalid
#                 response.delete_cookie("access_token", path="/")
#                 response.delete_cookie("refresh_token", path="/")
#                 return response

#             # Generate new access token
#             access_token = str(token.access_token)

#             response = Response(
#                 {"message": "Token refreshed successfully"},
#                 status=status.HTTP_200_OK,
#             )

#             # Set new access token in cookie
#             response.set_cookie(
#                 key="access_token",
#                 value=access_token,
#                 httponly=True,
#                 secure=True,
#                 samesite="Strict",
#                 max_age=3600,  # 1 hour
#                 path="/",
#             )

#             return response

#         except TokenError as e:
#             response = Response(
#                 {"detail": f"Invalid or expired refresh token. Please login again."},
#                 status=status.HTTP_401_UNAUTHORIZED,
#             )
#             # Clear cookies since token is invalid
#             response.delete_cookie("access_token", path="/")
#             response.delete_cookie("refresh_token", path="/")
#             return response


# class MeView(APIView):
#     """
#     Get or update current authenticated user profile

#     GET /api/auth/me/
#     PATCH /api/auth/me/
#     Body (for PATCH): {
#         "username": "string" (optional),
#         "email": "string" (optional),
#         "role": "string" (optional)
#     }
#     """

#     authentication_classes = [CookieJWTAuthentication]
#     permission_classes = [IsAuthenticated]

#     def get(self, request):
#         """Get current user profile"""
#         serializer = UserProfileSerializer(request.user)
#         return Response(serializer.data, status=status.HTTP_200_OK)

#     def patch(self, request):
#         """Update current user profile"""
#         serializer = UpdateUserProfileSerializer(
#             request.user, data=request.data, partial=True
#         )
#         serializer.is_valid(raise_exception=True)
#         serializer.save()

#         return Response(
#             {
#                 "user": UserProfileSerializer(request.user).data,
#                 "message": "Profile updated successfully",
#             },
#             status=status.HTTP_200_OK,
#         )


# class CheckAuthView(APIView):
#     """
#     Check if user is authenticated (useful for frontend)

#     GET /api/auth/check/
#     """

#     authentication_classes = [CookieJWTAuthentication]
#     permission_classes = [IsAuthenticated]

#     def get(self, request):
#         return Response(
#             {
#                 "authenticated": True,
#                 "user": UserSerializer(request.user).data,
#             },
#             status=status.HTTP_200_OK,
#         )
