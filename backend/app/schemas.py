from datetime import date
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    full_name: str
    mobile_number: str = Field(pattern=r"^[6-9]\d{9}$")
    email: Optional[EmailStr] = None
    password: str = Field(min_length=6)
    village_id: str
    ward_id: str
    house_number: Optional[str] = None
    address: Optional[str] = None
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None
    occupation: Optional[str] = None


class LoginRequest(BaseModel):
    mobile_number: str
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=6)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user_id: str


class ComplaintCreate(BaseModel):
    category_id: str
    title: str
    description: str
    location: Optional[str] = None
    priority: str = "Medium"


class ComplaintStatusUpdate(BaseModel):
    new_status: str
    remark: Optional[str] = None
    assigned_to: Optional[str] = None
