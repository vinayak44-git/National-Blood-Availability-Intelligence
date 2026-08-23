from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from fastapi import Cookie
from app.database import get_connection
from app.auth.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token
)


router = APIRouter(prefix="/auth", tags=["Authentication"])



class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str
    role: str
    hospital_id: str | None = None
    doctor_id: str | None = None
    bank_id: str | None = None


@router.post("/register")
def register_user(data: RegisterRequest):

    allowed_roles = {
        "requester",
        "provider",
        "dispatcher",
        "patient"
    }

    if data.role not in allowed_roles:
        raise HTTPException(
            status_code=400,
            detail="Invalid role"
        )

    if len(data.password) < 8:
        raise HTTPException(
            status_code=400,
            detail="Password must contain at least 8 characters"
        )

    conn = get_connection()

    existing_user = conn.execute(
        "SELECT user_id FROM users WHERE username = ?",
        (data.username,)
    ).fetchone()

    if existing_user:
        conn.close()

        raise HTTPException(
            status_code=409,
            detail="Username already exists"
        )

    if data.role == "requester":
        if not data.hospital_id:
            data.hospital_id = "H01"
        if not data.doctor_id:
            data.doctor_id = "D01"
    elif data.role == "provider":
        if not data.bank_id:
            data.bank_id = "B01"

    user_id = f"U{conn.execute('SELECT COUNT(*) FROM users').fetchone()[0] + 1:04d}"

    password_hash = hash_password(data.password)

    conn.execute(
        """
        INSERT INTO users (
            user_id,
            username,
            password_hash,
            role,
            hospital_id,
            doctor_id,
            bank_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            data.username,
            password_hash,
            data.role,
            data.hospital_id,
            data.doctor_id,
            data.bank_id
        )
    )

    conn.commit()
    conn.close()

    return {
        "message": "User registered successfully",
        "user_id": user_id,
        "role": data.role
    }


@router.post("/login")
def login(data: LoginRequest, response: Response):

    conn = get_connection()

    user = conn.execute(
        """
        SELECT
            user_id,
            username,
            password_hash,
            role,
            hospital_id,
            doctor_id,
            bank_id,
            is_active
        FROM users
        WHERE username = ?
        """,
        (data.username,)
    ).fetchone()

    conn.close()

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password"
        )

    if not user["is_active"]:
        raise HTTPException(
            status_code=403,
            detail="Account is disabled"
        )

    if not verify_password(
        data.password,
        user["password_hash"]
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password"
        )

    token = create_access_token(
    user["user_id"],
    user["role"],
    user["hospital_id"],
    user["doctor_id"],
    user["bank_id"]
)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=60 * 60
    )

    return {
        "message": "Login successful",
        "user_id": user["user_id"],
        "role": user["role"]
    }


@router.post("/logout")
def logout(response: Response):

    response.delete_cookie("access_token")

    return {
        "message": "Logged out successfully"
    }


def get_current_user(
    access_token: str | None = Cookie(default=None)
):
    if not access_token:
        raise HTTPException(
            status_code=401,
            detail="Authentication required"
        )

    user = decode_access_token(access_token)

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired session"
        )

    return user


@router.get("/me")
def get_me(current_user=Depends(get_current_user)):
    user_info = dict(current_user)
    conn = get_connection()
    if current_user.get("hospital_id"):
        h_row = conn.execute(
            "SELECT name, lat, lng FROM hospitals WHERE hospital_id = ?",
            (current_user["hospital_id"],)
        ).fetchone()
        if h_row:
            user_info["hospital_name"] = h_row["name"]
            user_info["hospital_lat"] = h_row["lat"]
            user_info["hospital_lng"] = h_row["lng"]
    if current_user.get("doctor_id"):
        d_row = conn.execute(
            "SELECT name FROM doctors WHERE doctor_id = ?",
            (current_user["doctor_id"],)
        ).fetchone()
        if d_row:
            user_info["doctor_name"] = d_row["name"]
    if current_user.get("bank_id"):
        b_row = conn.execute(
            "SELECT name FROM blood_banks WHERE bank_id = ?",
            (current_user["bank_id"],)
        ).fetchone()
        if b_row:
            user_info["bank_name"] = b_row["name"]

    u_row = conn.execute(
        "SELECT username FROM users WHERE user_id = ?",
        (current_user["user_id"],)
    ).fetchone()
    if u_row:
        user_info["username"] = u_row["username"]

    conn.close()
    return user_info


def require_role(*allowed_roles):

    def role_checker(
        current_user=Depends(get_current_user)
    ):
        if current_user["role"] not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail="You do not have permission to access this resource"
            )

        return current_user

    return role_checker