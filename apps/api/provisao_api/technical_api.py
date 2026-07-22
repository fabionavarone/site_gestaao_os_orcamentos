"""Technical records for service orders: diagnosis, tests, measurements and checklists."""
from datetime import UTC, datetime
from typing import Callable

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .db import SessionLocal
from .models import (
    ChecklistTemplate,
    ServiceOrder,
    ServiceOrderChecklist,
    ServiceOrderDiagnosis,
    ServiceOrderEvent,
    ServiceOrderMeasurement,
    ServiceOrderTechnicalTest,
    User,
)


def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


class DiagnosisPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: str = Field(min_length=3, max_length=5000)
    details: str | None = Field(default=None, max_length=10000)
    risk: str | None = Field(default=None, max_length=40)
    repairable: bool | None = None
    recommendation: str | None = Field(default=None, max_length=5000)


class ReviewPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str | None = Field(default=None, max_length=2000)


class MeasurementPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    parameter: str = Field(min_length=1, max_length=120)
    value: str = Field(min_length=1, max_length=120)
    unit: str | None = Field(default=None, max_length=40)
    instrument: str | None = Field(default=None, max_length=120)
    condition: str | None = Field(default=None, max_length=200)
    result: str | None = Field(default=None, max_length=40)


class TechnicalTestPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=2, max_length=160)
    procedure: str | None = Field(default=None, max_length=5000)
    result: str | None = Field(default=None, max_length=5000)
    status: str = Field(default="inconclusive", pattern="^(passed|failed|inconclusive)$")
    observation: str | None = Field(default=None, max_length=5000)


class ChecklistTemplatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=2, max_length=160)
    purpose: str | None = Field(default=None, max_length=120)
    items: list[dict] = Field(default_factory=list, max_length=200)


class ChecklistUpdatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[dict] = Field(max_length=200)


