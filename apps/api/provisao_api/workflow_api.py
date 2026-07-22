from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .db import SessionLocal
from .models import (Role, ServiceOrder, ServiceOrderEvent, User, UserRole,
    WorkflowDefinition, WorkflowExecutionEvent, WorkflowInstance, WorkflowState,
    WorkflowTransition, WorkflowVersion)
from .services.workflow import (WorkflowError, cancel_instance, clone_version,
    create_definition, ensure_draft, execute_transition, pause_instance,
    publish_version, resume_instance, start_instance, validate_actions,
    validate_condition_schema, validate_graph)

def db_session():
    session = SessionLocal()
    try: yield session
    finally: session.close()

class DefinitionIn(BaseModel):
    code: str = Field(pattern=r"^[a-z][a-z0-9_\-]{1,79}$")
    name: str = Field(min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=4000)
    entity_type: str = Field(default="service_order", pattern=r"^[a-z][a-z0-9_]{1,79}$")

class StateIn(BaseModel):
    code: str = Field(pattern=r"^[a-z][a-z0-9_\-]{1,79}$")
    name: str = Field(min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=4000)
    category: str = Field(pattern="^(intake|triage|technical|waiting|field|delivery|closed|warranty|cancelled)$")
    is_initial: bool = False; is_terminal: bool = False; is_public: bool = False
    position: int = Field(default=0, ge=0, le=10000)
    metadata: dict[str, Any] = Field(default_factory=dict)

class StateOrderIn(BaseModel): ids: list[str] = Field(min_length=1, max_length=500)

class TransitionIn(BaseModel):
    code: str = Field(pattern=r"^[a-z][a-z0-9_\-]{1,79}$")
    name: str = Field(min_length=2, max_length=160)
    from_state_id: str; to_state_id: str
    required_permission: str | None = Field(default="workflow.execute", max_length=100)
    requires_reason: bool = False; requires_assignment: bool = False
    requires_checklist_completion: bool = False; requires_diagnosis: bool = False
    requires_customer_notification: bool = False
    conditions: dict[str, Any] = Field(default_factory=dict)
    actions: list[dict[str, Any]] = Field(default_factory=list)
    active: bool = True; position: int = Field(default=0, ge=0, le=10000)

class ExecuteIn(BaseModel):
    transition_id: str
    reason: str | None = Field(default=None, max_length=4000)
    context: dict[str, Any] = Field(default_factory=dict)

class StartIn(BaseModel):
    workflow_version_id: str; entity_type: str = Field(pattern=r"^[a-z][a-z0-9_]{1,79}$"); entity_id: str
    metadata: dict[str, Any] = Field(default_factory=dict)

def definition_view(item: WorkflowDefinition):
    return {"id":item.id,"code":item.code,"name":item.name,"description":item.description,"entity_type":item.entity_type,"status":item.status,"created_at":item.created_at,"updated_at":item.updated_at}

def version_view(item: WorkflowVersion):
    return {"id":item.id,"workflow_definition_id":item.workflow_definition_id,"version_number":item.version_number,"status":item.status,"description":item.description,"created_at":item.created_at,"published_at":item.published_at,"superseded_at":item.superseded_at}

def state_view(item: WorkflowState):
    return {"id":item.id,"workflow_version_id":item.workflow_version_id,"code":item.code,"name":item.name,"description":item.description,"category":item.category,"is_initial":item.is_initial,"is_terminal":item.is_terminal,"is_public":item.is_public,"position":item.position,"metadata":item.metadata_json}

def transition_view(item: WorkflowTransition):
    return {"id":item.id,"workflow_version_id":item.workflow_version_id,"code":item.code,"name":item.name,"from_state_id":item.from_state_id,"to_state_id":item.to_state_id,"required_permission":item.required_permission,"requires_reason":item.requires_reason,"requires_assignment":item.requires_assignment,"requires_checklist_completion":item.requires_checklist_completion,"requires_diagnosis":item.requires_diagnosis,"requires_customer_notification":item.requires_customer_notification,"conditions":item.conditions,"actions":item.actions,"active":item.active,"position":item.position}

