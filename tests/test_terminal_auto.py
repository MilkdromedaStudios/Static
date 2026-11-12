"""Terminal auto-mode regression tests using an isolated fake client."""

from unittest.mock import AsyncMock

import pytest

from static_ai.terminal import Terminal


@pytest.mark.asyncio
async def test_auto_mode_requires_exact_confirmation(tmp_path):
    terminal = Terminal(AsyncMock(), tmp_path, "economy")
    terminal.session = AsyncMock()
    terminal.session.prompt_async.return_value = "no"
    await terminal.command("/auto on")
    assert terminal.auto_approve is False
    terminal.session.prompt_async.return_value = "AUTO APPROVE"
    await terminal.command("/auto on")
    assert terminal.auto_approve is True
    await terminal.command("/auto off")
    assert terminal.auto_approve is False


@pytest.mark.asyncio
async def test_continuous_mode_requires_spending_cap_and_confirmation(tmp_path):
    terminal = Terminal(AsyncMock(), tmp_path, "economy")
    terminal.session = AsyncMock()
    terminal.session.prompt_async.side_effect = ["10", "CONTINUE"]
    await terminal.command("/continuous on")
    assert terminal.continuous is True
    assert terminal.continuous_limit == 10.0
    await terminal.command("/continuous off")
    assert terminal.continuous is False


@pytest.mark.asyncio
async def test_continuous_rejects_invalid_cap(tmp_path):
    terminal = Terminal(AsyncMock(), tmp_path, "economy")
    terminal.session = AsyncMock()
    terminal.session.prompt_async.return_value = "10000"
    await terminal.command("/continuous on")
    assert terminal.continuous is False
