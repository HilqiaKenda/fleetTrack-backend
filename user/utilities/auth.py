from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.authentication import AuthenticationFailed


class CookieJWTAuthentication(JWTAuthentication):
    """AUthentication with cookie"""

    def authenticate(self, request):
        token = request.COOKIES.get("access_token")

        if not token:
            return None

        try:
            validated_token = self.get_validated_token(token)
        except AuthenticationFailed as exce:
            raise AuthenticationFailed(f"Authentication failed: {str(exce)}")

        except Exception as exce:
            raise AuthenticationFailed(f"Unexpected error occurred: {str(exce)}")

        try:
            user = self.get_user(validated_token)

            return user, validated_token

        except AuthenticationFailed as exce:
            raise AuthenticationFailed(f"Error while retrieving user: {str(exce)}")

        except Exception as exce:
            raise AuthenticationFailed(f"Unexpected error occurred: {str(exce)}")
