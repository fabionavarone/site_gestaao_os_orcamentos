import hashlib, hmac, json, logging, secrets, time
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status, UploadFile, File, Form
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from .config import settings
from .db import Base, engine, SessionLocal
from .models import Attachment, AuditLog, Branch, Channel, ChannelBot, Company, Conversation, ConversationMessage, Customer, Equipment, ExternalEvent, OutboxEvent, Role, ServiceOrder, ServiceOrderEvent, Session as UserSession, Team, TeamMember, User, UserRole
from .services.conversations import queue_outbound_message
from .services.crypto import CredentialCipher, masked_token, token_fingerprint
from .services.storage import LocalStorage
from .services.telegram import TelegramClient, TelegramError, payload_hash

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
class BotCreateIn(BaseModel): name: str = Field(min_length=2,max_length=160); token: str = Field(min_length=10,max_length=256); mode: str = Field(default="disabled",pattern="^(webhook|polling|disabled)$")
class BotUpdateIn(BaseModel): name: str | None = Field(default=None,min_length=2,max_length=160); mode: str | None = Field(default=None,pattern="^(webhook|polling|disabled)$")
class TokenReplaceIn(BaseModel): token: str = Field(min_length=10,max_length=256)
class ConversationStateIn(BaseModel): status: str = Field(pattern="^(new|queued|assigned|waiting_customer|waiting_internal|resolved|closed)$"); assigned_user_id: str | None = None; assigned_team_id: str | None = None
class LinkConversationIn(BaseModel): customer_id: str | None = None; equipment_id: str | None = None; service_order_id: str | None = None
ORDER_TRANSITIONS={"draft":{"awaiting_receipt","received","cancelled"},"awaiting_receipt":{"received","cancelled"},"received":{"triage","cancelled"},"triage":{"diagnosis","technical_hold","customer_hold"},"diagnosis":{"awaiting_budget","no_repair_condition","technical_hold"},"awaiting_budget":{"awaiting_customer_approval"},"awaiting_customer_approval":{"approved","rejected","customer_hold"},"approved":{"awaiting_parts","repair_in_progress"},"awaiting_parts":{"repair_in_progress","technical_hold"},"repair_in_progress":{"quality_test","technical_hold"},"quality_test":{"ready_for_delivery","repair_in_progress"},"ready_for_delivery":{"delivered"},"delivered":{"closed","warranty_return"},"rejected":{"closed"},"no_repair_condition":{"closed"},"technical_hold":{"triage","diagnosis","repair_in_progress"},"customer_hold":{"triage","awaiting_customer_approval"},"financial_hold":{"ready_for_delivery","closed"},"warranty_return":{"triage"},"closed":set(),"cancelled":set()}

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
app = FastAPI(title="Provisao Manager API", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings().origins, allow_credentials=True, allow_methods=["GET","POST","PATCH","DELETE"], allow_headers=["Content-Type","X-CSRF-Token","X-Request-ID"])

@app.middleware("http")
async def request_observability(request:Request,call_next):
    request_id=(request.headers.get("X-Request-ID") or secrets.token_hex(12))[:64]; started=time.monotonic()
    try: response=await call_next(request); result=str(response.status_code)
    except Exception: result="500"; logging.getLogger("provisao.api").exception(json.dumps({"service":"api","correlation_id":request_id,"operation":request.url.path,"result":result})); raise
    response.headers["X-Request-ID"]=request_id
    logging.getLogger("provisao.api").info(json.dumps({"service":"api","correlation_id":request_id,"operation":request.url.path,"result":result,"duration_ms":round((time.monotonic()-started)*1000,2)}))
    return response

@app.get("/api/v1/health")
def health(): return {"status":"ok", "ai_enabled": settings().local_llm_enabled}
@app.get("/api/v1/readiness")
def readiness(session: Session = Depends(db)):
    session.execute(select(1)); return {"status":"ready"}
@app.get("/api/v1/operational-metrics")
def operational_metrics(user:User=Depends(require("audit.read")),session:Session=Depends(db)):
    def grouped(model,column): return {str(k):v for k,v in session.execute(select(column,func.count()).where(model.company_id==user.company_id).group_by(column)).all()}
    return {"external_events":grouped(ExternalEvent,ExternalEvent.status),"outbox":grouped(OutboxEvent,OutboxEvent.status),"conversations":grouped(Conversation,Conversation.status),"attachments":{"count":session.scalar(select(func.count()).where(Attachment.company_id==user.company_id)) or 0,"bytes":session.scalar(select(func.coalesce(func.sum(Attachment.size_bytes),0)).where(Attachment.company_id==user.company_id)) or 0},"unassigned_conversations":session.scalar(select(func.count()).where(Conversation.company_id==user.company_id,Conversation.assigned_to.is_(None),Conversation.status.in_(["new","queued"]))) or 0}
