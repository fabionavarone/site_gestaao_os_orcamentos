import hashlib, secrets
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from .config import settings
from .db import Base, engine, SessionLocal
from .models import AuditLog, Branch, Company, Customer, Equipment, Role, Session as UserSession, Team, TeamMember, User, UserRole

# OWASP-aligned memory-hard hashing, tuned to the 4-vCPU deployment target.
pwd = CryptContext(schemes=["argon2"], argon2__memory_cost=19456, argon2__time_cost=2, argon2__parallelism=2, deprecated="auto")
COOKIE = "provisao_session"
def utcnow() -> datetime: return datetime.now(UTC)
def db():
    session = SessionLocal()
    try: yield session
    finally: session.close()
def audit(session: Session, user: User | None, action: str, entity: str, entity_id: str, detail: dict | None = None):
    session.add(AuditLog(company_id=user.company_id if user else None, actor_id=user.id if user else None, action=action, entity_type=entity, entity_id=entity_id, detail=detail or {}))
def token_hash(value: str) -> str: return hashlib.sha256(value.encode()).hexdigest()
def current_user(request: Request, session: Session = Depends(db)) -> User:
    raw = request.cookies.get(COOKIE)
    if not raw: raise HTTPException(401, "authentication required")
    item = session.scalar(select(UserSession).where(UserSession.token_hash == token_hash(raw), UserSession.revoked_at.is_(None), UserSession.expires_at > utcnow()))
    if not item: raise HTTPException(401, "session expired")
    user = session.get(User, item.user_id)
    if not user or not user.active: raise HTTPException(401, "inactive user")
    if request.method not in {"GET", "HEAD", "OPTIONS"} and request.headers.get("X-CSRF-Token") != item.csrf_token: raise HTTPException(403, "csrf validation failed")
    return user
def require(permission: str):
    def dependency(user: User = Depends(current_user), session: Session = Depends(db)) -> User:
        roles = session.scalars(select(Role).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == user.id)).all()
        permitted = any(role.code == "admin" or permission in role.permissions.get("permissions", []) for role in roles)
        if not permitted:
            audit(session, user, "access_denied", "permission", permission); session.commit()
            raise HTTPException(403, "permission denied")
        return user
    return dependency

class Login(BaseModel): email: EmailStr; password: str = Field(min_length=12, max_length=256)
class CustomerIn(BaseModel): name: str = Field(min_length=2, max_length=160); document: str | None = Field(default=None, max_length=32); email: EmailStr | None = None; phone: str | None = Field(default=None, max_length=32)
class EquipmentIn(BaseModel): customer_id: str; category: str = Field(min_length=2,max_length=100); manufacturer: str | None = None; model: str | None = None; serial_number: str | None = None
class RoleIn(BaseModel): code: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$"); name: str = Field(min_length=2,max_length=100); permissions: list[str] = Field(default_factory=list)
class BranchIn(BaseModel): name: str = Field(min_length=2,max_length=160)
class TeamIn(BaseModel): name: str = Field(min_length=2,max_length=160); branch_id: str | None = None
class UserIn(BaseModel): name: str = Field(min_length=2,max_length=160); email: EmailStr; password: str = Field(min_length=12,max_length=256); role_ids: list[str] = Field(min_length=1)

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
app = FastAPI(title="Provisao Manager API", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings().origins, allow_credentials=True, allow_methods=["GET","POST","PATCH","DELETE"], allow_headers=["Content-Type","X-CSRF-Token","X-Request-ID"])

@app.get("/api/v1/health")
def health(): return {"status":"ok", "ai_enabled": settings().local_llm_enabled}
@app.get("/api/v1/readiness")
def readiness(session: Session = Depends(db)):
    session.execute(select(1)); return {"status":"ready"}
