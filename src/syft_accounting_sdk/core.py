"""
Core module for the Accounting SDK providing user and transaction management functionality.
"""

from __future__ import annotations

from typing import Literal, Optional, Union

import requests

from logging import getLogger
from .error import ServiceException
from .schemas import User, Transaction


logger = getLogger(__name__)


class AdminClient:
    """Client for administrative operations in the accounting service.

    Attributes:
        url: Base URL of the accounting service
        key: API key for authentication
        session: Requests session with authentication headers
    """

    def __init__(self, *, url: str, key: str) -> None:
        """Initialize the admin client.

        Args:
            url: Base URL of the accounting service
            key: API key for authentication
        """
        self.url: str = url.rstrip("/")
        self.key: str = key
        self._session: requests.Session = requests.Session()
        self._session.headers.update({"Authorization": f"Bearer {self.key}"})

    def create_user(
        self,
        *,
        email: str,
        organization: str,
        password: Optional[str] = None,
    ) -> tuple[User, str]:
        """Create a new user in the accounting system.

        Args:
            email: Email address for the new user
            organization: Name of the organization the user belongs to
            password: Optional password for the user. If not provided, one will be generated

        Returns:
            A tuple of (User object, password)

        Raises:
            ServiceException: If the user creation fails
        """
        response = self._session.post(
            f"{self.url}/user/create",
            json={"email": email, "password": password, "organization": organization},
        )
        if not response.ok:
            raise ServiceException(response.status_code, response.json())

        data = response.json()
        return User(**data["user"]), password or data["password"]

    def add_balance(self, *, email: str, amount: float) -> User:
        """Add balance to a user's account.

        Args:
            email: Email of the user to add balance to
            amount: Amount to add to the user's balance

        Returns:
            Updated User object

        Raises:
            ServiceException: If the balance addition fails
            ValueError: If amount is not positive
        """
        if amount <= 0:
            raise ValueError("Amount must be positive")

        response = self._session.post(
            f"{self.url}/user/add-balance",
            json={"recipientEmail": email, "amount": amount},
        )

        if not response.ok:
            raise ServiceException(response.status_code, response.json())

        return User(**response.json()["user"])

    def get_user(self, *, email: str) -> User:
        """Get user information by email.

        Args:
            email: Email of the user to retrieve

        Returns:
            User object

        Raises:
            ServiceException: If the user retrieval fails
        """
        response = self._session.get(f"{self.url}/user/{email}")

        if not response.ok:
            raise ServiceException(response.status_code, response.json())

        return User(**response.json()["user"])

    def get_all_users(
        self, format: Literal["list", "dict"] = "list"
    ) -> Union[list[User], dict[str, User]]:
        """Get all users in the system.

        Args:
            format: Format of the return value.
                   "list" returns a list of User objects
                   "dict" returns a dict mapping emails to User objects

        Returns:
            List of User objects or dict of email -> User mappings

        Raises:
            ServiceException: If the users retrieval fails
            ValueError: If format is invalid
        """
        response = self._session.get(f"{self.url}/users")

        if not response.ok:
            raise ServiceException(response.status_code, response.json())

        users = [User(**item) for item in response.json()["users"]]
        if format == "list":
            return users

        return {user.email: user for user in users}


class TransactionCtx:
    """Context manager for handling the lifecycle of a transaction.

    On entering, creates a transaction. If not confirmed by the user, cancels the transaction on exit.

    Args:
        client: UserClient instance
        email: Email of the recipient
        amount: Amount to transfer
    """

    def __init__(
        self,
        client: "UserClient",
        email: str,
        amount: float,
        appName: Optional[str] = None,
        appEpPath: Optional[str] = None,
    ):
        self.client = client
        self.email = email
        self.amount = amount
        self.transaction: Optional[Transaction] = None
        self._confirmed = False
        self.appName = appName
        self.appEpPath = appEpPath

    def __enter__(self) -> "TransactionCtx":
        self.transaction = self.client.create_transaction(
            recipientEmail=self.email,
            amount=self.amount,
            appName=self.appName,
            appEpPath=self.appEpPath,
        )
        return self

    def confirm(self) -> Transaction:
        if self.transaction is None:
            raise RuntimeError("No transaction to confirm.")
        self.transaction = self.client.confirm_transaction(id=self.transaction.id)
        self._confirmed = True
        return self.transaction

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self._confirmed and self.transaction is not None:
            try:
                self.transaction = self.client.cancel_transaction(
                    id=self.transaction.id
                )
            except Exception:
                raise ServiceException(500, {"message": "Failed to cancel transaction"})


