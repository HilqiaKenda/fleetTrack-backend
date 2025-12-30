from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

class FlutterWaveConfig:
    """Flutterwave Configurations"""

    @staticmethod
    def validator():
        """Validation of settings"""

        required = [
            "FLUTTERWAVE_PUBLIC_KEY",
            "FLUTTERWAVE_SECRET_KEY",
        ]

        for setting in required:
            if not hasattr(settings, setting):
                raise ImproperlyConfigured(
                    f"Required setting {setting} is missing."
                    "Please this in your environment."
                                           )
            
    @staticmethod
    def get_secret_key()->str:
        """Get Flutter Secret Key"""

        return settings.FLUTTERWAVE_SECRET_KEY

    
    @staticmethod
    def get_public_key()->str:
        """Get Flutter Public Key"""

        return settings.FLUTTERWAVE_PUBLIC_KEY
    
    @staticmethod
    def get_base_url()->str:
        """Get Flutter Base Url"""

        return settings.FLUTTERWAVE_BASE_URL
    
    @staticmethod
    def get_app_base_url() -> str:
        return getattr(settings, "APP_BASE_URL", "http://127.0.0.1:8000")

    @staticmethod
    def get_webhook_url() -> str:
        return getattr(settings, "FLUTTERWAVE_WEBHOOK_URL", "")

    @staticmethod
    def get_timeout() -> int:
        return getattr(settings, "FLUTTERWAVE_TIMEOUT", 30)

    @staticmethod
    def is_local_environment() -> bool:
        """Check if running in local/dev environment"""
        return False

    @staticmethod
    def get_hash_secret() -> str:
        return getattr(settings, "FLUTTERWAVE_SECRET_HASH", "")
