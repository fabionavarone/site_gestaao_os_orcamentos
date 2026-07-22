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
from .models import AuditLog, Branch, Channel, Company, Conversation, ConversationMessage, Customer, Equipment, OutboxEvent, Role, ServiceOrder, ServiceOrderEvent, Session as UserSession, Team, TeamMember, User, UserRole
from .services.conversations import queue_outbound_message

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
class OrderIn(BaseModel): customer_id: str; equipment_id: str | None = None; title: str = Field(min_length=3,max_length=240); symptom: str | None = None; priority: str = Field(default="normal", pattern="^(low|normal|high|urgent)$")
class TransitionIn(BaseModel): status: str; reason: str | None = Field(default=None,max_length=2000); version: int
class ConversationIn(BaseModel): subject: str = Field(min_length=2,max_length=240); customer_id: str | None = None; channel: str = Field(default="web", pattern="^(web|telegram)$")
class MessageIn(BaseModel): body: str = Field(min_length=1,max_length=10000); internal: bool = False
class AssignmentIn(BaseModel): user_id: str | None = None; status: str = Field(default="human_queue", pattern="^(human_queue|assigned|paused|closed)$")
class OutboundMessageIn(BaseModel): body: str = Field(min_length=1,max_length=10000); idempotency_key: str = Field(min_length=16,max_length=128)
ORDER_TRANSITIONS={"draft":{"awaiting_receipt","received","cancelled"},"awaiting_receipt":{"received","cancelled"},"received":{"triage","cancelled"},"triage":{"diagnosis","technical_hold","customer_hold"},"diagnosis":{"awaiting_budget","no_repair_condition","technical_hold"},"awaiting_budget":{"awaiting_customer_approval"},"awaiting_customer_approval":{"approved","rejected","customer_hold"},"approved":{"awaiting_parts","repair_in_progress"},"awaiting_parts":{"repair_in_progress","technical_hold"},"repair_in_progress":{"quality_test","technical_hold"},"quality_test":{"ready_for_delivery","repair_in_progress"},"ready_for_delivery":{"delivered"},"delivered":{"closed","warranty_return"},"rejected":{"closed"},"no_repair_condition":{"closed"},"technical_hold":{"triage","diagnosis","repair_in_progress"},"customer_hold":{"triage","awaiting_customer_approval"},"financial_hold":{"ready_for_delivery","closed"},"warranty_return":{"triage"},"closed":set(),"cancelled":set()}

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
@app.post("/api/v1/service-orders", status_code=201)
def create_order(payload: OrderIn, user: User=Depends(current_user), session: Session=Depends(db)):
    customer=session.scalar(select(Customer).where(Customer.id==payload.customer_id,Customer.company_id==user.company_id))
    if not customer: raise HTTPException(404,"customer not found")
    if payload.equipment_id and not session.scalar(select(Equipment).where(Equipment.id==payload.equipment_id,Equipment.customer_id==customer.id)): raise HTTPException(422,"equipment does not belong to customer")
    number=(session.query(ServiceOrder).filter_by(company_id=user.company_id).count()+1); item=ServiceOrder(company_id=user.company_id,number=number,**payload.model_dump()); session.add(item); session.flush(); session.add(ServiceOrderEvent(service_order_id=item.id,actor_id=user.id,event_type="created",detail="service order created")); audit(session,user,"create","service_order",item.id); session.commit(); return {"id":item.id,"number":number,"version":item.version}
@app.post("/api/v1/service-orders/{order_id}/transition")
def transition_order(order_id: str,payload: TransitionIn,user: User=Depends(current_user),session: Session=Depends(db)):
    item=session.scalar(select(ServiceOrder).where(ServiceOrder.id==order_id,ServiceOrder.company_id==user.company_id))
    if not item: raise HTTPException(404,"service order not found")
    if item.version != payload.version: raise HTTPException(409,"stale service order version")
    if payload.status not in ORDER_TRANSITIONS.get(item.status,set()): raise HTTPException(409,"invalid service order transition")
    if payload.status in {"cancelled","closed","technical_hold","customer_hold","financial_hold"} and not payload.reason: raise HTTPException(422,"reason required")
    old=item.status; item.status=payload.status; item.version+=1; session.add(ServiceOrderEvent(service_order_id=item.id,actor_id=user.id,event_type="status_changed",detail=f"{old} -> {item.status}: {payload.reason or ''}")); audit(session,user,"transition","service_order",item.id,{"from":old,"to":item.status}); session.commit(); return {"id":item.id,"status":item.status,"version":item.version}