@app.post("/api/v1/auth/login")
def login(payload: Login, response: Response, session: Session = Depends(db)):
    user = session.scalar(select(User).where(User.email == payload.email.lower()))
    if not user or not user.active or (user.locked_until and user.locked_until > utcnow()) or not pwd.verify(payload.password, user.password_hash):
        if user: user.failed_logins += 1; user.locked_until = utcnow()+timedelta(minutes=min(30, 2**min(user.failed_logins,4))) if user.failed_logins >= 5 else None; session.commit()
        raise HTTPException(401, "invalid credentials")
    user.failed_logins=0; user.locked_until=None; raw=secrets.token_urlsafe(48); csrf=secrets.token_urlsafe(32); session.add(UserSession(user_id=user.id, token_hash=token_hash(raw), csrf_token=csrf, expires_at=utcnow()+timedelta(hours=8))); audit(session,user,"login","session",user.id); session.commit(); response.set_cookie(COOKIE,raw,httponly=True,secure=settings().app_env!="development",samesite="strict",max_age=28800,path="/"); return {"user":{"id":user.id,"name":user.name,"email":user.email},"csrf_token":csrf}
@app.post("/api/v1/auth/logout")
def logout(request: Request, response: Response, session: Session = Depends(db)):
    raw=request.cookies.get(COOKIE)
    if raw:
        item=session.scalar(select(UserSession).where(UserSession.token_hash==token_hash(raw)))
        if item: item.revoked_at=utcnow(); session.commit()
    response.delete_cookie(COOKIE,path="/"); return {"ok":True}
@app.post("/api/v1/customers", status_code=201)
def create_customer(payload: CustomerIn, user: User=Depends(current_user), session: Session=Depends(db)):
    item=Customer(company_id=user.company_id, **payload.model_dump()); session.add(item); audit(session,user,"create","customer",item.id); session.commit(); return {"id":item.id}
@app.post("/api/v1/equipment", status_code=201)
def create_equipment(payload: EquipmentIn, user: User=Depends(current_user), session: Session=Depends(db)):
    customer=session.get(Customer,payload.customer_id)
    if not customer or customer.company_id != user.company_id: raise HTTPException(404,"customer not found")
    item=Equipment(company_id=user.company_id,internal_code=f"EQ-{secrets.token_hex(5).upper()}",**payload.model_dump()); session.add(item); audit(session,user,"create","equipment",item.id); session.commit(); return {"id":item.id}

@app.post("/api/v1/roles", status_code=201)
def create_role(payload: RoleIn, user: User=Depends(require("organization.manage")), session: Session=Depends(db)):
    if session.scalar(select(Role).where(Role.company_id == user.company_id, Role.code == payload.code)): raise HTTPException(409, "role already exists")
    item=Role(company_id=user.company_id, code=payload.code, name=payload.name, permissions={"permissions":payload.permissions}); session.add(item); audit(session,user,"create","role",item.id); session.commit(); return {"id":item.id}
@app.post("/api/v1/branches", status_code=201)
def create_branch(payload: BranchIn, user: User=Depends(require("organization.manage")), session: Session=Depends(db)):
    item=Branch(company_id=user.company_id, name=payload.name); session.add(item); audit(session,user,"create","branch",item.id); session.commit(); return {"id":item.id}
@app.post("/api/v1/teams", status_code=201)
def create_team(payload: TeamIn, user: User=Depends(require("organization.manage")), session: Session=Depends(db)):
    if payload.branch_id and not session.scalar(select(Branch).where(Branch.id == payload.branch_id, Branch.company_id == user.company_id)): raise HTTPException(404,"branch not found")
    item=Team(company_id=user.company_id, **payload.model_dump()); session.add(item); audit(session,user,"create","team",item.id); session.commit(); return {"id":item.id}
@app.post("/api/v1/users", status_code=201)
def create_user(payload: UserIn, user: User=Depends(require("organization.manage")), session: Session=Depends(db)):
    if session.scalar(select(User).where(User.email == payload.email.lower())): raise HTTPException(409,"email already exists")
    roles=session.scalars(select(Role).where(Role.id.in_(payload.role_ids), Role.company_id == user.company_id)).all()
    if len(roles) != len(set(payload.role_ids)): raise HTTPException(422,"invalid roles")
    item=User(company_id=user.company_id,name=payload.name,email=payload.email.lower(),password_hash=pwd.hash(payload.password)); session.add(item); session.flush()
    for role in roles: session.add(UserRole(user_id=item.id,role_id=role.id))
    audit(session,user,"create","user",item.id); session.commit(); return {"id":item.id}
