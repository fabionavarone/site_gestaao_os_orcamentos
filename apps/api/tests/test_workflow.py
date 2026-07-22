import os
import unittest
import uuid

os.environ.setdefault("APP_SECRET_KEY", "test-secret-with-sufficient-length")
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

from sqlalchemy import select

from provisao_api.db import Base, SessionLocal, engine
from provisao_api.models import (Company, User, WorkflowActionExecution,
    WorkflowDefinition, WorkflowInstance, WorkflowState, WorkflowTransition,
    WorkflowVersion)
from provisao_api.services.workflow import (WorkflowError, clone_version,
    create_definition, evaluate_condition, execute_transition, publish_version,
    start_instance, validate_graph)


class WorkflowEngineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(engine)

    def setUp(self):
        self.db = SessionLocal()
        self.company = Company(name=f"Workflow {uuid.uuid4()}")
        self.db.add(self.company); self.db.flush()
        self.user = User(company_id=self.company.id, name="Supervisor", email=f"wf-{uuid.uuid4()}@example.test", password_hash="unused")
        self.db.add(self.user); self.db.commit()

    def tearDown(self):
        self.db.rollback(); self.db.close()

    def make_valid_workflow(self):
        definition, version = create_definition(self.db, company_id=self.company.id, code=f"test-{uuid.uuid4()}", name="Fluxo", description=None, entity_type="service_order", actor_id=self.user.id)
        initial = WorkflowState(workflow_version_id=version.id, code="intake", name="Recepção", category="intake", is_initial=True, position=0)
        final = WorkflowState(workflow_version_id=version.id, code="done", name="Concluído", category="closed", is_terminal=True, is_public=True, position=1)
        self.db.add_all([initial, final]); self.db.flush()
        transition = WorkflowTransition(workflow_version_id=version.id, code="complete", name="Concluir", from_state_id=initial.id, to_state_id=final.id, required_permission="workflow.execute", requires_reason=True, conditions={"equals":{"field":"approved","value":True}}, actions=[{"type":"audit","params":{"event":"completed"}}])
        self.db.add(transition); self.db.flush()
        return definition, version, initial, final, transition

    def test_graph_validation_rejects_missing_initial_and_unreachable_state(self):
        _, version = create_definition(self.db, company_id=self.company.id, code=f"invalid-{uuid.uuid4()}", name="Inválido", description=None, entity_type="service_order", actor_id=self.user.id)
        self.db.add(WorkflowState(workflow_version_id=version.id, code="orphan", name="Órfão", category="technical")); self.db.flush()
        errors = validate_graph(self.db, version)
        self.assertTrue(any("exactly one initial" in error for error in errors))
        with self.assertRaises(WorkflowError): publish_version(self.db, version, self.user.id)

    def test_publish_is_immutable_and_clone_preserves_old_instances(self):
        _, version, _, _, _ = self.make_valid_workflow(); publish_version(self.db, version, self.user.id)
        instance = start_instance(self.db, company_id=self.company.id, workflow_version=version, entity_type="service_order", entity_id=str(uuid.uuid4()), actor_id=self.user.id)
        with self.assertRaises(WorkflowError):
            from provisao_api.services.workflow import ensure_draft
            ensure_draft(version)
        clone = clone_version(self.db, version, self.user.id)
        self.assertEqual(clone.version_number, 2); self.assertEqual(clone.status, "draft")
        self.assertEqual(instance.workflow_version_id, version.id)
        self.assertEqual(self.db.scalar(select(WorkflowState).where(WorkflowState.workflow_version_id == clone.id, WorkflowState.code == "intake")).name, "Recepção")

    def test_instance_condition_permission_action_and_history(self):
        _, version, _, final, transition = self.make_valid_workflow(); publish_version(self.db, version, self.user.id)
        instance = start_instance(self.db, company_id=self.company.id, workflow_version=version, entity_type="service_order", entity_id=str(uuid.uuid4()), actor_id=self.user.id)
        with self.assertRaises(WorkflowError): execute_transition(self.db, instance=instance, transition=transition, actor_id=self.user.id, permissions=set(), reason="ok", context={"approved":True})
        with self.assertRaises(WorkflowError): execute_transition(self.db, instance=instance, transition=transition, actor_id=self.user.id, permissions={"workflow.execute"}, reason="ok", context={"approved":False})
        event = execute_transition(self.db, instance=instance, transition=transition, actor_id=self.user.id, permissions={"workflow.execute"}, reason="Finalizado", context={"approved":True}, handlers={"audit":lambda session, workflow, params, context:{"event":params["event"]}})
        self.assertEqual(instance.current_state_id, final.id); self.assertEqual(instance.status, "completed")
        self.assertEqual(event.reason, "Finalizado")
        action = self.db.scalar(select(WorkflowActionExecution).where(WorkflowActionExecution.workflow_execution_event_id == event.id))
        self.assertEqual(action.status, "completed")
        self.assertTrue(evaluate_condition({"all":[{"exists":{"field":"asset.id","value":True}},{"greater_than":{"field":"score","value":5}}]}, {"asset":{"id":"x"},"score":6}))

    def test_instance_start_is_idempotent(self):
        _, version, _, _, _ = self.make_valid_workflow(); publish_version(self.db, version, self.user.id)
        entity_id = str(uuid.uuid4())
        first = start_instance(self.db, company_id=self.company.id, workflow_version=version, entity_type="service_order", entity_id=entity_id, actor_id=self.user.id)
        second = start_instance(self.db, company_id=self.company.id, workflow_version=version, entity_type="service_order", entity_id=entity_id, actor_id=self.user.id)
        self.assertEqual(first.id, second.id)
        self.assertEqual(self.db.query(WorkflowInstance).filter_by(entity_id=entity_id).count(), 1)


if __name__ == "__main__":
    unittest.main()