@app.post("/api/v1/auth/login")
def login(payload: Login, response: Response, session: Session = Depends(db)):
    user = session.scalar(select(User).where(User.email == payload.email.lower()))
    if not user or not user.active or (user.locked_until and user.locked_until > utcnow()) or not pwd.verify(payload.password, user.password_hash):
        if user: user.failed_logins += 1; user.locked_until = utcnow()+timedelta(minutes=min(30, 2**min(user.failed_logins,4))) if user.failed_logins >= 5 else None; session.commit()
        raise HTTPException(401, "invalid credentials")
    user.failed_logins=0; user.locked_until=None; raw=secrets.token_urlsafe(48); csrf=secrets.token_urlsafe(32); session.add(UserSession(user_id=user.id, token_hash=token_hash(raw), csrf_token=csrf, expires_at=utcnow()+timedelta(hours=8))); audit(session,user,"login","session",user.id); session.commit(); response.set_cookie(COOKIE,raw,httponly=True,secure=settings().app_env!="development",samesite="strict",max_age=28800,path="/"); return {"user":{"id":user.id,"name":user.name,"email":user.email},"csrf_token":csrf}
@app.post("/api/v1/auth/logout")
def logout(request: Request, response: Response, user:User=Depends(current_user),session: Session = Depends(db)):
    raw=request.cookies.get(COOKIE)
    if raw:
        item=session.scalar(select(UserSession).where(UserSession.token_hash==token_hash(raw)))
        if item: item.revoked_at=utcnow(); session.commit()
    response.delete_cookie(COOKIE,path="/"); return {"ok":True}
@app.get("/api/v1/auth/me")
def auth_me(user:User=Depends(current_user)): return {"user":{"id":user.id,"name":user.name,"email":user.email}}

def bot_view(bot: ChannelBot) -> dict:
    return {"id":bot.id,"public_id":bot.public_id,"name":bot.name,"username":bot.username,"telegram_bot_id":bot.telegram_bot_id,"mode":bot.mode,"status":bot.status,"active":bot.active,"token":masked_token(bot.token_fingerprint),"last_validated_at":bot.last_validated_at,"last_error":bot.last_error,"created_at":bot.created_at,"updated_at":bot.updated_at}

def telegram_client(bot: ChannelBot) -> TelegramClient:
    cfg=settings(); cipher=CredentialCipher(cfg.telegram_token_encryption_key,cfg.telegram_token_encryption_previous_keys)
    if not bot.token_ciphertext: raise HTTPException(409,"bot token is not configured")
    return TelegramClient(cipher.decrypt(bot.token_ciphertext),api_base=cfg.telegram_api_base_url,file_base=cfg.telegram_file_base_url,timeout=cfg.telegram_request_timeout_seconds)

def owned_bot(session: Session, user: User, bot_id: str) -> ChannelBot:
    bot=session.scalar(select(ChannelBot).where(ChannelBot.id==bot_id,ChannelBot.company_id==user.company_id))
    if not bot: raise HTTPException(404,"Telegram bot not found")
    return bot

@app.get("/api/v1/telegram/bots")
def list_bots(user: User=Depends(require("telegram.manage")),session: Session=Depends(db)):
    return {"items":[bot_view(item) for item in session.scalars(select(ChannelBot).where(ChannelBot.company_id==user.company_id).order_by(ChannelBot.name)).all()]}

@app.post("/api/v1/telegram/bots",status_code=201)
def create_bot(payload: BotCreateIn,user: User=Depends(require("telegram.manage")),session: Session=Depends(db)):
    if session.scalar(select(ChannelBot).where(ChannelBot.company_id==user.company_id,ChannelBot.name==payload.name)): raise HTTPException(409,"bot name already exists")
    cfg=settings(); cipher=CredentialCipher(cfg.telegram_token_encryption_key,cfg.telegram_token_encryption_previous_keys)
    client=TelegramClient(payload.token,api_base=cfg.telegram_api_base_url,file_base=cfg.telegram_file_base_url,timeout=cfg.telegram_request_timeout_seconds)
    try: identity=client.get_me()
    except TelegramError as exc: raise HTTPException(422,"Telegram token validation failed") from exc
    channel=session.scalar(select(Channel).where(Channel.company_id==user.company_id,Channel.kind=="telegram",Channel.name==payload.name))
    if not channel: channel=Channel(company_id=user.company_id,kind="telegram",name=payload.name); session.add(channel); session.flush()
    secret=secrets.token_urlsafe(32)
    bot=ChannelBot(company_id=user.company_id,channel_id=channel.id,name=payload.name,public_id=secrets.token_hex(18),username=identity.get("username"),telegram_bot_id=str(identity["id"]),token_ciphertext=cipher.encrypt(payload.token),token_fingerprint=token_fingerprint(payload.token),webhook_secret_ciphertext=cipher.encrypt(secret),webhook_secret_hash=token_hash(secret),mode=payload.mode,status="inactive",active=False,last_validated_at=utcnow(),created_by=user.id)
    session.add(bot); session.flush(); audit(session,user,"telegram_bot_created","channel_bot",bot.id,{"username":bot.username,"mode":bot.mode}); session.commit(); return bot_view(bot)

