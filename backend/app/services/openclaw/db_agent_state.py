"""Shared DB mutation helpers for OpenClaw agent lifecycle services."""

from __future__ import annotations

from typing import Any, Literal

from app.core.agent_tokens import generate_agent_token, hash_agent_token
from app.core.time import utcnow
from app.models.agents import Agent
from app.services.openclaw.constants import DEFAULT_HEARTBEAT_CONFIG


def resolve_heartbeat_config(
    *,
    board_id: object | None,
    is_board_lead: bool,
    raw: dict[str, Any] | None,
) -> dict[str, Any]:
    """Return a normalized heartbeat config for Mission Control-managed agents.

    Board-scoped agents are internal operators, not chat-facing assistants. When their
    heartbeat target is left at the generic default of ``last``, OpenClaw can end up
    trying to deliver to the synthetic ``heartbeat`` channel and reject the run. Keep
    those agents internal-only unless an explicit real channel target was configured.
    """

    heartbeat = DEFAULT_HEARTBEAT_CONFIG.copy()
    if isinstance(raw, dict):
        heartbeat.update(raw)
    if (board_id is not None or is_board_lead) and heartbeat.get("target") in {None, "", "last"}:
        heartbeat["target"] = "none"
    return heartbeat


def ensure_heartbeat_config(agent: Agent) -> None:
    """Ensure an agent has a heartbeat_config dict populated."""

    agent.heartbeat_config = resolve_heartbeat_config(
        board_id=agent.board_id,
        is_board_lead=agent.is_board_lead,
        raw=agent.heartbeat_config if isinstance(agent.heartbeat_config, dict) else None,
    )


def mint_agent_token(agent: Agent) -> str:
    """Generate a new raw token and update the agent's token hash."""

    raw_token = generate_agent_token()
    agent.agent_token_hash = hash_agent_token(raw_token)
    return raw_token


def mark_provision_requested(
    agent: Agent,
    *,
    action: str,
    status: str | None = None,
) -> None:
    """Mark an agent as pending provisioning/update."""

    ensure_heartbeat_config(agent)
    agent.provision_requested_at = utcnow()
    agent.provision_action = action
    if status is not None:
        agent.status = status
    agent.updated_at = utcnow()


def mark_provision_complete(
    agent: Agent,
    *,
    status: Literal["online", "offline", "provisioning", "updating", "deleting"] = "online",
    clear_confirm_token: bool = False,
) -> None:
    """Clear provisioning fields after a successful gateway lifecycle run."""

    now = utcnow()
    if clear_confirm_token:
        agent.provision_confirm_token_hash = None
    agent.status = status
    if status == "online" and agent.last_seen_at is None:
        agent.last_seen_at = now
    agent.provision_requested_at = None
    agent.provision_action = None
    agent.updated_at = now


def mark_provision_failed(
    agent: Agent,
    *,
    previous_status: str,
) -> None:
    """Clear pending lifecycle state after a failed gateway lifecycle attempt."""

    agent.status = previous_status
    agent.provision_requested_at = None
    agent.provision_action = None
    agent.updated_at = utcnow()
