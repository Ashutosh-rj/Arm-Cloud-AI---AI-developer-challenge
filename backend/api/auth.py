import logging
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext

from db.connection import get_pool
from auth.middleware import create_access_token

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class TokenResponse(BaseModel):
    access_token: str
    token_type: str

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    
@router.post("/register", response_model=TokenResponse)
async def register(data: RegisterRequest) -> Any:
    pool = await get_pool()
    hashed = pwd_context.hash(data.password)
    async with pool.acquire() as conn:
        # Check if email exists
        exists = await conn.fetchval("SELECT id FROM users WHERE email = $1", data.email)
        if exists:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
            
        # Create user
        user_id = await conn.fetchval(
            "INSERT INTO users (email, hashed_password) VALUES ($1, $2) RETURNING id",
            data.email, hashed
        )
        
    access_token = create_access_token(data={"sub": data.email, "user_id": str(user_id)})
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/login", response_model=TokenResponse)
async def login(form_data: OAuth2PasswordRequestForm = Depends()) -> Any:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT id, email, hashed_password FROM users WHERE email = $1 AND is_active = TRUE", form_data.username)
        if not row:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
            
        if not pwd_context.verify(form_data.password, row["hashed_password"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
            
        access_token = create_access_token(data={"sub": row["email"], "user_id": str(row["id"])})
        return {"access_token": access_token, "token_type": "bearer"}
