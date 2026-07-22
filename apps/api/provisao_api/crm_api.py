"""Tenant-scoped CRM API used by the conversation and service-order flows."""
import re
from typing import Callable
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
from .db import SessionLocal
from .models import Customer, CustomerAddress, CustomerContact, CustomerMergeRequest, User

def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

def digits(value: str | None) -> str | None:
    normalized = re.sub(r"\D", "", value or "")
    return normalized or None

def email(value: str | None) -> str | None:
    return value.strip().lower() if value and value.strip() else None

class CustomerPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=2, max_length=160)
    customer_type: str = Field(default="individual", pattern="^(individual|company)$")
    document: str | None = Field(default=None, max_length=32)
    legal_name: str | None = Field(default=None, max_length=200)
    trade_name: str | None = Field(default=None, max_length=200)
    state_registration: str | None = Field(default=None, max_length=40)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=32)
    whatsapp: str | None = Field(default=None, max_length=32)
    notes: str | None = Field(default=None, max_length=5000)
    status: str = Field(default="active", pattern="^(active|inactive|blocked)$")
    tags: list[str] = Field(default_factory=list, max_length=30)
    source: str | None = Field(default=None, max_length=80)

class ContactPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=2, max_length=160)
    job_title: str | None = Field(default=None, max_length=100)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=32)
    whatsapp: str | None = Field(default=None, max_length=32)
    preferred_channel: str = Field(default="telegram", pattern="^(telegram|web|email|phone)$")
    is_primary: bool = False
    receives_notifications: bool = True
    active: bool = True
    notes: str | None = Field(default=None, max_length=3000)

class AddressPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    address_type: str = Field(default="service", pattern="^(billing|service|shipping|other)$")
    postal_code: str | None = Field(default=None, max_length=12)
    street: str = Field(min_length=2, max_length=200)
    number: str | None = Field(default=None, max_length=30)
    complement: str | None = Field(default=None, max_length=120)
    district: str | None = Field(default=None, max_length=120)
    city: str = Field(min_length=2, max_length=120)
    state: str = Field(min_length=2, max_length=2)
    country: str = Field(default="BR", min_length=2, max_length=2)
    reference: str | None = Field(default=None, max_length=300)
    latitude: str | None = Field(default=None, max_length=32)
    longitude: str | None = Field(default=None, max_length=32)
    is_primary: bool = False
    active: bool = True

class MergePayload(BaseModel):
    target_customer_id: str
    reason: str = Field(min_length=10, max_length=2000)

def customer_view(item: Customer) -> dict:
    return {"id": item.id, "name": item.name, "customer_type": item.customer_type, "document": item.document, "legal_name": item.legal_name, "trade_name": item.trade_name, "state_registration": item.state_registration, "email": item.email, "phone": item.phone, "whatsapp": item.whatsapp, "notes": item.notes, "status": item.status, "tags": item.tags or [], "source": item.source, "created_at": item.created_at, "updated_at": item.updated_at}