@app.get("/api/v1/telegram/bots/{bot_id}")
def get_bot(bot_id:str,user: User=Depends(require("telegram.manage")),session: Session=Depends(db)): return bot_view(owned_bot(session,user,bot_id))

@app.patch("/api/v1/telegram/bots/{bot_id}")
def update_bot(bot_id:str,payload:BotUpdateIn,user:User=Depends(require("telegram.manage")),session:Session=Depends(db)):
    bot=owned_bot(session,user,bot_id)
    if payload.name is not None: bot.name=payload.name
    if payload.mode is not None:
        if bot.active: raise HTTPException(409,"deactivate bot before changing mode")
        bot.mode=payload.mode
    audit(session,user,"telegram_bot_updated","channel_bot",bot.id,{"mode":bot.mode}); session.commit(); return bot_view(bot)

@app.post("/api/v1/telegram/bots/{bot_id}/validate")
def validate_bot(bot_id:str,user:User=Depends(require("telegram.manage")),session:Session=Depends(db)):
    bot=owned_bot(session,user,bot_id); bot.status="validating"; session.flush()
    try: identity=telegram_client(bot).get_me()
    except (TelegramError,ValueError) as exc:
        bot.status="error"; bot.last_error="token validation failed"; audit(session,user,"telegram_bot_validation_failed","channel_bot",bot.id); session.commit(); raise HTTPException(422,"Telegram token validation failed") from exc
    bot.username=identity.get("username"); bot.telegram_bot_id=str(identity["id"]); bot.last_validated_at=utcnow(); bot.last_error=None; bot.status="active" if bot.active else "inactive"; audit(session,user,"telegram_bot_validated","channel_bot",bot.id); session.commit(); return bot_view(bot)

@app.post("/api/v1/telegram/bots/{bot_id}/replace-token")
def replace_bot_token(bot_id:str,payload:TokenReplaceIn,user:User=Depends(require("telegram.manage")),session:Session=Depends(db)):
    bot=owned_bot(session,user,bot_id); cfg=settings()
    try: identity=TelegramClient(payload.token,api_base=cfg.telegram_api_base_url,file_base=cfg.telegram_file_base_url,timeout=cfg.telegram_request_timeout_seconds).get_me()
    except TelegramError as exc: raise HTTPException(422,"Telegram token validation failed") from exc
    cipher=CredentialCipher(cfg.telegram_token_encryption_key,cfg.telegram_token_encryption_previous_keys); bot.token_ciphertext=cipher.encrypt(payload.token); bot.token_fingerprint=token_fingerprint(payload.token); bot.username=identity.get("username"); bot.telegram_bot_id=str(identity["id"]); bot.last_validated_at=utcnow(); bot.last_error=None; audit(session,user,"telegram_bot_token_replaced","channel_bot",bot.id); session.commit(); return bot_view(bot)

@app.post("/api/v1/telegram/bots/{bot_id}/activate")
def activate_bot(bot_id:str,user:User=Depends(require("telegram.manage")),session:Session=Depends(db)):
    bot=owned_bot(session,user,bot_id)
    if bot.mode=="disabled" or not bot.last_validated_at: raise HTTPException(409,"validated bot mode required")
    bot.active=True; bot.status="active"; bot.last_error=None; audit(session,user,"telegram_bot_activated","channel_bot",bot.id,{"mode":bot.mode}); session.commit(); return bot_view(bot)

@app.post("/api/v1/telegram/bots/{bot_id}/deactivate")
def deactivate_bot(bot_id:str,user:User=Depends(require("telegram.manage")),session:Session=Depends(db)):
    bot=owned_bot(session,user,bot_id); bot.active=False; bot.status="inactive"; audit(session,user,"telegram_bot_deactivated","channel_bot",bot.id); session.commit(); return bot_view(bot)

