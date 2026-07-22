"""Completion, field service, delivery and warranty operations."""
from datetime import UTC, datetime, timedelta
from typing import Callable
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from .db import SessionLocal
from .models import (Channel, Conversation, ServiceOrder, ServiceOrderDelivery, ServiceOrderEvent, ServiceOrderSequence, ServiceOrderWorkSession, ServiceVisit, User, Warranty, WarrantyReturn)
from .services.conversations import queue_outbound_message

def db():
    session=SessionLocal()
    try: yield session
    finally: session.close()

class WorkPayload(BaseModel):
    model_config=ConfigDict(extra="forbid")
    mode: str=Field(pattern="^(bench|remote|field)$"); notes: str|None=None
class WorkStatePayload(BaseModel):
    status: str=Field(pattern="^(paused|completed|cancelled)$"); result: str|None=None
class VisitPayload(BaseModel):
    address: str=Field(min_length=3,max_length=2000); scheduled_start: datetime; scheduled_end: datetime|None=None; technician_id: str|None=None; notes: str|None=None
class VisitStatePayload(BaseModel):
    status: str=Field(pattern="^(confirmed|en_route|on_site|completed|cancelled|no_show|rescheduled)$"); result: str|None=None
class DeliveryPayload(BaseModel):
    mode: str=Field(pattern="^(delivery|pickup)$"); condition: str|None=None; accessories: dict={}; notes: str|None=None
class WarrantyPayload(BaseModel):
    starts_at: datetime; ends_at: datetime; coverage: str|None=None; exclusions: str|None=None
class ReturnPayload(BaseModel):
    reason: str=Field(min_length=3,max_length=3000)

