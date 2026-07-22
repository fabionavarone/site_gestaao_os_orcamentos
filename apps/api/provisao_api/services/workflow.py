"""Persistent, versioned workflow application service.

The engine only evaluates an allowlisted declarative condition language. Domain
actions are injected handlers so workflow configuration never gains SQL access.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import (WorkflowActionExecution, WorkflowDefinition,
    WorkflowExecutionEvent, WorkflowInstance, WorkflowState,
    WorkflowTransition, WorkflowVersion)

Condition = dict[str, Any]
ActionHandler = Callable[[Session, WorkflowInstance, dict[str, Any], dict[str, Any]], dict[str, Any] | None]
ALLOWED_OPERATORS = {"equals", "not_equals", "in", "not_in", "exists", "greater_than", "less_than", "all", "any"}
ALLOWED_ACTIONS = {"create_task", "assign_team", "assign_technician", "set_priority", "start_sla", "pause_sla", "resume_sla", "create_checklist", "add_timeline", "send_public_notification", "pause_automation", "update_allowed_field", "audit"}
DEFAULT_STATE_CODES = ("draft","awaiting_receipt","received","triage","diagnosis","awaiting_budget","awaiting_customer_approval","approved","rejected","awaiting_parts","repair_in_progress","quality_test","technical_hold","customer_hold","financial_hold","ready_for_delivery","delivered","closed","cancelled","warranty_return","no_repair_condition")
DEFAULT_TRANSITIONS = {"draft":("awaiting_receipt","received","cancelled"),"awaiting_receipt":("received","cancelled"),"received":("triage","cancelled"),"triage":("diagnosis","technical_hold","customer_hold"),"diagnosis":("awaiting_budget","no_repair_condition","technical_hold"),"awaiting_budget":("awaiting_customer_approval",),"awaiting_customer_approval":("approved","rejected","customer_hold"),"approved":("awaiting_parts","repair_in_progress"),"awaiting_parts":("repair_in_progress","technical_hold"),"repair_in_progress":("quality_test","technical_hold"),"quality_test":("ready_for_delivery","repair_in_progress"),"ready_for_delivery":("delivered","financial_hold"),"delivered":("closed","warranty_return"),"rejected":("closed",),"no_repair_condition":("closed",),"technical_hold":("triage","diagnosis","repair_in_progress"),"customer_hold":("triage","awaiting_customer_approval"),"financial_hold":("ready_for_delivery","closed"),"warranty_return":("triage",)}

class WorkflowError(ValueError):
    pass

def now():
    return datetime.now(UTC)

def ensure_draft(version: WorkflowVersion) -> None:
    if version.status != "draft":
        raise WorkflowError("published workflow versions are immutable")

def _value(context: dict[str, Any], path: str) -> Any:
    current: Any = context
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current

def validate_condition_schema(condition: Condition | None) -> None:
    if not condition:
        return
    if not isinstance(condition, dict) or len(condition) != 1:
        raise WorkflowError("condition must contain exactly one operator")
    operator, payload = next(iter(condition.items()))
    if operator not in ALLOWED_OPERATORS:
        raise WorkflowError("condition operator is not allowed")
    if operator in {"all", "any"}:
        if not isinstance(payload, list) or not payload:
            raise WorkflowError(f"{operator} requires a non-empty list")
        for item in payload:
            validate_condition_schema(item)
        return
    if not isinstance(payload, dict) or not isinstance(payload.get("field"), str):
        raise WorkflowError(f"{operator} requires a field")
    if operator != "exists" and "value" not in payload:
        raise WorkflowError(f"{operator} requires a value")

def evaluate_condition(condition: Condition | None, context: dict[str, Any]) -> bool:
    validate_condition_schema(condition)
    if not condition:
        return True
    operator, payload = next(iter(condition.items()))
    if operator == "all": return all(evaluate_condition(item, context) for item in payload)
    if operator == "any": return any(evaluate_condition(item, context) for item in payload)
    actual = _value(context, payload["field"]); expected = payload.get("value")
    if operator == "equals": return actual == expected
    if operator == "not_equals": return actual != expected
    if operator == "in": return actual in expected if isinstance(expected, list) else False
    if operator == "not_in": return actual not in expected if isinstance(expected, list) else False
    if operator == "exists": return (actual is not None) == bool(payload.get("value", True))
    if operator == "greater_than": return actual is not None and actual > expected
    if operator == "less_than": return actual is not None and actual < expected
    return False

def validate_actions(actions: list[dict[str, Any]] | None) -> None:
    if actions is None:
        return
    if not isinstance(actions, list):
        raise WorkflowError("actions must be a list")
    for action in actions:
        if not isinstance(action, dict) or action.get("type") not in ALLOWED_ACTIONS:
            raise WorkflowError("workflow action is not allowed")
        if not isinstance(action.get("params", {}), dict):
            raise WorkflowError("workflow action params must be an object")

def validate_graph(session: Session, version: WorkflowVersion) -> list[str]:
    states = list(session.scalars(select(WorkflowState).where(WorkflowState.workflow_version_id == version.id)))
    transitions = list(session.scalars(select(WorkflowTransition).where(WorkflowTransition.workflow_version_id == version.id, WorkflowTransition.active.is_(True))))
    errors: list[str] = []
    initial = [state for state in states if state.is_initial]
    if len(initial) != 1: errors.append("workflow must have exactly one initial state")
    state_ids = {state.id for state in states}
    outgoing: dict[str, set[str]] = {state.id: set() for state in states}
    for transition in transitions:
        if transition.from_state_id not in state_ids or transition.to_state_id not in state_ids:
            errors.append(f"transition {transition.code} references a state from another version")
            continue
        if transition.from_state_id == transition.to_state_id:
            errors.append(f"transition {transition.code} cannot target the same state")
        outgoing[transition.from_state_id].add(transition.to_state_id)
        try:
            validate_condition_schema(transition.conditions)
            validate_actions(transition.actions)
        except WorkflowError as exc:
            errors.append(f"transition {transition.code}: {exc}")
    for state in states:
        if state.is_terminal and outgoing[state.id]: errors.append(f"terminal state {state.code} has outgoing transitions")
    if len(initial) == 1:
        reached, pending = set(), [initial[0].id]
        while pending:
            current = pending.pop()
            if current in reached: continue
            reached.add(current); pending.extend(outgoing.get(current, set()) - reached)
        for state in states:
            if state.id not in reached: errors.append(f"state {state.code} is unreachable")
    return errors

def create_definition(session: Session, *, company_id: str, code: str, name: str, description: str | None, entity_type: str, actor_id: str | None) -> tuple[WorkflowDefinition, WorkflowVersion]:
    item = WorkflowDefinition(company_id=company_id, code=code, name=name, description=description, entity_type=entity_type, status="draft", created_by=actor_id)
    session.add(item); session.flush()
    version = WorkflowVersion(workflow_definition_id=item.id, version_number=1, status="draft", created_by=actor_id)
    session.add(version); session.flush()
    return item, version

def ensure_default_workflow(session: Session, company_id: str, actor_id: str) -> WorkflowVersion:
    version = session.scalar(select(WorkflowVersion).join(WorkflowDefinition).where(WorkflowDefinition.company_id == company_id, WorkflowDefinition.code == "service_order_default", WorkflowVersion.status == "published"))
    if version:
        return version
    definition, version = create_definition(session, company_id=company_id, code="service_order_default", name="Fluxo padrão de OS", description="Fluxo operacional padrão", entity_type="service_order", actor_id=actor_id)
    states: dict[str, WorkflowState] = {}
    for position, code in enumerate(DEFAULT_STATE_CODES):
        category = "intake" if code in {"draft","awaiting_receipt","received"} else "triage" if code == "triage" else "delivery" if code in {"ready_for_delivery","delivered"} else "warranty" if code == "warranty_return" else "cancelled" if code == "cancelled" else "closed" if code in {"closed","rejected","no_repair_condition"} else "waiting" if code.endswith("hold") or code.startswith("awaiting") else "technical"
        state = WorkflowState(workflow_version_id=version.id, code=code, name=code.replace("_"," ").title(), category=category, is_initial=code=="draft", is_terminal=code in {"closed","cancelled"}, is_public=code not in {"draft","technical_hold","financial_hold"}, position=position, metadata_json={})
        session.add(state); session.flush(); states[code] = state
    for origin, destinations in DEFAULT_TRANSITIONS.items():
        for position, destination in enumerate(destinations):
            session.add(WorkflowTransition(workflow_version_id=version.id, code=f"{origin}_to_{destination}", name=f"{states[origin].name} → {states[destination].name}", from_state_id=states[origin].id, to_state_id=states[destination].id, required_permission="service_order.transition", requires_reason=destination in {"cancelled","technical_hold","customer_hold","closed"}, requires_checklist_completion=destination in {"ready_for_delivery","closed"}, requires_diagnosis=destination in {"awaiting_budget","ready_for_delivery"}, requires_customer_notification=states[destination].is_public, conditions={}, actions=[], position=position))
    publish_version(session, version, actor_id)
    return version

def clone_version(session: Session, source: WorkflowVersion, actor_id: str | None) -> WorkflowVersion:
    if source.status not in {"published", "superseded", "archived"}:
        raise WorkflowError("only immutable versions can be cloned")
    number = session.scalar(select(func.max(WorkflowVersion.version_number)).where(WorkflowVersion.workflow_definition_id == source.workflow_definition_id)) or 0
    target = WorkflowVersion(workflow_definition_id=source.workflow_definition_id, version_number=number + 1, status="draft", description=source.description, created_by=actor_id)
    session.add(target); session.flush(); state_map: dict[str, str] = {}
    states = list(session.scalars(select(WorkflowState).where(WorkflowState.workflow_version_id == source.id).order_by(WorkflowState.position)))
    for state in states:
        clone = WorkflowState(workflow_version_id=target.id, code=state.code, name=state.name, description=state.description, category=state.category, is_initial=state.is_initial, is_terminal=state.is_terminal, is_public=state.is_public, position=state.position, metadata_json=dict(state.metadata_json or {}))
        session.add(clone); session.flush(); state_map[state.id] = clone.id
    transitions = session.scalars(select(WorkflowTransition).where(WorkflowTransition.workflow_version_id == source.id).order_by(WorkflowTransition.position))
    for transition in transitions:
        session.add(WorkflowTransition(workflow_version_id=target.id, code=transition.code, name=transition.name, from_state_id=state_map[transition.from_state_id], to_state_id=state_map[transition.to_state_id], required_permission=transition.required_permission, requires_reason=transition.requires_reason, requires_assignment=transition.requires_assignment, requires_checklist_completion=transition.requires_checklist_completion, requires_diagnosis=transition.requires_diagnosis, requires_customer_notification=transition.requires_customer_notification, conditions=dict(transition.conditions or {}), actions=list(transition.actions or []), active=transition.active, position=transition.position))
    session.flush(); return target

def publish_version(session: Session, version: WorkflowVersion, actor_id: str) -> None:
    ensure_draft(version); errors = validate_graph(session, version)
    if errors: raise WorkflowError("; ".join(errors))
    previous = session.scalars(select(WorkflowVersion).where(WorkflowVersion.workflow_definition_id == version.workflow_definition_id, WorkflowVersion.status == "published", WorkflowVersion.id != version.id)).all()
    stamp = now()
    for item in previous: item.status = "superseded"; item.superseded_at = stamp
    version.status = "published"; version.published_by = actor_id; version.published_at = stamp
    definition = session.get(WorkflowDefinition, version.workflow_definition_id)
    if definition: definition.status = "active"

def start_instance(session: Session, *, company_id: str, workflow_version: WorkflowVersion, entity_type: str, entity_id: str, actor_id: str | None, metadata: dict[str, Any] | None = None) -> WorkflowInstance:
    if workflow_version.status != "published": raise WorkflowError("workflow version is not published")
    existing = session.scalar(select(WorkflowInstance).where(WorkflowInstance.company_id == company_id, WorkflowInstance.entity_type == entity_type, WorkflowInstance.entity_id == entity_id))
    if existing: return existing
    initial = session.scalars(select(WorkflowState).where(WorkflowState.workflow_version_id == workflow_version.id, WorkflowState.is_initial.is_(True))).all()
    if len(initial) != 1: raise WorkflowError("published workflow has invalid initial state")
    instance = WorkflowInstance(company_id=company_id, workflow_version_id=workflow_version.id, entity_type=entity_type, entity_id=entity_id, current_state_id=initial[0].id, status="running", metadata_json=metadata or {})
    session.add(instance); session.flush()
    session.add(WorkflowExecutionEvent(workflow_instance_id=instance.id, from_state_id=None, to_state_id=initial[0].id, performed_by=actor_id, reason="workflow started", context={}))
    return instance

def available_transitions(session: Session, instance: WorkflowInstance, *, permissions: set[str], context: dict[str, Any]) -> list[WorkflowTransition]:
    transitions = session.scalars(select(WorkflowTransition).where(WorkflowTransition.workflow_version_id == instance.workflow_version_id, WorkflowTransition.from_state_id == instance.current_state_id, WorkflowTransition.active.is_(True)).order_by(WorkflowTransition.position)).all()
    return [item for item in transitions if (not item.required_permission or item.required_permission in permissions) and evaluate_condition(item.conditions, context)]

def execute_transition(session: Session, *, instance: WorkflowInstance, transition: WorkflowTransition, actor_id: str, permissions: set[str], reason: str | None, context: dict[str, Any], handlers: dict[str, ActionHandler] | None = None) -> WorkflowExecutionEvent:
    if instance.status != "running": raise WorkflowError("workflow instance is not running")
    if transition.workflow_version_id != instance.workflow_version_id or transition.from_state_id != instance.current_state_id or not transition.active: raise WorkflowError("transition is not available from current state")
    if transition.required_permission and transition.required_permission not in permissions: raise WorkflowError("permission denied for transition")
    if transition.requires_reason and not (reason or "").strip(): raise WorkflowError("transition requires a reason")
    if transition.requires_assignment and not context.get("assigned"): raise WorkflowError("transition requires assignment")
    if transition.requires_checklist_completion and not context.get("checklist_complete"): raise WorkflowError("transition requires completed checklist")
    if transition.requires_diagnosis and not context.get("diagnosis_approved"): raise WorkflowError("transition requires approved diagnosis")
    if not evaluate_condition(transition.conditions, context): raise WorkflowError("transition conditions were not satisfied")
    destination = session.get(WorkflowState, transition.to_state_id)
    if not destination or destination.workflow_version_id != instance.workflow_version_id: raise WorkflowError("transition target is invalid")
    event = WorkflowExecutionEvent(workflow_instance_id=instance.id, transition_id=transition.id, from_state_id=instance.current_state_id, to_state_id=destination.id, performed_by=actor_id, reason=reason, context=context)
    session.add(event); session.flush(); instance.current_state_id = destination.id
    if destination.is_terminal: instance.status = "completed"; instance.completed_at = now()
    for action in transition.actions or []:
        execution = WorkflowActionExecution(workflow_execution_event_id=event.id, action_type=action["type"], status="processing", attempts=1)
        session.add(execution); session.flush()
        try:
            handler = (handlers or {}).get(action["type"])
            if not handler: raise WorkflowError(f"action handler is unavailable: {action['type']}")
            execution.result = handler(session, instance, action.get("params", {}), context) or {}; execution.status = "completed"; execution.completed_at = now()
        except Exception as exc:
            execution.status = "failed"; execution.error = str(exc)[:1000]
            raise
    return event

def pause_instance(instance: WorkflowInstance) -> None:
    if instance.status != "running": raise WorkflowError("only running instances can be paused")
    instance.status = "paused"; instance.paused_at = now()

def resume_instance(instance: WorkflowInstance) -> None:
    if instance.status != "paused": raise WorkflowError("only paused instances can be resumed")
    instance.status = "running"; instance.paused_at = None

def cancel_instance(instance: WorkflowInstance) -> None:
    if instance.status in {"completed", "cancelled"}: raise WorkflowError("workflow instance is already final")
    instance.status = "cancelled"; instance.completed_at = now()