@app.post("/api/v1/telegram/bots/{bot_id}/configure-webhook")
def configure_webhook(bot_id:str,user:User=Depends(require("telegram.manage")),session:Session=Depends(db)):
    bot=owned_bot(session,user,bot_id)
    if bot.mode!="webhook": raise HTTPException(409,"bot is not in webhook mode")
    cfg=settings(); cipher=CredentialCipher(cfg.telegram_token_encryption_key,cfg.telegram_token_encryption_previous_keys)
    secret=cipher.decrypt(bot.webhook_secret_ciphertext); url=f"{cfg.public_base_url.rstrip('/')}/api/v1/telegram/webhooks/{bot.public_id}"
    try: telegram_client(bot).set_webhook(url,secret)
    except TelegramError as exc: bot.last_error="webhook configuration failed"; session.commit(); raise HTTPException(502,"Telegram webhook configuration failed") from exc
    bot.last_error=None; audit(session,user,"telegram_webhook_configured","channel_bot",bot.id,{"url_host":cfg.public_base_url}); session.commit(); return {"ok":True,"url":url}

@app.delete("/api/v1/telegram/bots/{bot_id}/webhook")
def delete_webhook(bot_id:str,user:User=Depends(require("telegram.manage")),session:Session=Depends(db)):
    bot=owned_bot(session,user,bot_id)
    try: telegram_client(bot).delete_webhook()
    except TelegramError as exc: raise HTTPException(502,"Telegram webhook removal failed") from exc
    audit(session,user,"telegram_webhook_deleted","channel_bot",bot.id); session.commit(); return {"ok":True}

@app.get("/api/v1/telegram/bots/{bot_id}/health")
def bot_health(bot_id:str,user:User=Depends(require("telegram.manage")),session:Session=Depends(db)):
    bot=owned_bot(session,user,bot_id); info={}
    if bot.mode=="webhook":
        try: info=telegram_client(bot).webhook_info()
        except TelegramError: info={"error":"provider unavailable"}
    return {"status":bot.status,"active":bot.active,"mode":bot.mode,"last_error":bot.last_error,"provider":info}

@app.get("/api/v1/telegram/bots/{bot_id}/delivery-metrics")
def bot_metrics(bot_id:str,user:User=Depends(require("telegram.manage")),session:Session=Depends(db)):
    bot=owned_bot(session,user,bot_id); rows=session.execute(select(OutboxEvent.status,func.count()).where(OutboxEvent.bot_id==bot.id).group_by(OutboxEvent.status)).all(); return {"outbox":{key:value for key,value in rows}}

@app.post("/api/v1/telegram/webhooks/{bot_public_id}",status_code=202)
async def telegram_webhook(bot_public_id:str,request:Request,session:Session=Depends(db)):
    cfg=settings(); raw=await request.body()
    if len(raw)>cfg.telegram_webhook_max_bytes: raise HTTPException(413,"payload too large")
    bot=session.scalar(select(ChannelBot).where(ChannelBot.public_id==bot_public_id,ChannelBot.active.is_(True),ChannelBot.mode=="webhook"))
    if not bot: raise HTTPException(404,"not found")
    provided=request.headers.get("X-Telegram-Bot-Api-Secret-Token","")
    if not hmac.compare_digest(token_hash(provided),bot.webhook_secret_hash or ""): raise HTTPException(403,"invalid webhook secret")
    recent=session.scalar(select(func.count()).where(ExternalEvent.bot_id==bot.id,ExternalEvent.received_at>utcnow()-timedelta(minutes=1))) or 0
    if recent>=120: raise HTTPException(429,"rate limit exceeded")
    try: payload=__import__("json").loads(raw)
    except (ValueError,UnicodeDecodeError): raise HTTPException(400,"invalid payload")
    if not isinstance(payload,dict) or not isinstance(payload.get("update_id"),int): raise HTTPException(400,"invalid payload")
    external_id=str(payload["update_id"]); key=f"telegram:{bot.id}:{external_id}"
    existing=session.scalar(select(ExternalEvent).where(ExternalEvent.idempotency_key==key))
    if existing: return {"accepted":True,"duplicate":True}
    event=ExternalEvent(company_id=bot.company_id,channel_id=bot.channel_id,bot_id=bot.id,external_event_id=external_id,idempotency_key=key,payload=payload,payload_hash=payload_hash(payload),status="received")
    session.add(event); session.flush(); session.add(AuditLog(company_id=bot.company_id,actor_id=None,action="telegram_update_received",entity_type="external_event",entity_id=event.id,detail={"bot_id":bot.id,"update_id":external_id})); session.commit(); return {"accepted":True,"duplicate":False}
@app.post("/api/v1/customers", status_code=201)
def create_customer(payload: CustomerIn, user: User=Depends(current_user), session: Session=Depends(db)):
    item=Customer(company_id=user.company_id, **payload.model_dump()); session.add(item); session.flush(); audit(session,user,"create","customer",item.id); session.commit(); return {"id":item.id}
