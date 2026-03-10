"""Tests for ScriptEngine run_script with mock controller and SessionStore."""
import asyncio
import os
import tempfile
from typing import Any, Dict, Optional

import pytest

from zerotoken.engine.script_engine import ScriptEngine
from zerotoken.storage_sqlite import SQLiteStorage
from zerotoken.controller import OperationRecord, PageState


class MockController:
    """Minimal controller that records calls and returns success."""

    def __init__(self):
        self.calls = []
        self._page_url = "about:blank"

    async def start(self, headless: bool = True, **kwargs) -> None:
        self.calls.append(("start", {"headless": headless, **kwargs}))

    async def open(self, url: str, **kwargs) -> OperationRecord:
        self.calls.append(("open", {"url": url}))
        self._page_url = url
        return OperationRecord(
            step=1,
            action="open",
            params={"url": url},
            result={"success": True},
            page_state=PageState(url=url, title=""),
        )

    async def click(self, selector: str, **kwargs) -> OperationRecord:
        self.calls.append(("click", {"selector": selector}))
        return OperationRecord(
            step=2,
            action="click",
            params={"selector": selector},
            result={"success": True},
            page_state=PageState(url=self._page_url, title=""),
        )


@pytest.fixture
def db_path():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    try:
        os.unlink(path)
    except OSError:
        pass


@pytest.fixture
def session_store(db_path):
    return SQLiteStorage(db_path)


@pytest.mark.asyncio
async def test_run_script_executes_open_and_click_writes_session(session_store):
    """Script with browser_open + browser_click runs and writes steps to SessionStore."""
    script = {
        "task_id": "test_run_1",
        "goal": "Open and click",
        "steps": [
            {"action": "browser_open", "params": {"url": "https://example.com"}},
            {"action": "browser_click", "params": {"selector": "#submit"}},
        ],
    }
    controller = MockController()
    engine = ScriptEngine(vars_map={})
    result = await engine.run_script(script, controller, session_store)
    assert result["success"] is True
    assert "session_id" in result
    session_id = result["session_id"]
    steps = session_store.session_get(session_id)
    assert len(steps) == 2
    assert steps[0]["action"] == "open"
    assert steps[0]["url"] == "https://example.com"
    assert steps[1]["action"] == "click"
    assert steps[1]["selector"] == "#submit"
    assert len(controller.calls) == 2
    assert controller.calls[0][0] == "open"
    assert controller.calls[1][0] == "click"
