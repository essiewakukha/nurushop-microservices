from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel, EmailStr
import secrets

app = FastAPI(title= "Nurushop Auth service")

#in-memeory stores( reset on restart)
users: dict[str, str] = {}      # email -> password
tokens: dict[str, str] = {}     # token -> email


class Credentials(BaseModel):
    email: EmailStr
    password: str


@app.post("/api/v1/register", status_code=201)
def register(creds: Credentials):
    if creds.email in users:
        raise HTTPException(status_code=409, detail="User already exists")
    if len(creds.password) < 8:
        raise HTTPException(status_code=422, detail="Password too short")
    users[creds.email] = creds.password
    return {"message": "User registered", "email": creds.email}


@app.post("/api/v1/login")
def login(creds: Credentials):
    if users.get(creds.email) != creds.password:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = secrets.token_hex(16)
    tokens[token] = creds.email
    return {"access_token": token, "token_type": "bearer"}


@app.get("/api/v1/validate")
def validate(authorization: str = Header(default="")):
    token = authorization.removeprefix("Bearer ").strip()
    email = tokens.get(token)
    if not email:
        raise HTTPException(status_code=401, detail="Invalid token")
    return {"valid": True, "email": email}


@app.get("/health")
def health():
    return {"status": "healthy"}