@app.post("/api/v1/equipment", status_code=201)
def create_equipment(payload: EquipmentIn, user: User=Depends(current_user), session: Session=Depends(db)):
    customer=session.get(Customer,payload.customer_id)
    if not customer or customer.company_id != user.company_id: raise HTTPException(404,"customer not found")
    item=Equipment(company_id=user.company_id,internal_code=f"EQ-{secrets.token_hex(5).upper()}",**payload.model_dump()); session.add(item); session.flush(); audit(session,user,"create","equipment",item.id); session.commit(); return {"id":item.id}
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
    item=Conversation(company_id=user.company_id,assigned_to=user.id,**payload.model_dump()); session.add(item); session.flush(); audit(session,user,"create","conversation",item.id); session.commit(); return {"id":item.id}
@app.post("/api/v1/conversations/{conversation_id}/messages",status_code=201)
def send_message(conversation_id: str,payload: MessageIn,user: User=Depends(current_user),session: Session=Depends(db)):
    conversation=session.scalar(select(Conversation).where(Conversation.id==conversation_id,Conversation.company_id==user.company_id))
    if not conversation: raise HTTPException(404,"conversation not found")
    if payload.internal:
        message=ConversationMessage(company_id=user.company_id,channel_id=conversation.channel_id,conversation_id=conversation.id,direction="internal",author_name=user.name,body=payload.body,normalized_text=payload.body,message_type="internal_note",status="received",internal=True,sender_user_id=user.id); session.add(message)
    else:
        channel=session.get(Channel,conversation.channel_id) if conversation.channel_id else session.scalar(select(Channel).where(Channel.company_id==user.company_id,Channel.kind==conversation.channel,Channel.active.is_(True)))
        if not channel: raise HTTPException(409,"active channel not configured")
        message,_,_=queue_outbound_message(session,conversation=conversation,channel=channel,author_name=user.name,body=payload.body,idempotency_key=f"web:{conversation.id}:{secrets.token_hex(16)}",bot_id=conversation.bot_id)
    audit(session,user,"internal_note_created" if payload.internal else "message_queued","conversation",conversation.id,{"message_id":message.id}); session.commit(); return {"id":message.id}

@app.get("/api/v1/conversations")
def inbox(status_filter: str | None = None, channel: str | None=None, bot_id: str|None=None, assigned_to:str|None=None, team_id:str|None=None, priority:str|None=None, q:str|None=None, page:int=1, limit: int = 50, user: User=Depends(current_user), session: Session=Depends(db)):
    base=select(Conversation).where(Conversation.company_id == user.company_id)
    statement=base.order_by(Conversation.last_message_at.desc().nullslast(),Conversation.updated_at.desc()).offset((max(page,1)-1)*min(limit,100)).limit(min(limit,100))
    if status_filter: statement=statement.where(Conversation.status == status_filter)
    if channel: statement=statement.where(Conversation.channel==channel)
    if bot_id: statement=statement.where(Conversation.bot_id==bot_id)
    if assigned_to: statement=statement.where(Conversation.assigned_to==assigned_to)
    if team_id: statement=statement.where(Conversation.assigned_team_id==team_id)
    if priority: statement=statement.where(Conversation.priority==priority)
    if q: statement=statement.where(or_(Conversation.subject.ilike(f"%{q[:100]}%")))
    items=session.scalars(statement).all()
    return {"items":[{"id":item.id,"channel":item.channel,"bot_id":item.bot_id,"subject":item.subject,"status":item.status,"priority":item.priority,"assigned_to":item.assigned_to,"assigned_team_id":item.assigned_team_id,"automation_paused":item.automation_paused,"unread_count":item.unread_count,"last_message_at":item.last_message_at} for item in items],"page":max(page,1),"limit":min(limit,100)}

@app.get("/api/v1/conversation-options")
def conversation_options(user:User=Depends(current_user),session:Session=Depends(db)):
    users=session.scalars(select(User).where(User.company_id==user.company_id,User.active.is_(True)).order_by(User.name).limit(200)).all()
    teams=session.scalars(select(Team).where(Team.company_id==user.company_id,Team.active.is_(True)).order_by(Team.name).limit(200)).all()
    customers=session.scalars(select(Customer).where(Customer.company_id==user.company_id).order_by(Customer.name).limit(200)).all()
    equipment=session.scalars(select(Equipment).where(Equipment.company_id==user.company_id).order_by(Equipment.category,Equipment.model).limit(200)).all()
    orders=session.scalars(select(ServiceOrder).where(ServiceOrder.company_id==user.company_id).order_by(ServiceOrder.number.desc()).limit(200)).all()
    return {"users":[{"id":item.id,"label":item.name} for item in users],"teams":[{"id":item.id,"label":item.name} for item in teams],"customers":[{"id":item.id,"label":item.name} for item in customers],"equipment":[{"id":item.id,"label":" · ".join(filter(None,[item.category,item.manufacturer,item.model,item.serial_number]))} for item in equipment],"service_orders":[{"id":item.id,"label":f"OS {item.number} · {item.title}"} for item in orders]}