def build_router(current_user: Callable, require: Callable, audit: Callable) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["technical-records"])

    def owned_order(session: Session, user: User, order_id: str) -> ServiceOrder:
        item = session.scalar(select(ServiceOrder).where(ServiceOrder.id == order_id, ServiceOrder.company_id == user.company_id))
        if not item:
            raise HTTPException(404, "service order not found")
        return item

    def diagnosis_view(item: ServiceOrderDiagnosis) -> dict:
        return {"id": item.id, "service_order_id": item.service_order_id, "version": item.version,
                "summary": item.summary, "details": item.details, "risk": item.risk,
                "repairable": item.repairable, "recommendation": item.recommendation,
                "status": item.status, "technician_id": item.technician_id,
                "reviewer_id": item.reviewer_id, "reviewed_at": item.reviewed_at,
                "created_at": item.created_at}

    def template_view(item: ChecklistTemplate) -> dict:
        return {"id": item.id, "name": item.name, "purpose": item.purpose,
                "status": item.status, "version": item.version, "items": item.items or [],
                "created_by": item.created_by, "created_at": item.created_at}

    @router.post("/service-orders/{order_id}/diagnoses", status_code=201)
    def create_diagnosis(order_id: str, payload: DiagnosisPayload,
                         user: User = Depends(require("diagnosis.create")), session: Session = Depends(db)):
        order = owned_order(session, user, order_id)
        latest = session.scalar(select(func.max(ServiceOrderDiagnosis.version)).where(ServiceOrderDiagnosis.service_order_id == order.id)) or 0
        # Approved records are immutable; a correction always supersedes the previous version.
        approved = session.scalar(select(ServiceOrderDiagnosis).where(ServiceOrderDiagnosis.service_order_id == order.id, ServiceOrderDiagnosis.status == "approved").order_by(ServiceOrderDiagnosis.version.desc()))
        if approved:
            approved.status = "superseded"
        item = ServiceOrderDiagnosis(company_id=user.company_id, service_order_id=order.id, version=latest + 1,
                                     technician_id=user.id, **payload.model_dump())
        session.add(item); session.flush()
        session.add(ServiceOrderEvent(service_order_id=order.id, actor_id=user.id, event_type="diagnosis_created", detail=f"diagnosis v{item.version} created"))
        audit(session, user, "service_order_diagnosis_created", "service_order_diagnosis", item.id, {"version": item.version})
        session.commit()
        return diagnosis_view(item)

    @router.get("/service-orders/{order_id}/diagnoses")
    def list_diagnoses(order_id: str, user: User = Depends(current_user), session: Session = Depends(db)):
        order = owned_order(session, user, order_id)
        return {"items": [diagnosis_view(x) for x in session.scalars(select(ServiceOrderDiagnosis).where(ServiceOrderDiagnosis.service_order_id == order.id).order_by(ServiceOrderDiagnosis.version.desc())).all()]}

    @router.post("/service-orders/{order_id}/diagnoses/{diagnosis_id}/submit-review")
    def submit_review(order_id: str, diagnosis_id: str, payload: ReviewPayload,
                      user: User = Depends(require("diagnosis.review")), session: Session = Depends(db)):
        order = owned_order(session, user, order_id)
        item = session.scalar(select(ServiceOrderDiagnosis).where(ServiceOrderDiagnosis.id == diagnosis_id, ServiceOrderDiagnosis.service_order_id == order.id, ServiceOrderDiagnosis.company_id == user.company_id))
        if not item: raise HTTPException(404, "diagnosis not found")
        if item.status != "draft": raise HTTPException(409, "only draft diagnoses can be submitted")
        item.status = "under_review"; item.reviewer_id = user.id; item.reviewed_at = datetime.now(UTC)
        session.add(ServiceOrderEvent(service_order_id=order.id, actor_id=user.id, event_type="diagnosis_submitted", detail=payload.reason or "diagnosis submitted for review"))
        audit(session, user, "service_order_diagnosis_submitted", "service_order_diagnosis", item.id)
        session.commit(); return diagnosis_view(item)

    @router.post("/service-orders/{order_id}/diagnoses/{diagnosis_id}/approve")
    def approve_diagnosis(order_id: str, diagnosis_id: str, payload: ReviewPayload,
                          user: User = Depends(require("diagnosis.approve")), session: Session = Depends(db)):
        order = owned_order(session, user, order_id)
        item = session.scalar(select(ServiceOrderDiagnosis).where(ServiceOrderDiagnosis.id == diagnosis_id, ServiceOrderDiagnosis.service_order_id == order.id, ServiceOrderDiagnosis.company_id == user.company_id))
        if not item: raise HTTPException(404, "diagnosis not found")
        if item.status != "under_review": raise HTTPException(409, "diagnosis must be under review")
        item.status = "approved"; item.reviewer_id = user.id; item.reviewed_at = datetime.now(UTC)
        session.add(ServiceOrderEvent(service_order_id=order.id, actor_id=user.id, event_type="diagnosis_approved", detail=payload.reason or "diagnosis approved"))
        audit(session, user, "service_order_diagnosis_approved", "service_order_diagnosis", item.id)
        session.commit(); return diagnosis_view(item)

    @router.post("/service-orders/{order_id}/measurements", status_code=201)
    def create_measurement(order_id: str, payload: MeasurementPayload,
                           user: User = Depends(require("diagnosis.create")), session: Session = Depends(db)):
        order = owned_order(session, user, order_id)
        item = ServiceOrderMeasurement(company_id=user.company_id, service_order_id=order.id, performed_by=user.id, **payload.model_dump())
        session.add(item); session.flush(); session.add(ServiceOrderEvent(service_order_id=order.id, actor_id=user.id, event_type="measurement_recorded", detail=payload.parameter)); audit(session, user, "service_order_measurement_created", "service_order_measurement", item.id); session.commit()
        return {"id": item.id, **payload.model_dump(), "performed_by": item.performed_by, "created_at": item.created_at}

    @router.post("/service-orders/{order_id}/technical-tests", status_code=201)
    def create_test(order_id: str, payload: TechnicalTestPayload,
                    user: User = Depends(require("diagnosis.create")), session: Session = Depends(db)):
        order = owned_order(session, user, order_id)
        item = ServiceOrderTechnicalTest(company_id=user.company_id, service_order_id=order.id, performed_by=user.id, **payload.model_dump())
        session.add(item); session.flush(); session.add(ServiceOrderEvent(service_order_id=order.id, actor_id=user.id, event_type="technical_test_recorded", detail=payload.name)); audit(session, user, "service_order_technical_test_created", "service_order_technical_test", item.id); session.commit()
        return {"id": item.id, **payload.model_dump(), "performed_by": item.performed_by, "created_at": item.created_at}

    @router.get("/checklist-templates")
    def list_templates(user: User = Depends(current_user), session: Session = Depends(db)):
        return {"items": [template_view(x) for x in session.scalars(select(ChecklistTemplate).where(ChecklistTemplate.company_id == user.company_id).order_by(ChecklistTemplate.name)).all()]}

    @router.post("/checklist-templates", status_code=201)
    def create_template(payload: ChecklistTemplatePayload, user: User = Depends(require("checklist.manage")), session: Session = Depends(db)):
        item = ChecklistTemplate(company_id=user.company_id, created_by=user.id, **payload.model_dump())
        session.add(item); session.flush(); audit(session, user, "checklist_template_created", "checklist_template", item.id); session.commit(); return template_view(item)

    @router.post("/checklist-templates/{template_id}/publish")
    def publish_template(template_id: str, user: User = Depends(require("checklist.manage")), session: Session = Depends(db)):
        item = session.scalar(select(ChecklistTemplate).where(ChecklistTemplate.id == template_id, ChecklistTemplate.company_id == user.company_id))
        if not item: raise HTTPException(404, "checklist template not found")
        if item.status == "published": raise HTTPException(409, "published checklist templates are immutable")
        if not item.items: raise HTTPException(422, "checklist must contain at least one item")
        for entry in item.items:
            if not isinstance(entry, dict) or not entry.get("code") or not entry.get("label"):
                raise HTTPException(422, "checklist items require code and label")
        item.status = "published"; audit(session, user, "checklist_template_published", "checklist_template", item.id); session.commit(); return template_view(item)

    @router.post("/service-orders/{order_id}/checklists", status_code=201)
    def assign_checklist(order_id: str, template_id: str = Query(...),
                         user: User = Depends(require("checklist.manage")), session: Session = Depends(db)):
        order = owned_order(session, user, order_id)
        template = session.scalar(select(ChecklistTemplate).where(ChecklistTemplate.id == template_id, ChecklistTemplate.company_id == user.company_id, ChecklistTemplate.status == "published"))
        if not template: raise HTTPException(404, "published checklist template not found")
        item = ServiceOrderChecklist(company_id=user.company_id, service_order_id=order.id, template_id=template.id, template_version=template.version, items=[{**entry, "value": entry.get("value")} for entry in template.items], status="pending")
        session.add(item); session.flush(); session.add(ServiceOrderEvent(service_order_id=order.id, actor_id=user.id, event_type="checklist_assigned", detail=template.name)); audit(session, user, "service_order_checklist_assigned", "service_order_checklist", item.id); session.commit()
        return checklist_view(item)

    @router.patch("/service-orders/{order_id}/checklists/{checklist_id}")
    def update_checklist(order_id: str, checklist_id: str, payload: ChecklistUpdatePayload,
                         user: User = Depends(require("checklist.manage")), session: Session = Depends(db)):
        order = owned_order(session, user, order_id)
        item = session.scalar(select(ServiceOrderChecklist).where(ServiceOrderChecklist.id == checklist_id, ServiceOrderChecklist.service_order_id == order.id, ServiceOrderChecklist.company_id == user.company_id))
        if not item: raise HTTPException(404, "checklist not found")
        required = [x for x in item.items if isinstance(x, dict) and x.get("required")]
        submitted = {x.get("code"): x for x in payload.items if isinstance(x, dict)}
        missing = [x.get("code") for x in required if x.get("code") not in submitted or "value" not in submitted[x.get("code")] or submitted[x.get("code")].get("value") in (None, "")]
        item.items = payload.items
        if missing: item.status = "pending"; raise HTTPException(422, detail={"message": "required checklist items incomplete", "items": missing})
        item.status = "completed"; item.completed_by = user.id; item.completed_at = datetime.now(UTC)
        session.add(ServiceOrderEvent(service_order_id=order.id, actor_id=user.id, event_type="checklist_completed", detail=str(item.id))); audit(session, user, "service_order_checklist_completed", "service_order_checklist", item.id); session.commit(); return checklist_view(item)

    return router


def checklist_view(item: ServiceOrderChecklist) -> dict:
    return {"id": item.id, "service_order_id": item.service_order_id, "template_id": item.template_id, "template_version": item.template_version, "items": item.items or [], "status": item.status, "completed_by": item.completed_by, "completed_at": item.completed_at}
