"""
auth.py — 인증 모듈 (회원가입 / 로그인 / JWT)
DB: SQLite (users.db) — 배포 시 PostgreSQL 교체 가능
"""
import sqlite3
import hashlib
import hmac
import os
import time
import base64
import json
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr

# ─── 설정 ────────────────────────────────────────────────────
DB_PATH     = Path(__file__).parent / "users.db"
SECRET_KEY  = os.getenv("JWT_SECRET", "welfare-secret-key-change-in-production")
TOKEN_EXPIRE = 60 * 60 * 24 * 7   # 7일 (초)

router  = APIRouter(prefix="/auth", tags=["auth"])
bearer  = HTTPBearer(auto_error=False)

# ─── DB 초기화 ───────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            email       TEXT UNIQUE NOT NULL,
            password    TEXT,              -- NULL이면 카카오 전용 계정
            name        TEXT NOT NULL,
            birth_year  INTEGER,
            gender      TEXT,
            login_type  TEXT DEFAULT 'email',   -- 'email' | 'kakao'
            kakao_id    TEXT,
            created_at  REAL DEFAULT (strftime('%s','now'))
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ─── 비밀번호 해시 ───────────────────────────────────────────
def _hash_pw(password: str) -> str:
    return hashlib.sha256((password + SECRET_KEY).encode()).hexdigest()

def _verify_pw(password: str, hashed: str) -> bool:
    return hmac.compare_digest(_hash_pw(password), hashed)

# ─── JWT (라이브러리 미사용, 단순 HS256 직접 구현) ───────────
def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

def _sign(data: str) -> str:
    import hmac as _hmac, hashlib as _hash
    sig = _hmac.new(SECRET_KEY.encode(), data.encode(), _hash.sha256).digest()
    return _b64url(sig)

def create_token(user_id: int, email: str) -> str:
    header  = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = _b64url(json.dumps({
        "sub": user_id,
        "email": email,
        "exp": time.time() + TOKEN_EXPIRE
    }).encode())
    sig = _sign(f"{header}.{payload}")
    return f"{header}.{payload}.{sig}"

def decode_token(token: str) -> Optional[dict]:
    try:
        header, payload, sig = token.split(".")
        if _sign(f"{header}.{payload}") != sig:
            return None
        data = json.loads(base64.urlsafe_b64decode(payload + "=="))
        if data.get("exp", 0) < time.time():
            return None
        return data
    except Exception:
        return None

def get_current_user(creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer)) -> Optional[dict]:
    if not creds:
        return None
    return decode_token(creds.credentials)

def require_auth(creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer)) -> dict:
    user = get_current_user(creds)
    if not user:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
    return user

# ─── Pydantic 모델 ───────────────────────────────────────────
class SignupRequest(BaseModel):
    email: str
    password: str
    name: str
    birth_year: Optional[int] = None
    gender: Optional[str] = None    # 'male' | 'female' | 'other'

class LoginRequest(BaseModel):
    email: str
    password: str

class KakaoLoginRequest(BaseModel):
    kakao_id: str
    email: Optional[str] = None
    name: Optional[str] = None

# ─── 엔드포인트 ─────────────────────────────────────────────

@router.post("/signup")
def signup(data: SignupRequest):
    if len(data.password) < 8:
        raise HTTPException(status_code=400, detail="비밀번호는 8자 이상이어야 해요.")
    hashed = _hash_pw(data.password)

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "INSERT INTO users (email, password, name, birth_year, gender, login_type) VALUES (?,?,?,?,?,?)",
            (data.email, hashed, data.name, data.birth_year, data.gender, "email")
        )
        conn.commit()
        uid = conn.execute("SELECT id FROM users WHERE email=?", (data.email,)).fetchone()[0]
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=409, detail="이미 사용 중인 이메일이에요.")
    finally:
        conn.close()

    token = create_token(uid, data.email)
    return {
        "access_token": token,
        "token_type":   "bearer",
        "user": {
            "id":         uid,
            "email":      data.email,
            "name":       data.name,
            "birth_year": data.birth_year,
            "gender":     data.gender,
            "login_type": "email",
        }
    }


