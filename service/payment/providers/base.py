from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
class TrasnsactionType:
    """Type of Transaction"""

    DEPOSIT="deposit"
    WITHDRAW="withdraw"
    TRANSFER="transfer"

class TransactionStatus:
    """Transaction Status"""

    SUCCESS="success"
    FAILED="failed"
    PROCESSING="processing"
    CANCELED="canceled"


@dataclass
class PaymentResult:
    """Render the result of payment standard accross different provider"""
    success: bool
    transaction_id: str
    tx_ref: str
    amount: Decimal
    currency: str
    provider: str
    transaction_type: str
    status: str
    status_code: int = None
    error: str = None
    payment_link: str = None
    metadata: Dict[str, Any] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "transaction_id": self.transaction_id,
            "tx_ref": self.tx_ref,
            "amount": float(self.amount),
            "currency": self.currency,
            "provider": self.provider,
            "transaction_type": self.transaction_type,
            "status": self.status,
            "status_code": self.status_code,
            "error": self.error,
            "payment_link": self.payment_link,
            "metadata": self.metadata or {},
        }



class ResultVerification:
    """Verification of Transaction Result"""

    @abstractmethod
    def deposit(self, amount, user, **option):
        """
        Initiate deposit/payment collection.

        Args:
            amount: Amount to collect
            customer: Customer details (email, phone, name)
            **options: Provider-specific options
        """

    @abstractmethod
    def withdraw(self, amount, recipient, method, tx_ref, **option):
        """
        Process withdrawal/transfer.

        Args:
            amount: Amount to withdraw
            recipient: Recipient details
            method: Withdrawal method (mobile_money, bank_transfer)
            **options: Provider-specific options
        """

    @abstractmethod
    def transfert(self, amount, sender, recipient, tx_ref, **option):
        """
        Transfer money between accounts.

        Args:
            amount: Amount to transfer
            sender: Sender details
            recipient: Recipient details
            **options: Provider-specific options
        """


@dataclass
class PaymentBaseProvider:
    """Abstract base class for all payment providers"""
    
    @abstractmethod
    def deposit(
        self, amount: Decimal, customer: Dict[str, str], **options
    ) -> PaymentResult:
        """
        Initiate deposit/payment collection.

        Args:
            amount: Amount to collect
            customer: Customer details (email, phone, name)
            **options: Provider-specific options
        """
        pass

    @abstractmethod
    def withdraw(
        self, amount: Decimal, recipient: Dict[str, str], method: str, **options
    ) -> PaymentResult:
        """
        Process withdrawal/transfer.

        Args:
            amount: Amount to withdraw
            recipient: Recipient details
            method: Withdrawal method (mobile_money, bank_transfer)
            **options: Provider-specific options
        """
        pass

    @abstractmethod
    def transfer(
        self,
        amount: Decimal,
        sender: Dict[str, str],
        recipient: Dict[str, str],
        **options,
    ) -> PaymentResult:
        """
        Transfer money between accounts.

        Args:
            amount: Amount to transfer
            sender: Sender details
            recipient: Recipient details
            **options: Provider-specific options
        """
        pass

    @abstractmethod
    def verify_transaction(self, transaction_id: str) -> ResultVerification:
        """
        Verify transaction status.

        Args:
            transaction_id: Transaction ID to verify
        """
        pass

    @abstractmethod
    def get_banks(self, country: str = "UG") -> Dict[str, Any]:
        """
        Get list of supported banks.

        Args:
            country: Country code
        """
        pass

    @abstractmethod
    def get_balance(self) -> Dict[str, Any]:
        """Get account balance"""
        pass

    @abstractmethod
    def create_subscription_plan(
        self, 
        name: str, 
        amount: Decimal, 
        interval: str, 
        duration: Optional[int] = None,
        **options
    ) -> Dict[str, Any]:
        """
        Create a subscription plan.

        Args:
            name: Plan name
            amount: Amount per interval
            interval: Frequency (daily, weekly, monthly, etc.)
            duration: Number of intervals (None for perpetual)
            **options: Provider-specific options
        """
        pass

    @abstractmethod
    def fetch_subscription_plans(self) -> List[Dict[str, Any]]:
        """Fetch all subscription plans"""
        pass

    @abstractmethod
    def cancel_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """
        Cancel an active subscription.

        Args:
            subscription_id: Provider's subscription ID
        """
        pass
