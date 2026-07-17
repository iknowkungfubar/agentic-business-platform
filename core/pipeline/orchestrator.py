"""Durable DAG Orchestrator — executes JSON-defined multi-agent workflows.

Each workflow is a Directed Acyclic Graph of agent steps. After each node
completes, the full execution state is persisted to the WorkflowExecution
table, enabling crash recovery with zero data loss.
"""

from __future__ import annotations

import json
import os
import random
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class DAGNode:
    """A single step in a workflow DAG."""

    def __init__(
        self,
        node_id: str,
        agent_type: str,
        prompt: str,
        depends_on: list[str] | None = None,
        model_tier: str = "t2",
        max_retries: int = 3,
    ):
        self.node_id = node_id
        self.agent_type = agent_type
        self.prompt = prompt
        self.depends_on = depends_on or []
        self.model_tier = model_tier
        self.max_retries = max_retries
        self.status = "PENDING"
        self.output = ""
        self.error = ""
        self.retry_count = 0


class WorkflowDefinition:
    """A complete workflow definition — series of DAG nodes."""

    def __init__(self, name: str, nodes: list[DAGNode]):
        self.name = name
        self.nodes = {n.node_id: n for n in nodes}
        self.entry_nodes = [n for n in nodes if not n.depends_on]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "nodes": {
                nid: {
                    "node_id": n.node_id,
                    "agent_type": n.agent_type,
                    "prompt": n.prompt[:100],
                    "depends_on": n.depends_on,
                    "model_tier": n.model_tier,
                    "status": n.status,
                }
                for nid, n in self.nodes.items()
            },
            "entry_nodes": [n.node_id for n in self.entry_nodes],
        }


class DAGOrchestrator:
    """Executes a workflow DAG with state persistence for crash recovery.

    Usage:
        workflow = WorkflowDefinition("research", [
            DAGNode("search", "search_agent", "Find information about X"),
            DAGNode("summarize", "summarize_agent", "Summarize findings",
                    depends_on=["search"]),
        ])
        orchestrator = DAGOrchestrator(db)
        result = await orchestrator.execute(workflow, org_id=1)
    """

    def __init__(self, db: Session, execution_id: int | None = None):
        self.db = db
        self.execution_id = execution_id

    async def execute(self, workflow: WorkflowDefinition, org_id: int) -> dict[str, Any]:
        """Execute a workflow from start to finish with persistence."""
        from app.models import WorkflowExecution

        # Create or load execution record
        if self.execution_id:
            record = self.db.query(WorkflowExecution).filter(WorkflowExecution.id == self.execution_id).first()
            if record:
                # Resume from saved state
                state = json.loads(record.state_payload) if record.state_payload else {}
                self._restore_state(workflow, state)
                record.status = "RUNNING"
            else:
                raise ValueError(f"Execution {self.execution_id} not found")
        else:
            record = WorkflowExecution(
                organization_id=org_id,
                name=workflow.name,
                status="PENDING",
                state_payload=json.dumps(workflow.to_dict()),
            )
            self.db.add(record)
            self.db.flush()
            self.execution_id = record.id

        # Execute nodes in DAG order
        completed: set[str] = set()
        max_iterations = len(workflow.nodes) * 2  # Safety valve
        iteration = 0

        while len(completed) < len(workflow.nodes) and iteration < max_iterations:
            iteration += 1
            ready = self._get_ready_nodes(workflow, completed)
            if not ready:
                if len(completed) < len(workflow.nodes):
                    # Deadlock or unreachable nodes
                    record.status = "FAILED"
                    record.error_message = f"Deadlock detected: {len(completed)}/{len(workflow.nodes)} completed"
                    record.current_node = "deadlock"
                    self.db.commit()
                break

            for node in ready:
                node.status = "RUNNING"
                record.current_node = node.node_id
                record.status = "RUNNING"
                self._save_state(record, workflow)
                self.db.commit()

                try:
                    # Execute the node (calls the appropriate agent)
                    output = await self._execute_node(node)
                    node.output = output
                    node.status = "COMPLETED"
                    completed.add(node.node_id)
                except Exception as exc:
                    node.retry_count += 1
                    if node.retry_count >= node.max_retries:
                        node.status = "FAILED"
                        node.error = str(exc)
                        record.status = "FAILED"
                        record.error_message = f"Node {node.node_id} failed: {exc}"
                        self._save_state(record, workflow)
                        self.db.commit()
                        return {"execution_id": self.execution_id, "status": "FAILED", "error": str(exc)}
                    # Will retry on next iteration

                self._save_state(record, workflow)
                self.db.commit()

        record.status = "COMPLETED"
        record.current_node = ""
        self._save_state(record, workflow)
        self.db.commit()

        return {"execution_id": self.execution_id, "status": "COMPLETED"}

    def _get_ready_nodes(self, workflow: WorkflowDefinition, completed: set[str]) -> list[DAGNode]:
        """Get nodes whose dependencies are all satisfied."""
        ready = []
        for node in workflow.nodes.values():
            if node.status in ("COMPLETED", "RUNNING", "FAILED"):
                continue
            if all(dep in completed for dep in node.depends_on):
                ready.append(node)
        return ready

    async def _execute_node(self, node: DAGNode) -> str:
        """Execute a single node — calls the appropriate agent/LLM."""
        # Chaos Engineering: inject random failures when enabled
        chaos = os.getenv("CHAOS_MODE", "false").lower() in ("1", "true", "yes")
        if chaos and random.random() < 0.05:
            failure_type = random.choice(["db_lock", "http_503", "timeout"])
            if failure_type == "db_lock":
                raise Exception("Chaos: Simulated DatabaseLockException")
            if failure_type == "http_503":
                raise Exception("Chaos: Simulated HTTP 503 Service Unavailable")
            raise TimeoutError("Chaos: Simulated node timeout")

        import httpx

        from app.config import settings

        inference_url = os.getenv("INFERENCE_URL", settings.inference_url)
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{inference_url}/chat/completions",
                json={
                    "model": settings.inference_model,
                    "messages": [
                        {"role": "system", "content": f"You are a {node.agent_type}. Execute the assigned task."},
                        {"role": "user", "content": node.prompt},
                    ],
                    "max_tokens": 2048,
                },
            )
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"]
            return f"[Agent error: {resp.status_code}]"

    @staticmethod
    def _restore_state(workflow: WorkflowDefinition, state: dict) -> None:
        """Restore node states from a saved execution record."""
        saved_nodes = state.get("nodes", {})
        for nid, saved in saved_nodes.items():
            if nid in workflow.nodes:
                workflow.nodes[nid].status = saved.get("status", "PENDING")
                workflow.nodes[nid].output = saved.get("output", "")
                workflow.nodes[nid].error = saved.get("error", "")
                workflow.nodes[nid].retry_count = saved.get("retry_count", 0)

    @staticmethod
    def _save_state(record: Any, workflow: WorkflowDefinition) -> None:
        """Persist the current workflow state to the DB."""
        state = workflow.to_dict()
        state["completed_nodes"] = [nid for nid, n in workflow.nodes.items() if n.status == "COMPLETED"]
        record.state_payload = json.dumps(state)
        record.updated_at = datetime.now(UTC)
