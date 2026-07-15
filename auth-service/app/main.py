from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, Field  # type: ignore[import]
import secrets

app = FastAPI(title="NuruShop Auth Service")
security = HTTPBearer(auto_error=False)

# In-memory stores (reset on restart — fine for this project)
users: dict[str, str] = {}      # email -> password
tokens: dict[str, str] = {}     # token -> email


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


@app.post(
    "/api/v1/register",
    status_code=201,
    responses={
        400: {"description": "Malformed request body"},
        409: {"description": "User already exists"},
    },
)
def register(creds: Credentials):
    if creds.email in users:
        raise HTTPException(status_code=409, detail="User already exists")
    users[creds.email] = creds.password
    return {"message": "User registered", "email": creds.email}


@app.post(
    "/api/v1/login",
    responses={
        400: {"description": "Malformed request body"},
        401: {"description": "Invalid credentials"},
    },
)
def login(creds: Credentials):
    if users.get(creds.email) != creds.password:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = secrets.token_hex(16)
    tokens[token] = creds.email
    return {"access_token": token, "token_type": "bearer"}


@app.get(
    "/api/v1/validate",
    responses={401: {"description": "Missing or invalid token"}},
)
def validate(credentials: HTTPAuthorizationCredentials | None = Depends(security)):
    email = tokens.get(credentials.credentials) if credentials else None
    if not email:
        raise HTTPException(
            status_code=401,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {"valid": True, "email": email}


@app.get("/health")
def health():
    return {"status": "healthy"}