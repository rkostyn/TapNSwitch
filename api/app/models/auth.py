from pydantic import BaseModel, Field
from typing import Optional


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=10, max_length=128)
    email: str = Field(max_length=254)
    registration_token: str = Field(max_length=128)

class RegisterResponse(BaseModel):
    user_id: str
    username: str
    email: str

class LoginRequest(BaseModel):
    credentials: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 86400