@app.get("/api/v1/conversations/{conversation_id}")
def conversation_detail(conversation_id:str,user:User=Depends(current_user),session:Session=Depends(db)):
    item=session.scalar(select(Conversation).where(Conversation.id==conversation_id,Conversation.company_id==user.company_id))
    if not item: raise HTTPException(404,"conversation not found")
    messages=session.scalars(select(ConversationMessage).where(ConversationMessage.conversation_id==item.id).order_by(ConversationMessage.created_at)).all()
    attachments=session.scalars(select(Attachment).where(Attachment.conversation_id==item.id,Attachment.deleted_at.is_(None))).all(); by_message={}
    for attachment in attachments: by_message.setdefault(attachment.message_id,[]).append({"id":attachment.id,"filename":attachment.original_filename or attachment.safe_filename,"mime_type":attachment.detected_mime_type,"size_bytes":attachment.size_bytes})
    item.unread_count=0; session.commit()
    return {"id":item.id,"subject":item.subject,"channel":item.channel,"bot_id":item.bot_id,"status":item.status,"priority":item.priority,"assigned_to":item.assigned_to,"assigned_team_id":item.assigned_team_id,"automation_paused":item.automation_paused,"customer_id":item.customer_id,"equipment_id":item.equipment_id,"service_order_id":item.service_order_id,"updated_at":item.updated_at,"messages":[{"id":m.id,"direction":m.direction,"type":m.message_type,"status":m.status,"author_name":m.author_name,"text":m.body,"internal":m.internal,"attempts":session.scalar(select(func.max(OutboxEvent.attempts)).where(OutboxEvent.message_id==m.id)) or 0,"created_at":m.created_at,"sent_at":m.sent_at,"failed_at":m.failed_at,"attachments":by_message.get(m.id,[])} for m in messages]}

@app.post("/api/v1/conversations/{conversation_id}/state")
def change_conversation_state(conversation_id:str,payload:ConversationStateIn,user:User=Depends(current_user),session:Session=Depends(db)):
    item=session.scalar(select(Conversation).where(Conversation.id==conversation_id,Conversation.company_id==user.company_id))
    if not item: raise HTTPException(404,"conversation not found")
    if payload.assigned_user_id and not session.scalar(select(User).where(User.id==payload.assigned_user_id,User.company_id==user.company_id,User.active.is_(True))): raise HTTPException(422,"invalid assignee")
    if payload.assigned_team_id and not session.scalar(select(Team).where(Team.id==payload.assigned_team_id,Team.company_id==user.company_id,Team.active.is_(True))): raise HTTPException(422,"invalid team")
    old=item.status; item.status=payload.status
    if payload.status=="assigned": item.assigned_to=payload.assigned_user_id or user.id
    elif payload.assigned_user_id is not None: item.assigned_to=payload.assigned_user_id
    elif payload.status in {"new","queued"}: item.assigned_to=None
    item.assigned_team_id=payload.assigned_team_id; item.automation_paused=payload.status in {"assigned","waiting_internal"}; item.closed_at=utcnow() if payload.status=="closed" else None
    audit(session,user,"conversation_state_changed","conversation",item.id,{"from":old,"to":item.status,"assigned_user_id":item.assigned_to,"assigned_team_id":item.assigned_team_id}); session.commit(); return {"id":item.id,"status":item.status,"assigned_to":item.assigned_to,"assigned_team_id":item.assigned_team_id}

@app.post("/api/v1/conversations/{conversation_id}/automation/{action}")
def conversation_automation(conversation_id:str,action:str,user:User=Depends(current_user),session:Session=Depends(db)):
    if action not in {"pause","resume"}: raise HTTPException(422,"invalid action")
    item=session.scalar(select(Conversation).where(Conversation.id==conversation_id,Conversation.company_id==user.company_id))
    if not item: raise HTTPException(404,"conversation not found")
    item.automation_paused=action=="pause"; audit(session,user,f"conversation_automation_{action}","conversation",item.id); session.commit(); return {"automation_paused":item.automation_paused}

