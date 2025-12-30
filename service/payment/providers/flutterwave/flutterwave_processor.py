import json
import logging
import uuid
from decimal import Decimal
from typing import Any, Dict, List

import requests

from service.payment.exception_handler import PaymentError
from service.payment.providers.base import (
    PaymentBaseProvider,
    PaymentResult,
    TransactionStatus,
    TrasnsactionType,
    ResultVerification,
)

from .auth import FlutterwaveAuth
from .config import FlutterWaveConfig

logger = logging.getLogger(__name__)


class FlutterwaveProcessor(PaymentBaseProvider):
    """Flutterwave implementation of payment provider"""

    def __init__(self):
        FlutterWaveConfig.validator()
        self.config = FlutterWaveConfig
        self.auth = FlutterwaveAuth
        self.base_url = self.config.get_base_url()
        self.headers = self.auth.get_headers()
        self.base_app_url = self.config.get_app_base_url()

    def deposit(
        self,
        amount: Decimal,
        customer: Dict[str, str],
        tx_ref: str,  # Now receiving tx_ref as parameter
        **options,
    ) -> PaymentResult:
        """
        Initiate payment collection (deposit).

        Args:
            amount: Amount to collect
            customer: Dict with 'email', 'phone', 'name'
            tx_ref: Transaction reference from your system
            **options:
                - redirect_url: URL to redirect after payment
                - currency: Currency code
                - title: Payment title
                - description: Payment description
                - payment_method: Specific payment method
                - plan: Flutterwave plan ID for recurring payments
        """
        url = f"{self.base_url}/payments"
        redirect_url = options.get(
            "redirect_url",
            f"{self.config.get_base_url()}/{options.get('redirect_url', 'deposit')}",
        )

        payload = {
            "tx_ref": tx_ref,  # Use the provided tx_ref
            "amount": str(amount),
            "currency": options.get("currency", "UGX"),
            "redirect_url": redirect_url,
            "customer": {
                "email": customer["email"],
                "phonenumber": customer[
                    "phone"
                ],  # Changed from phone_number to phonenumber
                "name": customer["name"],
            },
            "customizations": {
                "title": options.get("title", "Payment"),
                "description": options.get("description", "Deposit transaction"),
            },
            "payment_options": self._get_payment_options(options.get("payment_method")),
        }

        # Add plan if provided for subscription
        if options.get("plan"):
            payload["payment_plan"] = options.get("plan")

        try:
            logger.info(f"Initiating deposit with tx_ref: {tx_ref}")
            logger.debug(f"Payload: {json.dumps(payload, indent=2)}")

            response = requests.post(
                url,
                json=payload,
                headers=self.headers,
                timeout=self.config.get_timeout(),
            )

            response_data = response.json()
            logger.debug(f"Response: {json.dumps(response_data, indent=2)}")

            if response.status_code == 200 and response_data.get("status") == "success":
                data = response_data.get("data", {})
                return PaymentResult(
                    success=True,
                    transaction_id=str(data.get("id", "")),
                    tx_ref=tx_ref,  # Return the same tx_ref
                    amount=amount,
                    currency=payload["currency"],
                    provider="flutterwave",
                    transaction_type=TrasnsactionType.DEPOSIT.value,
                    status=TransactionStatus.PENDING.value,
                    status_code=response.status_code,
                    payment_link=data.get("link", ""),
                    metadata=response_data,
                )
            else:
                error_msg = response_data.get("message", "Payment initiation failed")
                logger.error(f"Deposit failed: {error_msg}")
                return self._create_error_result(
                    tx_ref,
                    amount,
                    TrasnsactionType.DEPOSIT.value,
                    error_msg,
                    response.status_code,
                )

        except requests.exceptions.Timeout:
            return self._handle_network_error(tx_ref, amount, "timeout")
        except requests.exceptions.ConnectionError:
            return self._handle_network_error(tx_ref, amount, "connection")
        except Exception as e:
            return self._handle_network_error(tx_ref, amount, str(e))

    def create_subscription_plan(
        self, name: str, amount: Decimal, interval: str, duration: int = None, **options
    ) -> Dict[str, Any]:
        """Create a Flutterwave payment plan"""
        url = f"{self.base_url}/payment-plans"

        payload = {
            "amount": float(amount),
            "name": name,
            "interval": interval.lower(),  # daily, weekly, monthly, quarterly, yearly
            "currency": options.get("currency", "UGX"),
        }

        if duration:
            payload["duration"] = duration

        try:
            response = requests.post(
                url,
                json=payload,
                headers=self.headers,
                timeout=self.config.get_timeout(),
            )
            response_data = response.json()

            if response.status_code == 200 and response_data.get("status") == "success":
                return {
                    "success": True,
                    "data": response_data.get("data", {}),
                    "provider": "flutterwave",
                }
            else:
                return {
                    "success": False,
                    "error": response_data.get("message", "Failed to create plan"),
                    "provider": "flutterwave",
                }
        except Exception as e:
            logger.error(f"Error creating subscription plan: {str(e)}")
            return {"success": False, "error": str(e), "provider": "flutterwave"}

    def fetch_subscription_plans(self) -> List[Dict[str, Any]]:
        """Fetch all Flutterwave payment plans"""
        url = f"{self.base_url}/payment-plans"

        try:
            response = requests.get(
                url, headers=self.headers, timeout=self.config.get_timeout()
            )
            response_data = response.json()

            if response.status_code == 200 and response_data.get("status") == "success":
                return {
                    "success": True,
                    "data": response_data.get("data", []),
                    "provider": "flutterwave",
                }
            else:
                return {
                    "success": False,
                    "error": response_data.get("message", "Failed to fetch plans"),
                    "provider": "flutterwave",
                }
        except Exception as e:
            logger.error(f"Error fetching subscription plans: {str(e)}")
            return {"success": False, "error": str(e), "provider": "flutterwave"}

    def cancel_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """Cancel a Flutterwave subscription"""
        url = f"{self.base_url}/subscriptions/{subscription_id}/cancel"

        try:
            response = requests.put(
                url, headers=self.headers, timeout=self.config.get_timeout()
            )
            response_data = response.json()

            if response.status_code == 200 and response_data.get("status") == "success":
                return {
                    "success": True,
                    "message": "Subscription cancelled successfully",
                    "provider": "flutterwave",
                }
            else:
                return {
                    "success": False,
                    "error": response_data.get("message", "Failed to cancel subscription"),
                    "provider": "flutterwave",
                }
        except Exception as e:
            logger.error(f"Error cancelling subscription: {str(e)}")
            return {"success": False, "error": str(e), "provider": "flutterwave"}

    def withdraw(
        self,
        amount: Decimal,
        recipient: Dict[str, str],
        method: str,
        tx_ref: str,  # Now receiving tx_ref as parameter
        **options,
    ) -> PaymentResult:
        """
        Process withdrawal/payout.

        Args:
            amount: Amount to withdraw
            recipient: Recipient details
            method: 'mobile_money' or 'bank_transfer'
            tx_ref: Transaction reference from your system
            **options:
                - narration: Transaction description
                - mobile_provider: 'MTN' or 'AIRTEL'
                - bank_code: Bank code (for bank transfers)
        """
        url = f"{self.base_url}/transfers"

        # Build base payload
        base_payload = {
            "amount": float(amount),
            "currency": options.get("currency", "UGX"),
            "reference": tx_ref,  # Use the provided tx_ref
            "narration": options.get("narration", "Withdrawal"),
            "callback_url": self.config.get_webhook_url(),
            "debit_currency": options.get("currency", "UGX"),
        }

        # Method-specific configuration
        if method.lower() == "mobile_money":
            payload = self._build_mobile_money_payload(base_payload, recipient, options)
        elif method.lower() == "bank_transfer":
            payload = self._build_bank_transfer_payload(
                base_payload, recipient, options
            )
        else:
            raise PaymentError(f"Unsupported withdrawal method: {method}")

        try:
            logger.info(f"Initiating withdrawal with tx_ref: {tx_ref}")
            logger.debug(f"Payload: {json.dumps(payload, indent=2)}")

            response = requests.post(
                url,
                json=payload,
                headers=self.headers,
                timeout=self.config.get_timeout(),
            )

            response_data = response.json()
            logger.debug(f"Response: {json.dumps(response_data, indent=2)}")

            if response.status_code == 200 and response_data.get("status") == "success":
                data = response_data.get("data", {})
                return PaymentResult(
                    success=True,
                    transaction_id=str(data.get("id", "")),
                    tx_ref=tx_ref,  # Return the same tx_ref
                    amount=amount,
                    currency=payload["currency"],
                    provider="flutterwave",
                    transaction_type=TrasnsactionType.WITHDRAWAL.value,
                    status=data.get("status", TransactionStatus.PROCESSING.value),
                    status_code=response.status_code,
                    metadata=response_data,
                )
            else:
                error_msg = response_data.get("message", "Withdrawal failed")
                logger.error(f"Withdrawal failed: {error_msg}")
                return self._create_error_result(
                    tx_ref,
                    amount,
                    TrasnsactionType.WITHDRAWAL.value,
                    error_msg,
                    response.status_code,
                )

        except requests.exceptions.Timeout:
            return self._handle_network_error(
                tx_ref, amount, "timeout", TrasnsactionType.WITHDRAWAL.value
            )
        except requests.exceptions.ConnectionError:
            return self._handle_network_error(
                tx_ref, amount, "connection", TrasnsactionType.WITHDRAWAL.value
            )
        except Exception as e:
            return self._handle_network_error(
                tx_ref, amount, str(e), TrasnsactionType.WITHDRAWAL.value
            )

    def transfer(
        self,
        amount: Decimal,
        sender: Dict[str, str],
        recipient: Dict[str, str],
        tx_ref: str,  # Add tx_ref
        **options,
    ) -> PaymentResult:
        """
        Transfer money (typically uses withdraw under the hood).
        """
        method = options.get("method", "mobile_money")
        return self.withdraw(amount, recipient, method, tx_ref, **options)

    def verify_transaction(self, transaction_id: str) -> ResultVerification:
        """Verify transaction status"""
        url = f"{self.base_url}/transactions/{transaction_id}/verify"

        try:
            logger.info(f"Verifying transaction: {transaction_id}")

            response = requests.get(
                url, headers=self.headers, timeout=self.config.get_timeout()
            )

            response_data = response.json()

            if response.status_code == 200 and response_data.get("status") == "success":
                data = response_data.get("data", {})
                return ResultVerification(
                    success=True,
                    transaction_id=transaction_id,
                    status=data.get("status", "unknown"),
                    amount=Decimal(str(data.get("amount", 0))),
                    currency=data.get("currency", ""),
                    provider="flutterwave",
                    metadata=response_data,
                )
            else:
                error_msg = response_data.get("message", "Verification failed")
                return ResultVerification(
                    success=False,
                    transaction_id=transaction_id,
                    status="unknown",
                    provider="flutterwave",
                    error=error_msg,
                )

        except Exception as e:
            logger.error(f"Verification error: {str(e)}")
            return ResultVerification(
                success=False,
                transaction_id=transaction_id,
                status="unknown",
                provider="flutterwave",
                error=str(e),
            )

    def get_banks(self, country: str = "UG") -> Dict[str, Any]:
        """Get list of supported banks"""
        url = f"{self.base_url}/banks/{country}"

        try:
            response = requests.get(
                url, headers=self.headers, timeout=self.config.get_timeout()
            )
            response_data = response.json()

            if response.status_code == 200:
                return {
                    "success": True,
                    "data": response_data.get("data", []),
                    "provider": "flutterwave",
                }
            else:
                return {
                    "success": False,
                    "error": "Unable to fetch banks",
                    "provider": "flutterwave",
                }

        except Exception as e:
            logger.error(f"Error fetching banks: {str(e)}")
            return {"success": False, "error": str(e), "provider": "flutterwave"}

    def get_balance(self) -> Dict[str, Any]:
        """Get account balance"""
        url = f"{self.base_url}/balances"

        try:
            response = requests.get(
                url, headers=self.headers, timeout=self.config.get_timeout()
            )
            response_data = response.json()

            if response.status_code == 200:
                return {
                    "success": True,
                    "data": response_data.get("data", []),
                    "provider": "flutterwave",
                }
            else:
                return {
                    "success": False,
                    "error": "Unable to fetch balance",
                    "provider": "flutterwave",
                }

        except Exception as e:
            logger.error(f"Error fetching balance: {str(e)}")
            return {"success": False, "error": str(e), "provider": "flutterwave"}

    # Helper methods
    def _build_mobile_money_payload(
        self, base: Dict, recipient: Dict, options: Dict
    ) -> Dict:
        """Build mobile money transfer payload"""
        provider = options.get("mobile_provider", "MTN").upper()
        mobile = recipient.get("phone", "").replace("+", "").replace(" ", "")

        return {
            **base,
            "account_bank": provider,
            "account_number": mobile,
            "beneficiary_name": recipient.get("name", "Customer"),
        }

    def _build_bank_transfer_payload(
        self, base: Dict, recipient: Dict, options: Dict
    ) -> Dict:
        """Build bank transfer payload"""
        return {
            **base,
            "account_bank": options.get("bank_code", recipient.get("bank_code", "")),
            "account_number": recipient.get("account_number", ""),
            "beneficiary_name": recipient.get(
                "account_name", recipient.get("name", "")
            ),
        }

    def _get_payment_options(self, payment_method: str = None) -> str:
        """Get payment options based on payment method"""
        if payment_method == "mobile_money":
            return "mobilemoneyuganda"
        elif payment_method == "bank_transfer":
            return "banktransfer"
        elif payment_method == "card":
            return "card"
        else:
            return "card,mobilemoneyuganda,banktransfer"

    def _create_error_result(
        self,
        tx_ref: str,
        amount: Decimal,
        tx_type: str,
        error: str,
        status_code: int = None,
    ) -> PaymentResult:
        """Create error result"""
        return PaymentResult(
            success=False,
            transaction_id="",
            tx_ref=tx_ref,
            amount=amount,
            currency="UGX",
            provider="flutterwave",
            transaction_type=tx_type,
            status=TransactionStatus.FAILED.value,
            status_code=status_code,
            error=error,
        )

    def _handle_network_error(
        self,
        tx_ref: str,
        amount: Decimal,
        error_type: str,
        tx_type: str = TrasnsactionType.DEPOSIT.value,
    ) -> PaymentResult:
        """Handle network-related errors"""

        print(f"user ref: {tx_ref} amount: {amount} error type: {error_type} tx_type: {tx_type}")
        error_messages = {
            "timeout": "Payment gateway timeout. Please try again.",
            "connection": "Unable to connect to payment gateway.",
        }
        error = error_messages.get(error_type, f"Payment error: {error_type}")
        logger.error(f"Network error: {error}")
        return self._create_error_result(tx_ref, amount, tx_type, error)