@app.post("/api/v1/conversations",status_code=201)
def create_conversation(payload: ConversationIn,user: User=Depends(current_user),session: Session=Depends(db)):
    if payload.customer_id and not session.scalar(select(Customer).where(Customer.id==payload.customer_id,Customer.company_id==user.company_id)): raise HTTPException(404,"customer not found")
    item=Conversation(company_id=user.company_id,assigned_to=user.id,**payload.model_dump()); session.add(item); audit(session,user,"create","conversation",item.id); session.commit(); return {"id":item.id}
@app.post("/api/v1/conversations/{conversation_id}/messages",status_code=201)
def send_message(conversation_id: str,payload: MessageIn,user: User=Depends(current_user),session: Session=Depends(db)):
    conversation=session.scalar(select(Conversation).where(Conversation.id==conversation_id,Conversation.company_id==user.company_id))
    if not conversation: raise HTTPException(404,"conversation not found")
    message=ConversationMessage(conversation_id=conversation.id,direction="internal" if payload.internal else "outbound",author_name=user.name,body=payload.body,internal=payload.internal); session.add(message); audit(session,user,"message","conversation",conversation.id,{"internal":payload.internal}); session.commit(); return {"id":message.id}

@app.get("/api/v1/conversations")
def inbox(status_filter: str | None = None, limit: int = 50, user: User=Depends(current_user), session: Session=Depends(db)):
    statement=select(Conversation).where(Conversation.company_id == user.company_id).order_by(Conversation.updated_at.desc()).limit(min(limit,100))
    if status_filter: statement=statement.where(Conversation.status == status_filter)
    items=session.scalars(statement).all()
    return {"items":[{"id":item.id,"channel":item.channel,"subject":item.subject,"status":item.status,"assigned_to":item.assigned_to,"automation_paused":item.automation_paused} for item in items]}

@app.post("/api/v1/conversations/{conversation_id}/assignment")
def assign_conversation(conversation_id: str, payload: AssignmentIn, user: User=Depends(current_user), session: Session=Depends(db)):
    conversation=session.scalar(select(Conversation).where(Conversation.id==conversation_id,Conversation.company_id==user.company_id))
    if not conversation: raise HTTPException(404,"conversation not found")
    if payload.user_id:
        assignee=session.scalar(select(User).where(User.id==payload.user_id,User.company_id==user.company_id,User.active.is_(True)))
        if not assignee: raise HTTPException(422,"invalid assignee")
    conversation.assigned_to=payload.user_id; conversation.status=payload.status; conversation.automation_paused=payload.status in {"assigned","paused"}
    audit(session,user,"assign","conversation",conversation.id,{"assigned_to":payload.user_id,"status":payload.status}); session.commit()
    return {"id":conversation.id,"status":conversation.status,"assigned_to":conversation.assigned_to,"automation_paused":conversation.automation_paused}

@app.post("/api/v1/conversations/{conversation_id}/outbound", status_code=201)
def queue_outbound(conversation_id: str, payload: OutboundMessageIn, user: User=Depends(current_user), session: Session=Depends(db)):
    conversation=session.scalar(select(Conversation).where(Conversation.id==conversation_id,Conversation.company_id==user.company_id))
    if not conversation: raise HTTPException(404,"conversation not found")
    channel=session.scalar(select(Channel).where(Channel.company_id==user.company_id,Channel.kind==conversation.channel,Channel.active.is_(True)))
    if not channel: raise HTTPException(409,"active channel not configured")
    message,event,created=queue_outbound_message(session,conversation=conversation,channel=channel,author_name=user.name,body=payload.body,idempotency_key=payload.idempotency_key)
    audit(session,user,"queue_outbound","conversation",conversation.id,{"outbox_event_id":event.id,"created":created}); session.commit()
    return {"message_id":message.id,"outbox_event_id":event.id,"status":event.status,"created":created}

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