def build_router(current_user:Callable,require:Callable,audit:Callable)->APIRouter:
    router=APIRouter(prefix="/api/v1/service-orders",tags=["completion"])
    def owned(session,user,id):
        item=session.scalar(select(ServiceOrder).where(ServiceOrder.id==id,ServiceOrder.company_id==user.company_id))
        if not item: raise HTTPException(404,"service order not found")
        return item
    def public_notify(session, order, body):
        if not order.conversation_id: return
        conversation=session.scalar(select(Conversation).where(Conversation.id==order.conversation_id,Conversation.company_id==order.company_id))
        channel=session.get(Channel, conversation.channel_id) if conversation else None
        if conversation and channel and channel.kind=="telegram":
            queue_outbound_message(session, conversation=conversation, channel=channel, author_name="Provisão", body=body, idempotency_key=f"os-public:{order.id}:{body[:40]}", bot_id=conversation.bot_id)
    def view(x): return {"id":x.id,"service_order_id":x.service_order_id,"mode":x.mode,"technician_id":x.technician_id,"status":x.status,"started_at":x.started_at,"paused_at":x.paused_at,"ended_at":x.ended_at,"result":x.result,"notes":x.notes}
    @router.post("/{order_id}/work-sessions",status_code=201)
    def start(order_id:str,payload:WorkPayload,user:User=Depends(require("bench_service.manage")),session:Session=Depends(db)):
        order=owned(session,user,order_id)
        active=session.scalar(select(ServiceOrderWorkSession).where(ServiceOrderWorkSession.service_order_id==order.id,ServiceOrderWorkSession.status.in_(["active","paused"])))
        if active: raise HTTPException(409,"an active work session already exists")
        item=ServiceOrderWorkSession(company_id=user.company_id,service_order_id=order.id,technician_id=user.id,**payload.model_dump());session.add(item);session.flush();session.add(ServiceOrderEvent(service_order_id=order.id,actor_id=user.id,event_type="work_started",detail=payload.mode));audit(session,user,"service_order_work_started","service_order_work_session",item.id);session.commit();return view(item)
    @router.patch("/{order_id}/work-sessions/{session_id}")
    def state(order_id:str,session_id:str,payload:WorkStatePayload,user:User=Depends(require("bench_service.manage")),session:Session=Depends(db)):
        order=owned(session,user,order_id); item=session.scalar(select(ServiceOrderWorkSession).where(ServiceOrderWorkSession.id==session_id,ServiceOrderWorkSession.service_order_id==order.id,ServiceOrderWorkSession.company_id==user.company_id))
        if not item: raise HTTPException(404,"work session not found")
        item.status=payload.status;item.result=payload.result or item.result;item.paused_at=datetime.now(UTC) if payload.status=="paused" else item.paused_at;item.ended_at=datetime.now(UTC) if payload.status in {"completed","cancelled"} else None;session.add(ServiceOrderEvent(service_order_id=order.id,actor_id=user.id,event_type="work_updated",detail=f"{item.mode}:{item.status}"));audit(session,user,"service_order_work_updated","service_order_work_session",item.id);session.commit();return view(item)
    @router.post("/{order_id}/visits",status_code=201)
    def create_visit(order_id:str,payload:VisitPayload,user:User=Depends(require("field_service.manage")),session:Session=Depends(db)):
        order=owned(session,user,order_id); item=ServiceVisit(company_id=user.company_id,service_order_id=order.id,**payload.model_dump());session.add(item);session.flush();session.add(ServiceOrderEvent(service_order_id=order.id,actor_id=user.id,event_type="visit_scheduled",detail=payload.address));audit(session,user,"service_visit_created","service_visit",item.id);session.commit();return {"id":item.id,"service_order_id":item.service_order_id,"status":item.status,"scheduled_start":item.scheduled_start,"scheduled_end":item.scheduled_end,"address":item.address,"technician_id":item.technician_id}
    @router.patch("/{order_id}/visits/{visit_id}")
    def update_visit(order_id:str,visit_id:str,payload:VisitStatePayload,user:User=Depends(require("field_service.manage")),session:Session=Depends(db)):
        order=owned(session,user,order_id); item=session.scalar(select(ServiceVisit).where(ServiceVisit.id==visit_id,ServiceVisit.service_order_id==order.id,ServiceVisit.company_id==user.company_id))
        if not item: raise HTTPException(404,"visit not found")
        item.status=payload.status;item.result=payload.result or item.result;session.add(ServiceOrderEvent(service_order_id=order.id,actor_id=user.id,event_type="visit_updated",detail=item.status));audit(session,user,"service_visit_updated","service_visit",item.id);session.commit();return {"id":item.id,"status":item.status,"result":item.result}
    @router.post("/{order_id}/delivery",status_code=201)
    def deliver(order_id:str,payload:DeliveryPayload,user:User=Depends(require("service_order.close")),session:Session=Depends(db)):
        order=owned(session,user,order_id)
        if order.status not in {"completed","resolved","diagnosis","triage","draft"}: raise HTTPException(409,"service order cannot be delivered")
        if session.scalar(select(ServiceOrderDelivery).where(ServiceOrderDelivery.service_order_id==order.id)): raise HTTPException(409,"service order already delivered")
        item=ServiceOrderDelivery(company_id=user.company_id,service_order_id=order.id,performed_by=user.id,**payload.model_dump());order.status="closed";order.completed_at=datetime.now(UTC);session.add(item);session.flush();session.add(ServiceOrderEvent(service_order_id=order.id,actor_id=user.id,event_type="delivered",detail=payload.mode));public_notify(session,order,f"OS {order.number} concluída. Equipamento disponível para {payload.mode}.");audit(session,user,"service_order_delivered","service_order_delivery",item.id);session.commit();return {"id":item.id,"mode":item.mode,"status":order.status,"delivered_at":item.delivered_at}
    @router.post("/{order_id}/warranty",status_code=201)
    def warranty(order_id:str,payload:WarrantyPayload,user:User=Depends(require("warranty.manage")),session:Session=Depends(db)):
        order=owned(session,user,order_id)
        if payload.ends_at<=payload.starts_at: raise HTTPException(422,"warranty end must be after start")
        if session.scalar(select(Warranty).where(Warranty.service_order_id==order.id)): raise HTTPException(409,"warranty already exists")
        item=Warranty(company_id=user.company_id,service_order_id=order.id,created_by=user.id,**payload.model_dump());session.add(item);session.flush();session.add(ServiceOrderEvent(service_order_id=order.id,actor_id=user.id,event_type="warranty_created",detail="warranty registered"));public_notify(session,order,f"A garantia da OS {order.number} foi registrada.");audit(session,user,"warranty_created","warranty",item.id);session.commit();return {"id":item.id,"service_order_id":item.service_order_id,"starts_at":item.starts_at,"ends_at":item.ends_at,"status":item.status}
    @router.post("/{order_id}/warranty-return",status_code=201)
    def warranty_return(order_id:str,payload:ReturnPayload,user:User=Depends(require("warranty.manage")),session:Session=Depends(db)):
        original=owned(session,user,order_id); now=datetime.now(UTC); active=session.scalar(select(Warranty).where(Warranty.service_order_id==original.id, Warranty.status=="active", Warranty.ends_at>=now))
        if not active: raise HTTPException(422,"no active warranty for service order")
        sequence=session.scalar(select(ServiceOrderSequence).where(ServiceOrderSequence.company_id==user.company_id).with_for_update())
        if not sequence: sequence=ServiceOrderSequence(company_id=user.company_id,next_number=(session.scalar(select(func.max(ServiceOrder.number)).where(ServiceOrder.company_id==user.company_id)) or 0)+1);session.add(sequence);session.flush()
        number=sequence.next_number;sequence.next_number+=1
        order=ServiceOrder(company_id=user.company_id,number=number,customer_id=original.customer_id,contact_id=original.contact_id,equipment_id=original.equipment_id,conversation_id=original.conversation_id,channel_of_origin=original.channel_of_origin,service_type=original.service_type,title=f"Retorno em garantia: {original.title}",symptom=payload.reason,priority=original.priority,status="draft",received_at=now,sla_policy=original.sla_policy,sla_due_at=now+timedelta(minutes=2880));session.add(order);session.flush();link=WarrantyReturn(company_id=user.company_id,original_service_order_id=original.id,return_service_order_id=order.id,reason=payload.reason,created_by=user.id);session.add(link);session.add(ServiceOrderEvent(service_order_id=order.id,actor_id=user.id,event_type="warranty_return_opened",detail=f"original:{original.number}"));public_notify(session,original,f"Foi aberto o retorno em garantia da OS {original.number}.");audit(session,user,"warranty_return_opened","warranty_return",link.id,{"original_service_order_id":original.id});session.commit();return {"id":order.id,"number":order.number,"original_service_order_id":original.id,"warranty_return_id":link.id}
    return router