@app.post("/api/v1/conversations/{conversation_id}/links")
def link_conversation(conversation_id:str,payload:LinkConversationIn,user:User=Depends(current_user),session:Session=Depends(db)):
    item=session.scalar(select(Conversation).where(Conversation.id==conversation_id,Conversation.company_id==user.company_id))
    if not item: raise HTTPException(404,"conversation not found")
    if payload.customer_id and not session.scalar(select(Customer).where(Customer.id==payload.customer_id,Customer.company_id==user.company_id)): raise HTTPException(422,"invalid customer")
    if payload.equipment_id and not session.scalar(select(Equipment).where(Equipment.id==payload.equipment_id,Equipment.company_id==user.company_id)): raise HTTPException(422,"invalid equipment")
    if payload.service_order_id and not session.scalar(select(ServiceOrder).where(ServiceOrder.id==payload.service_order_id,ServiceOrder.company_id==user.company_id)): raise HTTPException(422,"invalid service order")
    item.customer_id=payload.customer_id; item.equipment_id=payload.equipment_id; item.service_order_id=payload.service_order_id
    for attachment in session.scalars(select(Attachment).where(Attachment.conversation_id==item.id)).all(): attachment.customer_id=payload.customer_id; attachment.equipment_id=payload.equipment_id; attachment.service_order_id=payload.service_order_id
    audit(session,user,"conversation_linked","conversation",item.id,payload.model_dump()); session.commit(); return {"ok":True}

@app.post("/api/v1/conversations/{conversation_id}/attachments",status_code=201)
async def upload_conversation_attachment(conversation_id:str,file:UploadFile=File(...),caption:str|None=Form(None),user:User=Depends(current_user),session:Session=Depends(db)):
    item=session.scalar(select(Conversation).where(Conversation.id==conversation_id,Conversation.company_id==user.company_id))
    if not item: raise HTTPException(404,"conversation not found")
    channel=session.get(Channel,item.channel_id) if item.channel_id else None
    if not channel: raise HTTPException(409,"active channel not configured")
    cfg=settings(); data=await file.read(cfg.max_upload_bytes+1)
    try: stored=LocalStorage(cfg.storage_root).store(data,max_bytes=cfg.max_upload_bytes)
    except ValueError as exc: raise HTTPException(422,str(exc)) from exc
    message,outbox,_=queue_outbound_message(session,conversation=item,channel=channel,author_name=user.name,body=caption or file.filename or "Anexo",idempotency_key=f"upload:{item.id}:{stored.sha256}:{secrets.token_hex(8)}",bot_id=item.bot_id)
    message.message_type="document"; outbox.event_type="send_attachment"
    attachment=Attachment(company_id=user.company_id,message_id=message.id,conversation_id=item.id,customer_id=item.customer_id,storage_key=stored.key,original_filename=(file.filename or "attachment")[:255],safe_filename=stored.safe_filename,declared_mime_type=file.content_type,detected_mime_type=stored.detected_mime,size_bytes=stored.size,sha256=stored.sha256,status="available")
    session.add(attachment); session.flush(); outbox.payload={"attachment_id":attachment.id,"caption":caption,"external_chat_id":item.subject}; audit(session,user,"attachment_uploaded","attachment",attachment.id,{"size_bytes":stored.size,"mime":stored.detected_mime}); session.commit(); return {"id":attachment.id,"message_id":message.id,"outbox_event_id":outbox.id}

@app.get("/api/v1/attachments/{attachment_id}/download")
def download_attachment(attachment_id:str,user:User=Depends(current_user),session:Session=Depends(db)):
    item=session.scalar(select(Attachment).where(Attachment.id==attachment_id,Attachment.company_id==user.company_id,Attachment.deleted_at.is_(None)))
    if not item: raise HTTPException(404,"attachment not found")
    try: data=LocalStorage(settings().storage_root).read(item.storage_key)
    except (ValueError,FileNotFoundError) as exc: raise HTTPException(404,"attachment content not found") from exc
    audit(session,user,"attachment_downloaded","attachment",item.id,{"size_bytes":item.size_bytes}); session.commit(); return Response(content=data,media_type=item.detected_mime_type,headers={"Content-Disposition":f'attachment; filename="{item.safe_filename}"',"X-Content-Type-Options":"nosniff"})

@app.delete("/api/v1/attachments/{attachment_id}")
def delete_attachment(attachment_id:str,user:User=Depends(current_user),session:Session=Depends(db)):
    item=session.scalar(select(Attachment).where(Attachment.id==attachment_id,Attachment.company_id==user.company_id,Attachment.deleted_at.is_(None)))
    if not item: raise HTTPException(404,"attachment not found")
    item.deleted_at=utcnow();item.status="deleted";audit(session,user,"attachment_soft_deleted","attachment",item.id);session.commit();return {"ok":True}

