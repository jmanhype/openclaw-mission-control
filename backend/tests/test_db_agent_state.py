from __future__ import annotations

from uuid import uuid4

from app.models.agents import Agent
from app.services.openclaw.db_agent_state import mark_provision_complete
from app.services.openclaw.provisioning_db import AgentLifecycleService


def test_mark_provision_complete_sets_last_seen_for_online_agent() -> None:
    agent = Agent(name="Riley Gateway Agent", gateway_id=uuid4())

    mark_provision_complete(agent, status="online")

    assert agent.status == "online"
    assert agent.provision_requested_at is None
    assert agent.provision_action is None
    assert agent.last_seen_at is not None
    assert AgentLifecycleService.with_computed_status(agent).status == "online"


def test_mark_provision_complete_leaves_last_seen_empty_for_non_online_status() -> None:
    agent = Agent(name="Riley Gateway Agent", gateway_id=uuid4())

    mark_provision_complete(agent, status="offline")

    assert agent.status == "offline"
    assert agent.last_seen_at is None
