"""Tests for generating script from trajectory and saving to ScriptStore."""
import os
import tempfile

import pytest

from zerotoken.controller import OperationRecord, PageState
from zerotoken.engine.script_generator import trajectory_to_script, save_script_from_trajectory
from zerotoken.storage_sqlite import SQLiteStorage
from zerotoken.trajectory import Trajectory, TrajectoryRecorder


@pytest.fixture
def db_path():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    try:
        os.unlink(path)
    except OSError:
        pass


def test_trajectory_to_script_includes_selector_candidates():
    """trajectory_to_script produces steps with selector_candidates from operations."""
    trajectory_data = {
        "task_id": "gen_1",
        "goal": "Test",
        "operations": [
            {"step": 1, "action": "open", "params": {"url": "https://a.com"}},
            {
                "step": 2,
                "action": "click",
                "params": {"selector": "#btn"},
                "selector_candidates": [
                    {"type": "css", "value": "#btn"},
                    {"type": "test_id", "value": "[data-testid=submit]"},
                ],
            },
        ],
    }
    script = trajectory_to_script(trajectory_data, prepend_init=True)
    assert script["task_id"] == "gen_1"
    assert script["goal"] == "Test"
    # browser_init, trajectory_start, browser_open, browser_click
    assert len(script["steps"]) == 4
    assert script["steps"][2]["action"] == "browser_open"
    assert script["steps"][3]["action"] == "browser_click"
    assert script["steps"][3].get("selector_candidates") == [
        {"type": "css", "value": "#btn"},
        {"type": "test_id", "value": "[data-testid=submit]"},
    ]


def test_save_script_from_trajectory_then_load_has_selector_candidates(db_path):
    """Save trajectory to DB, generate script to ScriptStore, script_load returns steps with selector_candidates."""
    store = SQLiteStorage(db_path)
    # Save trajectory with selector_candidates
    traj_id = store.trajectory_save(
        task_id="task_script_1",
        goal="Goal",
        operations=[
            {"step": 1, "action": "open", "params": {"url": "https://x.com"}},
            {
                "step": 2,
                "action": "click",
                "params": {"selector": "#ok"},
                "selector_candidates": [{"type": "css", "value": "#ok"}],
            },
        ],
        metadata={},
    )
    loaded_traj = store.trajectory_load(traj_id)
    assert loaded_traj is not None
    save_script_from_trajectory(loaded_traj, store, prepend_init=False)
    script = store.script_load("task_script_1")
    assert script is not None
    assert len(script["steps"]) == 2
    assert script["steps"][1]["selector_candidates"] == [{"type": "css", "value": "#ok"}]
