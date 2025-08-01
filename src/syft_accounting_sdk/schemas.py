from pydantic import BaseModel, EmailStr, Field, field_validator
from enum import Enum
from datetime import datetime
from typing import Optional


class User(BaseModel):
    """Represents a user in the accounting system."""

    id: str
    email: EmailStr
    balance: float = Field(ge=0.0)
    organization: Optional[str] = None

    def __str__(self) -> str:
        return f"User(id={self.id}, email={self.email}, balance={self.balance})"

    def __repr__(self) -> str:
        model_dict = self.model_dump()
        return "User\n" + "\n".join(
            f"  {k + ':':<12} {v}" for k, v in model_dict.items()
        )


class CreatorType(str, Enum):
    """Enumeration for the entity that created or resolved a transaction."""

    SYSTEM = "SYSTEM"
    SENDER = "SENDER"
    RECIPIENT = "RECIPIENT"


class TransactionStatus(str, Enum):
    """Enumeration for the status of a transaction."""

    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class Transaction(BaseModel):
    """Represents a financial transaction between users."""

    id: str
    senderEmail: EmailStr
    recipientEmail: EmailStr
    createdBy: CreatorType
    resolvedBy: Optional[CreatorType] = None
    amount: float = Field(gt=0.0)
    status: TransactionStatus
    createdAt: datetime
    resolvedAt: Optional[datetime] = None
    appName: Optional[str] = None
    appEpPath: Optional[str] = None

    def __str__(self) -> str:
        return (
            f"Transaction(id={self.id}, from={self.senderEmail}, "
            f"to={self.recipientEmail}, amount={self.amount}, status={self.status})"
        )

    def __repr__(self) -> str:
        model_dict = self.model_dump()
        return "Transaction\n" + "\n".join(
            f"  {k + ':':<15} {v}" for k, v in model_dict.items()
        )