def build_router(current_user: Callable, require: Callable, audit: Callable) -> APIRouter:
    router = APIRouter(prefix="/api/v1/crm", tags=["crm"])
    def owned(session: Session, user: User, customer_id: str) -> Customer:
        item = session.scalar(select(Customer).where(Customer.id == customer_id, Customer.company_id == user.company_id))
        if not item: raise HTTPException(404, "customer not found")
        return item
    @router.get("/customers")
    def customers(q: str | None = None, status: str | None = None, customer_type: str | None = None, page: int = Query(1, ge=1), limit: int = Query(50, ge=1, le=100), user: User = Depends(current_user), session: Session = Depends(db)):
        statement = select(Customer).where(Customer.company_id == user.company_id).order_by(Customer.updated_at.desc()).offset((page - 1) * limit).limit(limit)
        if q: statement = statement.where(or_(Customer.name.ilike(f"%{q[:100]}%"), Customer.normalized_document == digits(q), Customer.normalized_email == email(q), Customer.normalized_phone == digits(q)))
        if status: statement = statement.where(Customer.status == status)
        if customer_type: statement = statement.where(Customer.customer_type == customer_type)
        items = session.scalars(statement).all()
        return {"items": [customer_view(item) for item in items], "page": page, "limit": limit, "has_more": len(items) == limit}
    @router.post("/customers", status_code=201)
    def create_customer(payload: CustomerPayload, user: User = Depends(require("crm.create")), session: Session = Depends(db)):
        normalized_document, normalized_email, normalized_phone = digits(payload.document), email(str(payload.email) if payload.email else None), digits(payload.phone)
        duplicate = session.scalar(select(Customer).where(Customer.company_id == user.company_id, or_(normalized_document and Customer.normalized_document == normalized_document, normalized_email and Customer.normalized_email == normalized_email, normalized_phone and Customer.normalized_phone == normalized_phone))) if any((normalized_document, normalized_email, normalized_phone)) else None
        if duplicate: raise HTTPException(409, detail={"message": "possible duplicate customer", "customer_id": duplicate.id})
        item = Customer(company_id=user.company_id, normalized_document=normalized_document, normalized_email=normalized_email, normalized_phone=normalized_phone, **payload.model_dump()); session.add(item); session.flush(); audit(session, user, "crm_customer_created", "customer", item.id); session.commit(); return customer_view(item)
    @router.get("/customers/{customer_id}")
    def get_customer(customer_id: str, user: User = Depends(current_user), session: Session = Depends(db)):
        item = owned(session, user, customer_id); contacts = session.scalars(select(CustomerContact).where(CustomerContact.customer_id == item.id).order_by(CustomerContact.is_primary.desc(), CustomerContact.name)).all(); addresses = session.scalars(select(CustomerAddress).where(CustomerAddress.customer_id == item.id).order_by(CustomerAddress.is_primary.desc(), CustomerAddress.street)).all()
        return {**customer_view(item), "contacts": [contact_view(x) for x in contacts], "addresses": [address_view(x) for x in addresses]}
    @router.patch("/customers/{customer_id}")
    def update_customer(customer_id: str, payload: CustomerPayload, user: User = Depends(require("crm.update")), session: Session = Depends(db)):
        item = owned(session, user, customer_id); data = payload.model_dump(); item.normalized_document, item.normalized_email, item.normalized_phone = digits(payload.document), email(str(payload.email) if payload.email else None), digits(payload.phone)
        for key, value in data.items(): setattr(item, key, value)
        audit(session, user, "crm_customer_updated", "customer", item.id); session.commit(); return customer_view(item)
    @router.post("/customers/{customer_id}/merge-requests", status_code=201)
    def merge_request(customer_id: str, payload: MergePayload, user: User = Depends(require("crm.merge_request")), session: Session = Depends(db)):
        source = owned(session, user, customer_id); target = owned(session, user, payload.target_customer_id)
        if source.id == target.id: raise HTTPException(422, "source and target must differ")
        item = CustomerMergeRequest(company_id=user.company_id, source_customer_id=source.id, target_customer_id=target.id, reason=payload.reason, requested_by=user.id); session.add(item); session.flush(); audit(session, user, "crm_merge_requested", "customer_merge_request", item.id, {"source": source.id, "target": target.id}); session.commit(); return {"id": item.id, "status": item.status}
    @router.post("/customers/{customer_id}/contacts", status_code=201)
    def create_contact(customer_id: str, payload: ContactPayload, user: User = Depends(require("crm.update")), session: Session = Depends(db)):
        customer = owned(session, user, customer_id); item = CustomerContact(company_id=user.company_id, customer_id=customer.id, normalized_email=email(str(payload.email) if payload.email else None), normalized_phone=digits(payload.phone), **payload.model_dump()); session.add(item); session.flush(); audit(session, user, "crm_contact_created", "customer_contact", item.id); session.commit(); return contact_view(item)
    @router.post("/customers/{customer_id}/addresses", status_code=201)
    def create_address(customer_id: str, payload: AddressPayload, user: User = Depends(require("crm.update")), session: Session = Depends(db)):
        customer = owned(session, user, customer_id); item = CustomerAddress(company_id=user.company_id, customer_id=customer.id, **payload.model_dump()); session.add(item); session.flush(); audit(session, user, "crm_address_created", "customer_address", item.id); session.commit(); return address_view(item)
    return router

def contact_view(item: CustomerContact) -> dict:
    return {"id": item.id, "customer_id": item.customer_id, "name": item.name, "job_title": item.job_title, "email": item.email, "phone": item.phone, "whatsapp": item.whatsapp, "preferred_channel": item.preferred_channel, "is_primary": item.is_primary, "receives_notifications": item.receives_notifications, "active": item.active, "notes": item.notes}

def address_view(item: CustomerAddress) -> dict:
    return {"id": item.id, "customer_id": item.customer_id, "address_type": item.address_type, "postal_code": item.postal_code, "street": item.street, "number": item.number, "complement": item.complement, "district": item.district, "city": item.city, "state": item.state, "country": item.country, "reference": item.reference, "latitude": item.latitude, "longitude": item.longitude, "is_primary": item.is_primary, "active": item.active}
