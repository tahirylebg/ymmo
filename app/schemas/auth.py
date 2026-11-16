"""Input / output contracts for authentication (validated by Pydantic)."""

import re

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.enums import UserRole

PHONE_PATTERN = r"^\+?[0-9 .-]{10,20}$"


class PasswordPolicy:
    """Single place for the password rules (reused by register and password change)."""

    MIN_LENGTH = 10

    @classmethod
    def validate(cls, value: str) -> str:
        problems = []
        if len(value) < cls.MIN_LENGTH:
            problems.append(f"au moins {cls.MIN_LENGTH} caractères")
        if not re.search(r"[a-z]", value):
            problems.append("une minuscule")
        if not re.search(r"[A-Z]", value):
            problems.append("une majuscule")
        if not re.search(r"\d", value):
            problems.append("un chiffre")
        if problems:
            raise ValueError("Le mot de passe doit contenir " + ", ".join(problems) + ".")
        return value


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    phone: str | None = Field(default=None, pattern=PHONE_PATTERN)

    @field_validator("password")
    @classmethod
    def _password_policy(cls, value: str) -> str:
        return PasswordPolicy.validate(value)

    @field_validator("first_name", "last_name")
    @classmethod
    def _strip(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Champ obligatoire.")
        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    first_name: str
    last_name: str
    phone: str | None
    role: UserRole
    agency_id: int | None
