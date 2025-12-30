from decimal import Decimal
from typing import Dict
from service.payment.exception_handler import ProviderNotFoundError
from service.payment.providers.flutterwave.flutterwave_processor import FlutterwaveProcessor


class PaymentService:
    """Main Payment Operations Handler"""

    PROVIDER = {
            "flutterWave": FlutterwaveProcessor
        }
    
    def __init__(self,provider):

        self.provider_name = provider
        self._provider = self._get_provider(provider)


    def _get_provider(self, provider):
        """
        Docstring for _get_provider
        
        :param self: Description
        """

        provider_class = self.PROVIDER.get(provider)
        if not provider_class:
            raise ProviderNotFoundError(f"Provider '{provider}' not found."
                                        f"Available {list(self.PROVIDER.keys())}")
        
        return provider_class()

    def deposit(self, amount: Decimal, user: Dict[str, str], tx_ref, **options):
        """
        When a user has make a payment

        Args:
            amount: Amount to collect
            customer: Dict with 'email', 'phone', 'name'
            tx_ref: Transaction reference from your system
            **options:
                - currency: Currency code (default: 'UGX')
                - redirect_url: Redirect URL after payment
                - title: Payment title
                - description: Payment description
                - payment_method: Specific payment method

        Returns:
            PaymentResult with payment link and transaction details
        """
        return self._provider.deposit(amount, user, tx_ref, **options)

    def withdraw(self, amount, recipient, method, tx_ref, **options):
        """
        Withdrawal process  with thw amount to withdraw currency recepient details

        Args:
            amount: Amount to withdraw
            recipient: Recipient details
            method: 'mobile_money' or 'bank_transfer'
            tx_ref: Transaction reference from your system
            **options:
                - currency: Currency code (default: 'UGX')
                - narration: Transaction description
                - mobile_provider: 'MTN' or 'AIRTEL' (for mobile money)
                - bank_code: Bank code (for bank transfers)

        Returns:
            PaymentResult with transaction details
        """
        return self._provider.withdraw(amount, recipient, method, tx_ref, **options)


    def transfert(self, amount, sender, recipient, tx_ref, **options):
        """
        Transaction process between accounts
        """

        return self._provider.transfer(amount, sender, recipient, tx_ref, **options)
    

