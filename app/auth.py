import os
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from .database import get_db
from .models import AdminUser, Customer

SECRET_KEY = os.getenv("JWT_SECRET", "dev-secret-change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 12

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/admin/login")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_admin(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> AdminUser:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciais inválidas",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        if email is None or payload.get("type") != "admin":
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    admin = db.query(AdminUser).filter(AdminUser.email == email).first()
    if admin is None:
        raise credentials_exception
    return admin


def get_current_customer(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> Customer:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciais inválidas",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        if email is None or payload.get("type") != "customer":
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    customer = db.query(Customer).filter(Customer.email == email).first()
    if customer is None:
        raise credentials_exception
    return customer