@router.post("/login")
def login(data: LoginRequest):
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT id, email, password, name, birth_year, gender, login_type FROM users WHERE email=?",
        (data.email,)
    ).fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=401, detail="이메일 또는 비밀번호가 올바르지 않아요.")
    uid, email, pw_hash, name, birth_year, gender, login_type = row

    if login_type == "kakao":
        raise HTTPException(status_code=400, detail="카카오 계정으로 가입된 이메일이에요. 카카오 로그인을 이용해주세요.")

    if not _verify_pw(data.password, pw_hash or ""):
        raise HTTPException(status_code=401, detail="이메일 또는 비밀번호가 올바르지 않아요.")

    token = create_token(uid, email)
    return {
        "access_token": token,
        "token_type":   "bearer",
        "user": {
            "id":         uid,
            "email":      email,
            "name":       name,
            "birth_year": birth_year,
            "gender":     gender,
            "login_type": login_type,
        }
    }


@router.post("/kakao")
def kakao_login(data: KakaoLoginRequest):
    """
    카카오 OAuth 콜백 후 kakao_id로 회원가입/로그인 처리.
    프론트에서 카카오 SDK로 kakao_id 받아서 이 엔드포인트로 전송.
    """
    conn = sqlite3.connect(DB_PATH)

    # 기존 카카오 계정 조회
    row = conn.execute(
        "SELECT id, email, name, birth_year, gender, login_type FROM users WHERE kakao_id=?",
        (data.kakao_id,)
    ).fetchone()

    if row:
        uid, email, name, birth_year, gender, login_type = row
        conn.close()
    else:
        # 신규 카카오 사용자 생성
        email = data.email or f"kakao_{data.kakao_id}@kakao.com"
        name  = data.name or "카카오 사용자"
        conn.execute(
            "INSERT OR IGNORE INTO users (email, name, login_type, kakao_id) VALUES (?,?,?,?)",
            (email, name, "kakao", data.kakao_id)
        )
        conn.commit()
        uid = conn.execute("SELECT id FROM users WHERE kakao_id=?", (data.kakao_id,)).fetchone()[0]
        birth_year, gender = None, None
        conn.close()

    token = create_token(uid, email)
    return {
        "access_token": token,
        "token_type":   "bearer",
        "user": {
            "id":         uid,
            "email":      email,
            "name":       name,
            "birth_year": birth_year,
            "gender":     gender,
            "login_type": "kakao",
        }
    }


@router.get("/me")
def get_me(current_user: dict = Depends(require_auth)):
    """현재 로그인 유저 정보 조회."""
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT id, email, name, birth_year, gender, login_type, created_at FROM users WHERE id=?",
        (current_user["sub"],)
    ).fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="유저를 찾을 수 없어요.")
    uid, email, name, birth_year, gender, login_type, created_at = row
    return {
        "id":         uid,
        "email":      email,
        "name":       name,
        "birth_year": birth_year,
        "gender":     gender,
        "login_type": login_type,
        "created_at": created_at,
    }


@router.put("/me")
def update_me(data: dict, current_user: dict = Depends(require_auth)):
    """프로필 업데이트 (이름, 출생연도, 성별)."""
    allowed = {k: v for k, v in data.items() if k in ("name", "birth_year", "gender")}
    if not allowed:
        raise HTTPException(status_code=400, detail="수정할 항목이 없어요.")

    sets   = ", ".join(f"{k}=?" for k in allowed)
    values = list(allowed.values()) + [current_user["sub"]]
    conn   = sqlite3.connect(DB_PATH)
    conn.execute(f"UPDATE users SET {sets} WHERE id=?", values)
    conn.commit()
    conn.close()
    return {"message": "업데이트 완료"}
