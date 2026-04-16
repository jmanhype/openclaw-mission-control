# ruff: noqa: INP001
"""Regression tests for parsing OpenClaw CLI JSON output."""

from __future__ import annotations

from app.services.openclaw.gateway_rpc import _parse_cli_json_output


def test_parse_cli_json_output_accepts_plain_json() -> None:
    result = _parse_cli_json_output('{"ok":true,"result":{"id":"demo"}}')

    assert result == {"ok": True, "result": {"id": "demo"}}


def test_parse_cli_json_output_accepts_prefixed_text_with_json_line() -> None:
    output = "Config overwrite: /tmp/openclaw.json\n{\"ok\":true,\"result\":{\"id\":\"demo\"}}"

    result = _parse_cli_json_output(output)

    assert result == {"ok": True, "result": {"id": "demo"}}