class DelegatedTransactionCtx(TransactionCtx):
    """Context manager for handling the lifecycle of a delegated transaction.

    On entering, creates a transaction on behalf of another user.
    If not confirmed by the user, cancels the transaction on exit.

    Args:
        client: UserClient instance
        email: Email of the user who is authorizing the transaction
        amount: Amount to transfer
        token: Delegation token authorizing the transaction
    """

    def __init__(
        self,
        client: "UserClient",
        email: str,
        amount: float,
        token: str,
        appName: Optional[str] = None,
        appEpPath: Optional[str] = None,
    ):
        super().__init__(client, email, amount, appName, appEpPath)
        self.token = token

    def __enter__(self) -> "DelegatedTransactionCtx":
        self.transaction = self.client.create_delegated_transaction(
            senderEmail=self.email,
            amount=self.amount,
            token=self.token,
            appName=self.appName,
            appEpPath=self.appEpPath,
        )
        return self


class UserClient:
    """Client for user operations in the accounting service.

    Attributes:
        url: Base URL of the accounting service
        email: User's email address
        _session: Requests session with authentication
    """

    def __init__(self, url: str, email: str, password: str) -> None:
        """Initialize the user client.

        Args:
            url: Base URL of the accounting service
            email: User's email address
            password: User's password for authentication
        """
        self.url: str = url.rstrip("/")
        self.email: str = email
        self._session: requests.Session = requests.Session()
        self._session.auth = (email, password)

    @classmethod
    def create_user(
        cls,
        *,
        url: str,
        email: str,
        organization: str,
        password: Optional[str] = None,
    ) -> tuple[User, str]:
        """Create a new user and return a client instance.

        Args:
            url: Base URL of the accounting service
            email: Email address for the new user
            password: Optional password for the user. If not provided, one will be generated

        Returns:
            A tuple of (User object, password)

        Raises:
            ServiceException: If the user creation fails
        """
        response = requests.post(
            f"{url.rstrip('/')}/user/create",
            json={
                "email": email,
                "password": password,
                "organization": organization,
            },
        )
        if not response.ok:
            raise ServiceException(response.status_code, response.json())

        data = response.json()
        return User(**data["user"]), password or data["password"]

    def get_user_info(self) -> User:
        """Get the current user's information.

        Returns:
            User object for the current user

        Raises:
            ServiceException: If the user info retrieval fails
        """
        response = self._session.get(f"{self.url}/user/my-info")

        if not response.ok:
            raise ServiceException(response.status_code, response.json())

        return User(**response.json()["user"])

    def create_transaction(
        self,
        *,
        recipientEmail: str,
        amount: float,
        appName: Optional[str] = None,
        appEpPath: Optional[str] = None,
    ) -> Transaction:
        """Create a new transaction from the current user.

        Args:
            recipientEmail: Email of the recipient
            amount: Amount to transfer
            appName: Name of the application initiating the transaction
            appEpPath: Path of the endpoint initiating the transaction

        Returns:
            Created Transaction object

        Raises:
            ServiceException: If the transaction creation fails
            ValueError: If amount is not positive
        """
        if amount <= 0:
            raise ValueError("Amount must be positive")

        response = self._session.post(
            f"{self.url}/transaction/create",
            json={
                "senderEmail": self.email,
                "recipientEmail": recipientEmail,
                "amount": amount,
                "appName": appName,
                "appEpPath": appEpPath,
            },
        )

        if not response.ok:
            raise ServiceException(response.status_code, response.json())

        return Transaction(**response.json()["transaction"])

    def create_delegated_transaction(
        self,
        *,
        senderEmail: str,
        amount: float,
        token: str,
        appName: Optional[str] = None,
        appEpPath: Optional[str] = None,
    ) -> Transaction:
        """Create a transaction on behalf of another user using a delegation token.

        Args:
            senderEmail: Email of the user sending the funds
            amount: Amount to transfer
            token: Delegation token authorizing the transaction

        Returns:
            Created Transaction object

        Raises:
            ServiceException: If the transaction creation fails
            ValueError: If amount is not positive
        """
        if amount <= 0:
            raise ValueError("Amount must be positive")

        response = self._session.post(
            f"{self.url}/transaction/create",
            json={
                "senderEmail": senderEmail,
                "recipientEmail": self.email,
                "amount": amount,
                "token": token,
                "appName": appName,
                "appEpPath": appEpPath,
            },
        )

        if not response.ok:
            raise ServiceException(response.status_code, response.json())

        return Transaction(**response.json()["transaction"])

    def create_transaction_token(self, *, recipientEmail: str) -> str:
        """Create a delegation token for future transactions.

        Args:
            recipientEmail: Email of the user who will be authorized to create transactions

        Returns:
            Delegation token string

        Raises:
            ServiceException: If the token creation fails
        """
        response = self._session.post(
            f"{self.url}/token/create", json={"recipientEmail": recipientEmail}
        )

        if not response.ok:
            raise ServiceException(response.status_code, response.json())

        return response.json()["token"]

    def confirm_transaction(self, *, id: str) -> Transaction:
        """Confirm a pending transaction.

        Args:
            id: ID of the transaction to confirm

        Returns:
            Updated Transaction object

        Raises:
            ServiceException: If the transaction confirmation fails
        """
        response = self._session.post(
            f"{self.url}/transaction/confirm", json={"transactionId": id}
        )

        if not response.ok:
            raise ServiceException(response.status_code, response.json())

        return Transaction(**response.json()["transaction"])

    def cancel_transaction(self, *, id: str) -> Transaction:
        """Cancel a pending transaction.

        Args:
            id: ID of the transaction to cancel

        Returns:
            Updated Transaction object

        Raises:
            ServiceException: If the transaction cancellation fails
        """
        response = self._session.post(
            f"{self.url}/transaction/cancel", json={"transactionId": id}
        )

        if not response.ok:
            raise ServiceException(response.status_code, response.json())

        return Transaction(**response.json()["transaction"])

    def transfer(
        self,
        recipientEmail: str,
        amount: float,
        app_name: Optional[str] = None,
        app_ep_path: Optional[str] = None,
    ) -> TransactionCtx:
        """Convenience method to use TransactionContext as a context manager.

        Args:
            recipientEmail: Email of the recipient
            amount: Amount to transfer
        Returns:
            TransactionContext instance
        """
        return TransactionCtx(self, recipientEmail, amount, app_name, app_ep_path)

    def delegated_transfer(
        self,
        senderEmail: str,
        amount: float,
        token: str,
        app_name: Optional[str] = None,
        app_ep_path: Optional[str] = None,
    ) -> DelegatedTransactionCtx:
        """Convenience method to use DelegatedTransactionCtx as a context manager.

        Args:
            senderEmail: Email of the sender, who is authorizing the transaction
            amount: Amount to transfer
            token: Delegation token authorizing the transaction

        Returns:
            DelegatedTransactionContext instance
        """
        return DelegatedTransactionCtx(
            self, senderEmail, amount, token, app_name, app_ep_path
        )

    def get_transaction_history(self) -> list[Transaction]:
        """Get the transaction history for the current user.

        Returns:
            List of Transaction objects

        Raises:
            ServiceException: If the transaction history retrieval fails
        """
        response = self._session.get(f"{self.url}/transactions")

        if not response.ok:
            raise ServiceException(response.status_code, response.json())

        response_json = response.json()

        return [Transaction(**item) for item in response_json["transactions"]]

    def update_password(self, *, old_password: str, new_password: str) -> User:
        """Update the password for the current user.

        Args:
            old_password: Old password for the user
            new_password: New password for the user

        Returns:
            Updated User object

        Raises:
            ServiceException: If the password update fails
        """

        response = self._session.put(
            f"{self.url}/user/update-password",
            json={"oldPassword": old_password, "newPassword": new_password},
        )

        if not response.ok:
            raise ServiceException(response.status_code, response.json())

        return User(**response.json()["user"])

    def update_organization(self, *, organization: str) -> User:
        """Update the organization for the current user.

        Args:
            organization: New organization for the user

        Returns:
            Updated User object

        Raises:
            ServiceException: If the organization update fails
        """
        response = self._session.put(
            f"{self.url}/user/update-organization",
            json={"organization": organization},
        )

        if not response.ok:
            raise ServiceException(response.status_code, response.json())

        return User(**response.json()["user"])
