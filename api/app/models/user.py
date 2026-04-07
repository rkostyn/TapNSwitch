from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class User(BaseModel):
    user_id: str
    user_name: str
    email: Optional[str]
    created_at: Optional[datetime] = None


class UserCreate(BaseModel):
    user_name: str
    email: str
    password: str
    registration_token: str


class UserGet(BaseModel):
    user_id: str
    user_name: Optional[str]
    email: Optional[str]


class UserDelete(BaseModel):
    user_id: str
    user_name: str
    email: str