class PaymentError(Exception):
    """Base exception for payment operations"""

    pass


class AuthenticationError(PaymentError):
    """Raised when authentication fails"""

    pass


class ProviderNotFoundError(PaymentError):
    """Raised when specified provider is not available"""

    pass


class InsufficientFundsError(PaymentError):
    """Raised when payment fails due to insufficient funds"""

    pass


class InvalidAccountError(PaymentError):
    """Raised when account details are invalid"""

    pass


class TransactionError(PaymentError):
    """Raised when transaction processing fails"""

    pass


class VerificationError(PaymentError):
    """Raised when transaction verification fails"""

    pass
