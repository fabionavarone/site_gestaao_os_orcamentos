"""Service-order intake and technical-operation APIs."""
from datetime import UTC, datetime, timedelta
from typing import Callable
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from .db import SessionLocal
from .models import Channel, Conversation, Customer, Equipment, ServiceOrder, ServiceOrderEvent, ServiceOrderSequence, ServiceOrderTask, ServiceOrderTriage, Team, User, WorkflowInstance
from .services.conversations import queue_outbound_message
from .services.workflow import ensure_default_workflow, start_instance

def db():
    session=SessionLocal()
    try: yield session
    finally: session.close()

class IntakePayload(BaseModel):
    customer_id: str; contact_id: str|None=None; equipment_id: str|None=None; conversation_id: str|None=None; title: str=Field(min_length=3,max_length=240); symptom: str|None=None; priority: str=Field(default="normal",pattern="^(low|normal|high|urgent)$"); service_type: str=Field(default="bench",pattern="^(bench|field|remote|pickup|delivery)$")
class TriagePayload(BaseModel):
    physical_condition: str|None=None; visual_signs: str|None=None; powers_on: bool|None=None; accessories: dict={}; electrical_risk: bool=False; mechanical_risk: bool=False; suggested_priority: str|None=Field(default=None,pattern="^(low|normal|high|urgent)$"); observations: str|None=None; checklist: dict={}
class TaskPayload(BaseModel):
    title: str=Field(min_length=2,max_length=200); description: str|None=None; assigned_to: str|None=None; priority: str=Field(default="normal",pattern="^(low|normal|high|urgent)$"); due_at: datetime|None=None
class TaskStatePayload(BaseModel): status: str=Field(pattern="^(pending|in_progress|blocked|completed|cancelled)$"); blocked_reason: str|None=None
class TimelinePayload(BaseModel): detail: str=Field(min_length=1,max_length=5000); visibility: str=Field(default="internal",pattern="^(internal|public)$")

