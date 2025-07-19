"""
Core module for the Accounting SDK providing user and transaction management functionality.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional, Union

import requests
from pydantic import BaseModel, EmailStr, Field, validator


class User(BaseModel):
    """Represents a user in the accounting system.

    Attributes:
        id: Unique identifier for the user
        email: User's email address
        balance: User's current balance
    """

    id: str
    email: EmailStr
    balance: float = Field(ge=0.0)

    def __str__(self) -> str:
        """Return a human-readable string representation of the user."""
        return f"User(id={self.id}, email={self.email}, balance={self.balance})"

    def __repr__(self) -> str:
        """Return a detailed string representation of the user."""
        model_dict = self.model_dump()
        return "User\n" + "\n".join(
            f"  {k + ':':<12} {v}" for k, v in model_dict.items()
        )


CreatorType = Literal["SYSTEM", "SENDER", "RECIPIENT"]
TransactionStatus = Literal["PENDING", "COMPLETED", "CANCELLED"]


class Transaction(BaseModel):
    """Represents a financial transaction between users.

    Attributes:
        id: Unique identifier for the transaction
        senderEmail: Email of the user sending the funds
        recipientEmail: Email of the user receiving the funds
        createdBy: Entity that created the transaction
        resolvedBy: Entity that resolved (completed/cancelled) the transaction
        amount: Amount of money being transferred
        status: Current status of the transaction
        createdAt: Timestamp when the transaction was created
        resolvedAt: Timestamp when the transaction was resolved
    """

    id: str
    senderEmail: EmailStr
    recipientEmail: EmailStr
    createdBy: CreatorType
    resolvedBy: Optional[CreatorType] = None
    amount: float = Field(gt=0.0)
    status: TransactionStatus
    createdAt: datetime
    resolvedAt: Optional[datetime] = None

    @validator("amount")
    def validate_amount(cls, v: float) -> float:
        """Validate that the transaction amount is positive."""
        if v <= 0:
            raise ValueError("Transaction amount must be positive")
        return v

    def __str__(self) -> str:
        """Return a human-readable string representation of the transaction."""
        return (
            f"Transaction(id={self.id}, from={self.senderEmail}, "
            f"to={self.recipientEmail}, amount={self.amount}, status={self.status})"
        )

    def __repr__(self) -> str:
        """Return a detailed string representation of the transaction."""
        model_dict = self.model_dump()
        return "Transaction\n" + "\n".join(
            f"  {k + ':':<15} {v}" for k, v in model_dict.items()
        )


class ServiceException(Exception):
    """Exception raised for errors in the accounting service.

    Attributes:
        status_code: HTTP status code of the error
        body: Response body containing error details
        message: Formatted error message
    """

    def __init__(self, status_code: int, body: dict[str, str]) -> None:
        self.status_code = status_code
        self.body = body
        self.message = f"Error {status_code}: {body}"
        super().__init__(self.message)


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
        self, *, email: str, password: Optional[str] = None
    ) -> tuple[User, str]:
        """Create a new user in the accounting system.

        Args:
            email: Email address for the new user
            password: Optional password for the user. If not provided, one will be generated

        Returns:
            A tuple of (User object, password)

        Raises:
            ServiceException: If the user creation fails
        """
        response = self._session.post(
            f"{self.url}/user/create",
            json={"email": email, "password": password},
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
        cls, *, url: str, email: str, password: Optional[str] = None
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
            json={"email": email, "password": password},
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

    def create_transaction(self, *, recipientEmail: str, amount: float) -> Transaction:
        """Create a new transaction from the current user.

        Args:
            recipientEmail: Email of the recipient
            amount: Amount to transfer

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
            },
        )

        if not response.ok:
            raise ServiceException(response.status_code, response.json())

        return Transaction(**response.json()["transaction"])

    def create_delegated_transaction(
        self, *, senderEmail: str, amount: float, token: str
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