def build_workflow_router(current_user: Callable, require: Callable, audit: Callable) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["workflow"])

    def owned_definition(session, user, item_id):
        item=session.scalar(select(WorkflowDefinition).where(WorkflowDefinition.id==item_id,WorkflowDefinition.company_id==user.company_id))
        if not item: raise HTTPException(404,"workflow definition not found")
        return item
    def owned_version(session,user,item_id):
        item=session.scalar(select(WorkflowVersion).join(WorkflowDefinition,WorkflowDefinition.id==WorkflowVersion.workflow_definition_id).where(WorkflowVersion.id==item_id,WorkflowDefinition.company_id==user.company_id))
        if not item: raise HTTPException(404,"workflow version not found")
        return item
    def owned_instance(session,user,item_id):
        item=session.scalar(select(WorkflowInstance).where(WorkflowInstance.id==item_id,WorkflowInstance.company_id==user.company_id))
        if not item: raise HTTPException(404,"workflow instance not found")
        return item
    def fail(exc):
        raise HTTPException(409,str(exc)) from exc

    @router.get("/workflows")
    def list_definitions(q:str|None=None,status_filter:str|None=None,page:int=1,limit:int=50,user:User=Depends(require("workflow.view")),session:Session=Depends(db_session)):
        stmt=select(WorkflowDefinition).where(WorkflowDefinition.company_id==user.company_id)
        if q: stmt=stmt.where(WorkflowDefinition.name.ilike(f"%{q[:100]}%"))
        if status_filter: stmt=stmt.where(WorkflowDefinition.status==status_filter)
        total=session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        items=session.scalars(stmt.order_by(WorkflowDefinition.name).offset((max(page,1)-1)*min(limit,100)).limit(min(limit,100))).all()
        return {"items":[definition_view(item) for item in items],"total":total,"page":max(page,1),"limit":min(limit,100)}

    @router.post("/workflows",status_code=201)
    def create(payload:DefinitionIn,user:User=Depends(require("workflow.manage")),session:Session=Depends(db_session)):
        if session.scalar(select(WorkflowDefinition).where(WorkflowDefinition.company_id==user.company_id,WorkflowDefinition.code==payload.code)): raise HTTPException(409,"workflow code already exists")
        item,version=create_definition(session,company_id=user.company_id,actor_id=user.id,**payload.model_dump()); audit(session,user,"workflow_created","workflow_definition",item.id,{"version_id":version.id});session.commit()
        return {**definition_view(item),"draft_version":version_view(version)}

    @router.get("/workflows/{definition_id}")
    def get_definition(definition_id:str,user:User=Depends(require("workflow.view")),session:Session=Depends(db_session)):
        item=owned_definition(session,user,definition_id); versions=session.scalars(select(WorkflowVersion).where(WorkflowVersion.workflow_definition_id==item.id).order_by(WorkflowVersion.version_number.desc())).all()
        return {**definition_view(item),"versions":[version_view(version) for version in versions]}

    @router.post("/workflow-versions/{version_id}/clone",status_code=201)
    def clone(version_id:str,user:User=Depends(require("workflow.manage")),session:Session=Depends(db_session)):
        source=owned_version(session,user,version_id)
        try: target=clone_version(session,source,user.id)
        except WorkflowError as exc: fail(exc)
        audit(session,user,"workflow_version_cloned","workflow_version",target.id,{"source_id":source.id});session.commit();return version_view(target)

    @router.get("/workflow-versions/{version_id}")
    def get_version(version_id:str,user:User=Depends(require("workflow.view")),session:Session=Depends(db_session)):
        version=owned_version(session,user,version_id);states=session.scalars(select(WorkflowState).where(WorkflowState.workflow_version_id==version.id).order_by(WorkflowState.position)).all();transitions=session.scalars(select(WorkflowTransition).where(WorkflowTransition.workflow_version_id==version.id).order_by(WorkflowTransition.position)).all()
        return {**version_view(version),"states":[state_view(item) for item in states],"transitions":[transition_view(item) for item in transitions],"validation_errors":validate_graph(session,version)}

    @router.post("/workflow-versions/{version_id}/states",status_code=201)
    def add_state(version_id:str,payload:StateIn,user:User=Depends(require("workflow.manage")),session:Session=Depends(db_session)):
        version=owned_version(session,user,version_id)
        try: ensure_draft(version)
        except WorkflowError as exc: fail(exc)
        if session.scalar(select(WorkflowState).where(WorkflowState.workflow_version_id==version.id,WorkflowState.code==payload.code)): raise HTTPException(409,"state code already exists")
        item=WorkflowState(workflow_version_id=version.id,metadata_json=payload.metadata,**payload.model_dump(exclude={"metadata"}));session.add(item);session.flush();audit(session,user,"workflow_state_created","workflow_state",item.id);session.commit();return state_view(item)

    @router.patch("/workflow-states/{state_id}")
    def update_state(state_id:str,payload:StateIn,user:User=Depends(require("workflow.manage")),session:Session=Depends(db_session)):
        item=session.get(WorkflowState,state_id)
        if not item: raise HTTPException(404,"workflow state not found")
        version=owned_version(session,user,item.workflow_version_id)
        try: ensure_draft(version)
        except WorkflowError as exc: fail(exc)
        for key,value in payload.model_dump(exclude={"metadata"}).items():setattr(item,key,value)
        item.metadata_json=payload.metadata;audit(session,user,"workflow_state_updated","workflow_state",item.id);session.commit();return state_view(item)

    @router.delete("/workflow-states/{state_id}")
    def delete_state(state_id:str,user:User=Depends(require("workflow.manage")),session:Session=Depends(db_session)):
        item=session.get(WorkflowState,state_id)
        if not item: raise HTTPException(404,"workflow state not found")
        version=owned_version(session,user,item.workflow_version_id)
        try: ensure_draft(version)
        except WorkflowError as exc: fail(exc)
        used=session.scalar(select(func.count()).where((WorkflowTransition.from_state_id==item.id)|(WorkflowTransition.to_state_id==item.id))) or 0
        if used: raise HTTPException(409,"state is referenced by transitions")
        session.delete(item);audit(session,user,"workflow_state_deleted","workflow_state",item.id);session.commit();return {"ok":True}

    @router.post("/workflow-versions/{version_id}/states/reorder")
    def reorder_states(version_id:str,payload:StateOrderIn,user:User=Depends(require("workflow.manage")),session:Session=Depends(db_session)):
        version=owned_version(session,user,version_id)
        try: ensure_draft(version)
        except WorkflowError as exc: fail(exc)
        states=session.scalars(select(WorkflowState).where(WorkflowState.workflow_version_id==version.id)).all();by_id={item.id:item for item in states}
        if set(payload.ids)!=set(by_id): raise HTTPException(422,"all version state ids are required exactly once")
        for position,item_id in enumerate(payload.ids):by_id[item_id].position=position
        session.commit();return {"ok":True}

    @router.post("/workflow-versions/{version_id}/transitions",status_code=201)
    def add_transition(version_id:str,payload:TransitionIn,user:User=Depends(require("workflow.manage")),session:Session=Depends(db_session)):
        version=owned_version(session,user,version_id)
        try: ensure_draft(version);validate_condition_schema(payload.conditions);validate_actions(payload.actions)
        except WorkflowError as exc: fail(exc)
        states=session.scalars(select(WorkflowState).where(WorkflowState.id.in_([payload.from_state_id,payload.to_state_id]),WorkflowState.workflow_version_id==version.id)).all()
        if len(states)!=2: raise HTTPException(422,"transition states must belong to the version")
        item=WorkflowTransition(workflow_version_id=version.id,**payload.model_dump());session.add(item);session.flush();audit(session,user,"workflow_transition_created","workflow_transition",item.id);session.commit();return transition_view(item)

    @router.patch("/workflow-transitions/{transition_id}")
    def update_transition(transition_id:str,payload:TransitionIn,user:User=Depends(require("workflow.manage")),session:Session=Depends(db_session)):
        item=session.get(WorkflowTransition,transition_id)
        if not item: raise HTTPException(404,"workflow transition not found")
        version=owned_version(session,user,item.workflow_version_id)
        try: ensure_draft(version);validate_condition_schema(payload.conditions);validate_actions(payload.actions)
        except WorkflowError as exc: fail(exc)
        states=session.scalars(select(WorkflowState).where(WorkflowState.id.in_([payload.from_state_id,payload.to_state_id]),WorkflowState.workflow_version_id==version.id)).all()
        if len(states)!=2: raise HTTPException(422,"transition states must belong to the version")
        for key,value in payload.model_dump().items():setattr(item,key,value)
        audit(session,user,"workflow_transition_updated","workflow_transition",item.id);session.commit();return transition_view(item)

    @router.get("/workflow-versions/{version_id}/validate")
    def validate(version_id:str,user:User=Depends(require("workflow.view")),session:Session=Depends(db_session)):
        version=owned_version(session,user,version_id);errors=validate_graph(session,version);return {"valid":not errors,"errors":errors}

    @router.post("/workflow-versions/{version_id}/publish")
    def publish(version_id:str,user:User=Depends(require("workflow.publish")),session:Session=Depends(db_session)):
        version=owned_version(session,user,version_id)
        try: publish_version(session,version,user.id)
        except WorkflowError as exc: raise HTTPException(422,str(exc)) from exc
        audit(session,user,"workflow_version_published","workflow_version",version.id,{"version":version.version_number});session.commit();return version_view(version)

    @router.post("/workflow-versions/{version_id}/archive")
    def archive(version_id:str,user:User=Depends(require("workflow.manage")),session:Session=Depends(db_session)):
        version=owned_version(session,user,version_id)
        if version.status=="published":raise HTTPException(409,"published version must be superseded before archival")
        version.status="archived";audit(session,user,"workflow_version_archived","workflow_version",version.id);session.commit();return version_view(version)

    @router.get("/workflow-instances")
    def list_instances(entity_type:str|None=None,status_filter:str|None=None,user:User=Depends(require("workflow.view")),session:Session=Depends(db_session)):
        stmt=select(WorkflowInstance).where(WorkflowInstance.company_id==user.company_id)
        if entity_type:stmt=stmt.where(WorkflowInstance.entity_type==entity_type)
        if status_filter:stmt=stmt.where(WorkflowInstance.status==status_filter)
        return {"items":[{"id":item.id,"workflow_version_id":item.workflow_version_id,"entity_type":item.entity_type,"entity_id":item.entity_id,"current_state_id":item.current_state_id,"status":item.status,"started_at":item.started_at,"completed_at":item.completed_at} for item in session.scalars(stmt.order_by(WorkflowInstance.started_at.desc()).limit(200)).all()]}

    @router.post("/workflow-instances",status_code=201)
    def start(payload:StartIn,user:User=Depends(require("workflow.execute")),session:Session=Depends(db_session)):
        version=owned_version(session,user,payload.workflow_version_id)
        try:item=start_instance(session,company_id=user.company_id,workflow_version=version,entity_type=payload.entity_type,entity_id=payload.entity_id,actor_id=user.id,metadata=payload.metadata)
        except WorkflowError as exc:fail(exc)
        audit(session,user,"workflow_instance_started","workflow_instance",item.id,{"entity_type":item.entity_type,"entity_id":item.entity_id});session.commit();return {"id":item.id,"current_state_id":item.current_state_id,"status":item.status}

    @router.get("/workflow-instances/{instance_id}")
    def get_instance(instance_id:str,user:User=Depends(require("workflow.view")),session:Session=Depends(db_session)):
        item=owned_instance(session,user,instance_id);events=session.scalars(select(WorkflowExecutionEvent).where(WorkflowExecutionEvent.workflow_instance_id==item.id).order_by(WorkflowExecutionEvent.created_at)).all();transitions=session.scalars(select(WorkflowTransition).where(WorkflowTransition.workflow_version_id==item.workflow_version_id,WorkflowTransition.from_state_id==item.current_state_id,WorkflowTransition.active.is_(True)).order_by(WorkflowTransition.position)).all()
        return {"id":item.id,"workflow_version_id":item.workflow_version_id,"entity_type":item.entity_type,"entity_id":item.entity_id,"current_state_id":item.current_state_id,"status":item.status,"metadata":item.metadata_json,"available_transitions":[transition_view(value) for value in transitions],"events":[{"id":event.id,"transition_id":event.transition_id,"from_state_id":event.from_state_id,"to_state_id":event.to_state_id,"performed_by":event.performed_by,"reason":event.reason,"context":event.context,"created_at":event.created_at} for event in events]}

    def action_handlers(actor:User):
        def audit_action(session,instance,params,context):audit(session,actor,params.get("event","workflow_action"),instance.entity_type,instance.entity_id);return {"audited":True}
        def timeline(session,instance,params,context):
            if instance.entity_type=="service_order":session.add(ServiceOrderEvent(service_order_id=instance.entity_id,actor_id=actor.id,event_type=params.get("event_type","workflow"),detail=str(params.get("detail","workflow action"))[:4000]))
            return {"created":True}
        def update_field(session,instance,params,context):
            if instance.entity_type!="service_order" or params.get("field") not in {"status","priority"}:raise WorkflowError("field is not allowlisted")
            order=session.get(ServiceOrder,instance.entity_id);setattr(order,params["field"],params.get("value"));return {"field":params["field"]}
        return {"audit":audit_action,"add_timeline":timeline,"update_allowed_field":update_field}

    @router.post("/workflow-instances/{instance_id}/execute")
    def execute(instance_id:str,payload:ExecuteIn,user:User=Depends(require("workflow.execute")),session:Session=Depends(db_session)):
        instance=owned_instance(session,user,instance_id);transition=session.get(WorkflowTransition,payload.transition_id)
        if not transition:raise HTTPException(404,"workflow transition not found")
        roles=session.scalars(select(Role).join(UserRole,UserRole.role_id==Role.id).where(UserRole.user_id==user.id)).all();permissions={permission for role in roles for permission in role.permissions.get("permissions",[])}
        if any(role.code=="admin" for role in roles):permissions.update({"workflow.execute",transition.required_permission} if transition.required_permission else {"workflow.execute"})
        try:event=execute_transition(session,instance=instance,transition=transition,actor_id=user.id,permissions=permissions,reason=payload.reason,context=payload.context,handlers=action_handlers(user))
        except WorkflowError as exc:
            audit(session,user,"workflow_transition_rejected","workflow_instance",instance.id,{"transition_id":payload.transition_id,"reason":str(exc)});session.commit();raise HTTPException(409,str(exc)) from exc
        if instance.entity_type=="service_order":
            order=session.scalar(select(ServiceOrder).where(ServiceOrder.id==instance.entity_id,ServiceOrder.company_id==user.company_id));destination=session.get(WorkflowState,instance.current_state_id)
            if order and destination:order.status=destination.code;order.version+=1;session.add(ServiceOrderEvent(service_order_id=order.id,actor_id=user.id,event_type="status_changed",detail=f"workflow transition to {destination.code}: {payload.reason or ''}"))
        audit(session,user,"workflow_transition_executed","workflow_instance",instance.id,{"transition_id":transition.id,"event_id":event.id});session.commit();return {"event_id":event.id,"current_state_id":instance.current_state_id,"status":instance.status}

    @router.post("/workflow-instances/{instance_id}/{action}")
    def instance_control(instance_id:str,action:str,user:User=Depends(require("workflow.execute")),session:Session=Depends(db_session)):
        item=owned_instance(session,user,instance_id)
        try:
            if action=="pause":pause_instance(item)
            elif action=="resume":resume_instance(item)
            elif action=="cancel":cancel_instance(item)
            else:raise HTTPException(422,"invalid workflow action")
        except WorkflowError as exc:fail(exc)
        audit(session,user,f"workflow_instance_{action}","workflow_instance",item.id);session.commit();return {"id":item.id,"status":item.status}

    return router
