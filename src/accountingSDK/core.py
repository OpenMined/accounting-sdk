import json
from typing import Literal, Optional, Union
import requests
from datetime import datetime

from pydantic import BaseModel


class User(BaseModel):
    id: str
    email: str
    balance: float

    def __repr__(self):
        model_dict = self.model_dump()
        return "User\n" + "\n".join(f"  {k+':':<12} {v}" for k, v in model_dict.items())


class Transaction(BaseModel):
    id: str
    senderEmail: str
    recipientEmail: str
    createdBy: Literal["SYSTEM", "SENDER", "RECIPIENT"]
    resolvedBy: Optional[Literal["SYSTEM", "SENDER", "RECIPIENT"]]
    amount: float
    status: Literal["PENDING", "COMPLETED", "CANCELLED"]
    createdAt: datetime
    resolvedAt: Optional[datetime]

    def __repr__(self):
        model_dict = self.model_dump()
        return "Transaction\n" + "\n".join(
            f"  {k+':':<15} {v}" for k, v in model_dict.items()
        )


class ServiceException(Exception):
    def __init__(self, status_code, body):
        self.status_code = status_code
        self.message = f"Error {status_code}: {body}"
        super().__init__(self.message)


class AdminClient:
    def __init__(self, *, url: str, key: str):
        self.url = url
        self.key = key
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {self.key}"})

    def create_user(
        self, *, email: str, password: Optional[str] = None
    ) -> tuple[User, str]:
        response = self.session.post(
            f"{self.url}/user/create",
            json={"email": email, "password": password},
        )
        if not response.ok:
            raise ServiceException(response.status_code, response.json())

        if password:
            return User(**response.json()["user"]), password
        return User(**response.json()["user"]), response.json()["password"]

    def add_balance(self, *, email: str, amount: float):
        response = self.session.post(
            f"{self.url}/user/add-balance",
            json={"recipientEmail": email, "amount": amount},
        )

        if not response.ok:
            raise ServiceException(response.status_code, response.json())

        return User(**response.json()["user"])

    def get_user(self, *, email: str):
        response = self.session.get(f"{self.url}/user/{email}")

        if not response.ok:
            raise ServiceException(response.status_code, response.json())

        return User(**response.json()["user"])

    def get_all_users(self, format: Literal["list", "dict"] = "list"):
        if format not in ["list", "dict"]:
            raise ValueError('format must be one of "list" or "dict"')

        response = self.session.get(f"{self.url}/users")

        if not response.ok:
            raise ServiceException(response.status_code, response.json())

        users = [User(**item) for item in response.json()["users"]]
        if format == "list":
            return users

        return {user.email: user for user in users}


class UserClient:
    def __init__(self, url: str, email: str, password: str):
        self.url = url
        self.email = email
        self.session = requests.Session()
        self.session.auth = (email, password)

    @classmethod
    def create_user(
        cls, *, url: str, email: str, password: Optional[str] = None
    ) -> tuple[User, str]:
        response = requests.post(
            f"{url}/user/create",
            json={"email": email, "password": password},
        )
        if not response.ok:
            raise ServiceException(response.status_code, response.json())

        if password:
            return User(**response.json()["user"]), password
        return User(**response.json()["user"]), response.json()["password"]

    def get_user_info(self):
        response = self.session.get(f"{self.url}/user/my-info")

        if not response.ok:
            raise ServiceException(response.status_code, response.json())

        return User(**response.json()["user"])

    def create_transaction(self, *, recipientEmail: str, amount: float):
        response = self.session.post(
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
    ):
        response = self.session.post(
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

    def create_transaction_token(self, *, recipientEmail: str):
        response = self.session.post(
            f"{self.url}/token/create", json={"recipientEmail": recipientEmail}
        )

        if not response.ok:
            raise ServiceException(response.status_code, response.json())

        return response.json()["token"]

    def confirm_transaction(self, *, id: str):
        response = self.session.post(
            f"{self.url}/transaction/confirm", json={"transactionId": id}
        )

        if not response.ok:
            raise ServiceException(response.status_code, response.json())

        return Transaction(**response.json()["transaction"])

    def cancel_transaction(self, *, id: str):
        response = self.session.post(
            f"{self.url}/transaction/cancel", json={"transactionId": id}
        )

        if not response.ok:
            raise ServiceException(response.status_code, response.json())

        return Transaction(**response.json()["transaction"])