@app.get("/api/v1/outbox")
def list_outbox(status_filter:str|None=None,user:User=Depends(current_user),session:Session=Depends(db)):
    stmt=select(OutboxEvent).where(OutboxEvent.company_id==user.company_id).order_by(OutboxEvent.created_at.desc()).limit(100)
    if status_filter: stmt=stmt.where(OutboxEvent.status==status_filter)
    return {"items":[{"id":x.id,"conversation_id":x.conversation_id,"message_id":x.message_id,"operation":x.event_type,"status":x.status,"attempts":x.attempts,"last_error":x.last_error,"created_at":x.created_at,"sent_at":x.delivered_at} for x in session.scalars(stmt).all()]}

@app.post("/api/v1/outbox/{event_id}/reprocess")
def reprocess_outbox(event_id:str,user:User=Depends(require("telegram.manage")),session:Session=Depends(db)):
    event=session.scalar(select(OutboxEvent).where(OutboxEvent.id==event_id,OutboxEvent.company_id==user.company_id,OutboxEvent.status.in_(["dead_letter","failed"])))
    if not event: raise HTTPException(404,"dead-letter item not found")
    event.status="pending"; event.available_at=utcnow(); event.locked_at=None; event.locked_by=None; event.last_error=None; event.dead_lettered_at=None; audit(session,user,"outbox_reprocessed","outbox_event",event.id); session.commit(); return {"id":event.id,"status":event.status}

@app.get("/api/v1/external-events")
def list_external_events(status_filter:str|None=None,user:User=Depends(require("telegram.manage")),session:Session=Depends(db)):
    stmt=select(ExternalEvent).where(ExternalEvent.company_id==user.company_id).order_by(ExternalEvent.received_at.desc()).limit(100)
    if status_filter:stmt=stmt.where(ExternalEvent.status==status_filter)
    return {"items":[{"id":x.id,"bot_id":x.bot_id,"external_event_id":x.external_event_id,"status":x.status,"attempts":x.attempts,"error":x.error,"received_at":x.received_at,"processed_at":x.processed_at} for x in session.scalars(stmt).all()]}

@app.post("/api/v1/external-events/{event_id}/reprocess")
def reprocess_external_event(event_id:str,user:User=Depends(require("telegram.manage")),session:Session=Depends(db)):
    event=session.scalar(select(ExternalEvent).where(ExternalEvent.id==event_id,ExternalEvent.company_id==user.company_id,ExternalEvent.status.in_(["dead_letter","retry"])))
    if not event:raise HTTPException(404,"inbox event not found")
    event.status="received";event.error=None;event.processed_at=None;audit(session,user,"external_event_reprocessed","external_event",event.id);session.commit();return {"id":event.id,"status":event.status}

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
    item=Role(company_id=user.company_id, code=payload.code, name=payload.name, permissions={"permissions":payload.permissions}); session.add(item); session.flush(); audit(session,user,"create","role",item.id); session.commit(); return {"id":item.id}
@app.post("/api/v1/branches", status_code=201)
def create_branch(payload: BranchIn, user: User=Depends(require("organization.manage")), session: Session=Depends(db)):
    item=Branch(company_id=user.company_id, name=payload.name); session.add(item); session.flush(); audit(session,user,"create","branch",item.id); session.commit(); return {"id":item.id}
@app.post("/api/v1/teams", status_code=201)
def create_team(payload: TeamIn, user: User=Depends(require("organization.manage")), session: Session=Depends(db)):
    if payload.branch_id and not session.scalar(select(Branch).where(Branch.id == payload.branch_id, Branch.company_id == user.company_id)): raise HTTPException(404,"branch not found")
    item=Team(company_id=user.company_id, **payload.model_dump()); session.add(item); session.flush(); audit(session,user,"create","team",item.id); session.commit(); return {"id":item.id}
@app.post("/api/v1/users", status_code=201)
def create_user(payload: UserIn, user: User=Depends(require("organization.manage")), session: Session=Depends(db)):
    if session.scalar(select(User).where(User.email == payload.email.lower())): raise HTTPException(409,"email already exists")
    roles=session.scalars(select(Role).where(Role.id.in_(payload.role_ids), Role.company_id == user.company_id)).all()
    if len(roles) != len(set(payload.role_ids)): raise HTTPException(422,"invalid roles")
    item=User(company_id=user.company_id,name=payload.name,email=payload.email.lower(),password_hash=pwd.hash(payload.password)); session.add(item); session.flush()
    for role in roles: session.add(UserRole(user_id=item.id,role_id=role.id))
    audit(session,user,"create","user",item.id); session.commit(); return {"id":item.id}
