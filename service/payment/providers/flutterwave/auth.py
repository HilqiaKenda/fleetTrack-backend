import logging
from typing import Dict
from service.payment.exception_handler import AuthenticationError
from .config import FlutterWaveConfig

logger = logging.getLogger(__name__)


class FlutterwaveAuth:
    """Handle Flutterwave authentication"""

    @classmethod
    def validate_credentials(cls) -> bool:
        """Validate credentials are configured"""
        try:
            FlutterWaveConfig.validate()
            return True
        except Exception as e:
            logger.error(f"Flutterwave credentials validation failed: {e}")
            return False

    @classmethod
    def get_headers(cls) -> Dict[str, str]:
        """Get authenticated headers"""
        try:
            return {
                "Authorization": f"Bearer {FlutterWaveConfig.get_secret_key()}",
                "Content-Type": "application/json",
            }
        except Exception as e:
            raise AuthenticationError(f"Failed to get auth headers: {str(e)}")

    @classmethod
    def get_public_key(cls) -> str:
        """Get public key for client-side operations"""
        try:
            return FlutterWaveConfig.get_public_key()
        except Exception as e:
            raise AuthenticationError(f"Failed to get public key: {str(e)}")