def build_router(current_user:Callable,require:Callable,audit:Callable)->APIRouter:
    router=APIRouter(prefix="/api/v1/service-orders",tags=["service-orders"])
    def owned(session,user,id):
        item=session.scalar(select(ServiceOrder).where(ServiceOrder.id==id,ServiceOrder.company_id==user.company_id))
        if not item: raise HTTPException(404,"service order not found")
        return item
    def number(session,company):
        sequence=session.scalar(select(ServiceOrderSequence).where(ServiceOrderSequence.company_id==company).with_for_update())
        if not sequence:
            sequence=ServiceOrderSequence(company_id=company,next_number=(session.scalar(select(func.max(ServiceOrder.number)).where(ServiceOrder.company_id==company)) or 0)+1);session.add(sequence);session.flush()
        result=sequence.next_number;sequence.next_number+=1;return result
    @router.get("")
    def list_orders(q:str|None=None,status:str|None=None,priority:str|None=None,page:int=1,limit:int=50,user:User=Depends(current_user),session:Session=Depends(db)):
        statement=select(ServiceOrder).where(ServiceOrder.company_id==user.company_id).order_by(ServiceOrder.updated_at.desc()).offset((max(page,1)-1)*min(limit,100)).limit(min(limit,100))
        if q: statement=statement.where(ServiceOrder.title.ilike(f"%{q[:100]}%"))
        if status: statement=statement.where(ServiceOrder.status==status)
        if priority: statement=statement.where(ServiceOrder.priority==priority)
        return {"items":[{"id":x.id,"number":x.number,"customer_id":x.customer_id,"equipment_id":x.equipment_id,"title":x.title,"status":x.status,"priority":x.priority,"service_type":x.service_type,"sla_due_at":x.sla_due_at,"team_id":x.team_id,"technician_id":x.technician_id} for x in session.scalars(statement).all()],"page":page,"limit":limit}
    @router.post("/from-conversation",status_code=201)
    def create_from_conversation(payload:IntakePayload,user:User=Depends(require("service_order.create")),session:Session=Depends(db)):
        customer=session.scalar(select(Customer).where(Customer.id==payload.customer_id,Customer.company_id==user.company_id))
        if not customer: raise HTTPException(404,"customer not found")
        if payload.equipment_id and not session.scalar(select(Equipment).where(Equipment.id==payload.equipment_id,Equipment.customer_id==customer.id,Equipment.company_id==user.company_id)): raise HTTPException(422,"equipment does not belong to customer")
        if payload.conversation_id and not session.scalar(select(Conversation).where(Conversation.id==payload.conversation_id,Conversation.company_id==user.company_id)): raise HTTPException(422,"conversation not found")
        existing=session.scalar(select(ServiceOrder).where(ServiceOrder.company_id==user.company_id,ServiceOrder.conversation_id==payload.conversation_id,ServiceOrder.status.not_in(["closed","cancelled"]))) if payload.conversation_id else None
        if existing: raise HTTPException(409,detail={"message":"conversation already has an open service order","service_order_id":existing.id})
        item=ServiceOrder(company_id=user.company_id,number=number(session,user.company_id),customer_id=customer.id,contact_id=payload.contact_id,equipment_id=payload.equipment_id,conversation_id=payload.conversation_id,channel_of_origin="telegram" if payload.conversation_id else "web",service_type=payload.service_type,title=payload.title,symptom=payload.symptom,priority=payload.priority,status="draft",received_at=datetime.now(UTC),sla_policy={"response_minutes":60,"triage_minutes":240,"resolution_minutes":2880},sla_due_at=datetime.now(UTC)+timedelta(minutes=2880))
        session.add(item);session.flush(); version=ensure_default_workflow(session,user.company_id,user.id);instance=start_instance(session,company_id=user.company_id,workflow_version=version,entity_type="service_order",entity_id=item.id,actor_id=user.id);item.workflow_instance_id=instance.id;session.add(ServiceOrderEvent(service_order_id=item.id,actor_id=user.id,event_type="created_from_conversation",detail="service order intake created"));audit(session,user,"service_order_created_from_conversation","service_order",item.id,{"number":item.number});session.commit();return {"id":item.id,"number":item.number,"workflow_instance_id":instance.id,"status":item.status,"sla_due_at":item.sla_due_at}
    @router.get("/{order_id}")
    def detail(order_id:str,user:User=Depends(current_user),session:Session=Depends(db)):
        item=owned(session,user,order_id); tasks=session.scalars(select(ServiceOrderTask).where(ServiceOrderTask.service_order_id==item.id).order_by(ServiceOrderTask.created_at)).all(); events=session.scalars(select(ServiceOrderEvent).where(ServiceOrderEvent.service_order_id==item.id).order_by(ServiceOrderEvent.created_at)).all(); triage=session.scalar(select(ServiceOrderTriage).where(ServiceOrderTriage.service_order_id==item.id)); return {"id":item.id,"number":item.number,"customer_id":item.customer_id,"equipment_id":item.equipment_id,"conversation_id":item.conversation_id,"title":item.title,"symptom":item.symptom,"status":item.status,"priority":item.priority,"service_type":item.service_type,"team_id":item.team_id,"responsible_id":item.responsible_id,"technician_id":item.technician_id,"sla_due_at":item.sla_due_at,"sla_violated":sla_violated(item.sla_due_at,item.status),"tasks":[task_view(x) for x in tasks],"triage":triage_view(triage) if triage else None,"timeline":[{"id":x.id,"event_type":x.event_type,"detail":x.detail,"actor_id":x.actor_id,"created_at":x.created_at} for x in events]}
    @router.post("/{order_id}/triage")
    def triage(order_id:str,payload:TriagePayload,user:User=Depends(require("triage.perform")),session:Session=Depends(db)):
        item=owned(session,user,order_id); current=session.scalar(select(ServiceOrderTriage).where(ServiceOrderTriage.service_order_id==item.id)); data=payload.model_dump()
        if current:
            for key,value in data.items(): setattr(current,key,value)
        else: current=ServiceOrderTriage(company_id=user.company_id,service_order_id=item.id,performed_by=user.id,**data);session.add(current)
        item.triaged_at=datetime.now(UTC); item.status="triage"; item.priority=payload.suggested_priority or item.priority; session.add(ServiceOrderEvent(service_order_id=item.id,actor_id=user.id,event_type="triage_completed",detail="technical triage recorded"));audit(session,user,"service_order_triage_completed","service_order",item.id);session.commit();return triage_view(current)
    @router.post("/{order_id}/tasks",status_code=201)
    def create_task(order_id:str,payload:TaskPayload,user:User=Depends(require("task.manage")),session:Session=Depends(db)):
        item=owned(session,user,order_id); task=ServiceOrderTask(company_id=user.company_id,service_order_id=item.id,**payload.model_dump());session.add(task);session.flush();session.add(ServiceOrderEvent(service_order_id=item.id,actor_id=user.id,event_type="task_created",detail=payload.title));audit(session,user,"service_order_task_created","service_order_task",task.id);session.commit();return task_view(task)
    @router.patch("/{order_id}/tasks/{task_id}")
    def update_task(order_id:str,task_id:str,payload:TaskStatePayload,user:User=Depends(require("task.manage")),session:Session=Depends(db)):
        item=owned(session,user,order_id);task=session.scalar(select(ServiceOrderTask).where(ServiceOrderTask.id==task_id,ServiceOrderTask.service_order_id==item.id,ServiceOrderTask.company_id==user.company_id));
        if not task: raise HTTPException(404,"task not found")
        task.status=payload.status;task.blocked_reason=payload.blocked_reason;task.completed_at=datetime.now(UTC) if payload.status=="completed" else None;session.add(ServiceOrderEvent(service_order_id=item.id,actor_id=user.id,event_type="task_updated",detail=f"{task.title}: {task.status}"));audit(session,user,"service_order_task_updated","service_order_task",task.id);session.commit();return task_view(task)
    @router.post("/{order_id}/timeline")
    def timeline(order_id:str,payload:TimelinePayload,user:User=Depends(current_user),session:Session=Depends(db)):
        item=owned(session,user,order_id);event_type="public_update" if payload.visibility=="public" else "internal_comment";session.add(ServiceOrderEvent(service_order_id=item.id,actor_id=user.id,event_type=event_type,detail=payload.detail));audit(session,user,event_type,"service_order",item.id)
        if payload.visibility=="public" and item.conversation_id:
            conversation=session.get(Conversation,item.conversation_id);channel=session.get(Channel,conversation.channel_id) if conversation else None
            if conversation and channel and channel.kind=="telegram": queue_outbound_message(session,conversation=conversation,channel=channel,author_name="Provisão",body=payload.detail,idempotency_key=f"os-public:{item.id}:{datetime.now(UTC).timestamp()}",bot_id=conversation.bot_id)
        session.commit();return {"ok":True,"visibility":payload.visibility}
    return router

def task_view(x): return {"id":x.id,"service_order_id":x.service_order_id,"title":x.title,"description":x.description,"assigned_to":x.assigned_to,"status":x.status,"priority":x.priority,"due_at":x.due_at,"completed_at":x.completed_at,"blocked_reason":x.blocked_reason}
def sla_violated(due,status):
    if not due or status in {"closed","cancelled"}: return False
    if due.tzinfo is None: due=due.replace(tzinfo=UTC)
    return due < datetime.now(UTC)
def triage_view(x): return {"id":x.id,"service_order_id":x.service_order_id,"performed_by":x.performed_by,"physical_condition":x.physical_condition,"visual_signs":x.visual_signs,"powers_on":x.powers_on,"accessories":x.accessories or {},"electrical_risk":x.electrical_risk,"mechanical_risk":x.mechanical_risk,"suggested_priority":x.suggested_priority,"observations":x.observations,"checklist":x.checklist or {}}
