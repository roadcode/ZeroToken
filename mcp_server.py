"""
ZeroToken MCP Server - Enhanced for AI Agent with structured operation records.
Exposes browser automation tools via MCP protocol with detailed trajectory capture.
"""

import asyncio
import json
import os
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from zerotoken.controller import BrowserController
from zerotoken.trajectory import TrajectoryRecorder
from zerotoken.storage_sqlite import SQLiteStorage
from zerotoken.engine import ScriptEngine, save_script_from_trajectory


# 创建 MCP 服务器
server = Server("zerotoken")

# 全局状态
_controller = None
_trajectory_recorder = None
_current_trajectory = None
_storage = None


def _base_dir() -> str:
    return os.path.dirname(os.path.abspath(__file__))


def get_storage() -> SQLiteStorage:
    """Get or create global SQLite storage (scripts, trajectories, sessions)."""
    global _storage
    if _storage is None:
        db_path = os.environ.get("ZEROTOKEN_DB") or os.path.join(_base_dir(), "zerotoken.db")
        _storage = SQLiteStorage(db_path)
    return _storage


def get_controller() -> BrowserController:
    """Get or create global browser controller."""
    global _controller
    if _controller is None:
        _controller = BrowserController()
        _controller.set_adaptive_store(get_storage())
    return _controller


def get_trajectory_recorder() -> TrajectoryRecorder:
    """Get or create global trajectory recorder."""
    global _trajectory_recorder
    if _trajectory_recorder is None:
        _trajectory_recorder = TrajectoryRecorder(trajectory_store=get_storage())
        _trajectory_recorder.bind_controller(get_controller())
    return _trajectory_recorder


# 定义可用工具
@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="browser_open",
            description="Open a URL in the browser and return detailed operation record",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The URL to open"},
                    "wait_until": {"type": "string", "description": "Wait condition (load, domcontentloaded, networkidle, commit)", "default": "networkidle"},
                    "record_trajectory": {"type": "boolean", "description": "Whether to record this operation to trajectory", "default": True},
                    "include_screenshot": {"type": "boolean", "description": "Include screenshot in response (set false to reduce token)", "default": True}
                },
                "required": ["url"]
            }
        ),
        Tool(
            name="browser_click",
            description="Click an element and return detailed operation record with page state",
            inputSchema={
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "CSS selector of the element to click"},
                    "timeout": {"type": "integer", "description": "Timeout in milliseconds", "default": 30000},
                    "wait_after": {"type": "number", "description": "Seconds to wait after click", "default": 0.5},
                    "record_trajectory": {"type": "boolean", "description": "Whether to record this operation", "default": True},
                    "include_screenshot": {"type": "boolean", "description": "Include screenshot in response (set false to reduce token)", "default": True},
                    "auto_save": {"type": "boolean", "description": "Save element fingerprint for adaptive relocation when selector works", "default": False},
                    "adaptive": {"type": "boolean", "description": "If selector fails, relocate element by stored fingerprint", "default": False},
                    "identifier": {"type": "string", "description": "Optional key for stored fingerprint (default: selector)"}
                },
                "required": ["selector"]
            }
        ),
        Tool(
            name="browser_input",
            description="Type text into an input field and return detailed operation record",
            inputSchema={
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "CSS selector of the input field"},
                    "text": {"type": "string", "description": "Text to type"},
                    "delay": {"type": "integer", "description": "Delay between keystrokes (ms)", "default": 50},
                    "clear_first": {"type": "boolean", "description": "Clear existing value before typing", "default": True},
                    "record_trajectory": {"type": "boolean", "description": "Whether to record this operation", "default": True},
                    "include_screenshot": {"type": "boolean", "description": "Include screenshot in response (set false to reduce token)", "default": True},
                    "auto_save": {"type": "boolean", "description": "Save element fingerprint for adaptive relocation", "default": False},
                    "adaptive": {"type": "boolean", "description": "If selector fails, relocate by stored fingerprint", "default": False},
                    "identifier": {"type": "string", "description": "Optional key for stored fingerprint (default: selector)"}
                },
                "required": ["selector", "text"]
            }
        ),
        Tool(
            name="browser_get_text",
            description="Extract text or attribute from an element with detailed result",
            inputSchema={
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "CSS selector of the element"},
                    "attr": {"type": "string", "description": "Attribute to extract (text, html, value, innerText)", "default": "text"},
                    "record_trajectory": {"type": "boolean", "description": "Whether to record this operation", "default": True},
                    "include_screenshot": {"type": "boolean", "description": "Include screenshot in response (set false to reduce token)", "default": True},
                    "auto_save": {"type": "boolean", "description": "Save element fingerprint for adaptive relocation", "default": False},
                    "adaptive": {"type": "boolean", "description": "If selector fails, relocate by stored fingerprint", "default": False},
                    "identifier": {"type": "string", "description": "Optional key for stored fingerprint (default: selector)"}
                },
                "required": ["selector"]
            }
        ),
        Tool(
            name="browser_get_html",
            description="Get HTML content of page or element",
            inputSchema={
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "CSS selector (omit for full page HTML)"},
                    "record_trajectory": {"type": "boolean", "description": "Whether to record this operation", "default": True},
                    "include_screenshot": {"type": "boolean", "description": "Include screenshot in response (set false to reduce token)", "default": True},
                    "auto_save": {"type": "boolean", "description": "Save element fingerprint for adaptive relocation (when selector set)", "default": False},
                    "adaptive": {"type": "boolean", "description": "If selector fails, relocate by stored fingerprint", "default": False},
                    "identifier": {"type": "string", "description": "Optional key for stored fingerprint (default: selector)"}
                }
            }
        ),
        Tool(
            name="browser_screenshot",
            description="Take a screenshot and return image data with page state",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to save the screenshot (optional)"},
                    "full_page": {"type": "boolean", "description": "Capture full page", "default": False},
                    "selector": {"type": "string", "description": "CSS selector to capture specific element"},
                    "record_trajectory": {"type": "boolean", "description": "Whether to record this operation", "default": True}
                }
            }
        ),
        Tool(
            name="browser_wait_for",
            description="Wait for a condition (selector, url, text, navigation)",
            inputSchema={
                "type": "object",
                "properties": {
                    "condition": {"type": "string", "description": "Type of condition (selector, url, text, navigation)"},
                    "value": {"type": "string", "description": "Condition value"},
                    "timeout": {"type": "integer", "description": "Timeout in milliseconds", "default": 30000},
                    "record_trajectory": {"type": "boolean", "description": "Whether to record this operation", "default": True},
                    "include_screenshot": {"type": "boolean", "description": "Include screenshot in response (set false to reduce token)", "default": True}
                },
                "required": ["condition"]
            }
        ),
        Tool(
            name="browser_extract_data",
            description="Extract structured data based on schema (AI-node capable)",
            inputSchema={
                "type": "object",
                "properties": {
                    "schema": {
                        "type": "object",
                        "description": "Data extraction schema",
                        "properties": {
                            "fields": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "selector": {"type": "string"},
                                        "type": {"type": "string"}
                                    }
                                }
                            }
                        }
                    },
                    "include_screenshot": {"type": "boolean", "description": "Include screenshot in response (set false to reduce token)", "default": True}
                },
                "required": ["schema"]
            }
        ),
        Tool(
            name="trajectory_start",
            description="Start a new trajectory recording for a task",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "Unique task identifier"},
                    "goal": {"type": "string", "description": "Natural language description of the task goal"}
                },
                "required": ["task_id", "goal"]
            }
        ),
        Tool(
            name="trajectory_complete",
            description="Complete the current trajectory and get AI-ready prompt",
            inputSchema={
                "type": "object",
                "properties": {
                    "export_for_ai": {"type": "boolean", "description": "Export trajectory in AI-optimized format", "default": True}
                }
            }
        ),
        Tool(
            name="trajectory_get",
            description="Get the current trajectory operations",
            inputSchema={
                "type": "object",
                "properties": {
                    "format": {"type": "string", "description": "Output format (json, ai_prompt)", "default": "json"}
                }
            }
        ),
        Tool(
            name="trajectory_list",
            description="List saved trajectories (for later loading via trajectory_load)",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Max number of trajectories to return", "default": 20},
                    "since": {"type": "number", "description": "Optional: only return trajectories saved at or after this Unix timestamp"}
                }
            }
        ),
        Tool(
            name="trajectory_load",
            description="Load the latest saved trajectory by task_id (not by id) for script generation or analysis",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "Task ID of the saved trajectory"},
                    "format": {"type": "string", "description": "Output format: ai_prompt or json", "default": "ai_prompt", "enum": ["ai_prompt", "json"]}
                },
                "required": ["task_id"]
            }
        ),
        Tool(
            name="trajectory_delete",
            description="Delete saved trajectories by task_id to avoid too many records",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "Task ID of the trajectory to delete"}
                },
                "required": ["task_id"]
            }
        ),
        Tool(
            name="trajectory_to_script",
            description="Convert a saved trajectory to script and save to MCP database. Use task_id to load trajectory.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "Task ID of the saved trajectory to convert"},
                    "script_task_id": {"type": "string", "description": "Optional script task_id (default: same as task_id)"},
                    "prepend_init": {"type": "boolean", "description": "Prepend browser_init and trajectory_start steps", "default": True},
                    "stealth": {"type": "boolean", "description": "Include stealth: true in browser_init for anti-bot sites", "default": False}
                },
                "required": ["task_id"]
            }
        ),
        Tool(
            name="script_save",
            description="Save a script to the MCP database (task_id, goal, steps). Overwrites if task_id exists.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "Task ID (script key)"},
                    "goal": {"type": "string", "description": "Goal description"},
                    "steps": {"type": "array", "description": "List of steps: {action, params, selector_candidates?, fuzzy_point?}"}
                },
                "required": ["task_id", "goal", "steps"]
            }
        ),
        Tool(
            name="script_list",
            description="List scripts in the MCP database.",
            inputSchema={
                "type": "object",
                "properties": {"limit": {"type": "integer", "description": "Max number to return", "default": 100}}
            }
        ),
        Tool(
            name="script_load",
            description="Load a script by task_id from the MCP database.",
            inputSchema={
                "type": "object",
                "properties": {"task_id": {"type": "string", "description": "Task ID"}},
                "required": ["task_id"]
            }
        ),
        Tool(
            name="script_delete",
            description="Delete a script by task_id from the MCP database.",
            inputSchema={
                "type": "object",
                "properties": {"task_id": {"type": "string"}},
                "required": ["task_id"]
            }
        ),
        Tool(
            name="run_script",
            description="Run a script (start) or resume a paused session (deterministic replay). Writes session to DB.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "Start mode: task_id of the script (mutually exclusive with session_id)"},
                    "vars": {"type": "object", "description": "Start mode: optional map of {{varname}} replacements"},
                    "session_id": {"type": "string", "description": "Resume mode: session_id to resume (mutually exclusive with task_id)"},
                    "resolution": {"type": "object", "description": "Resume mode: resolution object {type, note?, patch?}"}
                }
            }
        ),
        Tool(
            name="run_script_by_job_id",
            description="Run a script by binding_key (e.g. OpenClaw job_id). Looks up script_task_id and default_vars, merges with vars, then executes. One-step for scheduled tasks.",
            inputSchema={
                "type": "object",
                "properties": {
                    "binding_key": {"type": "string", "description": "External job identifier (e.g. OpenClaw job_id)"},
                    "vars": {"type": "object", "description": "Optional vars to merge with binding default_vars (overrides defaults)"}
                },
                "required": ["binding_key"]
            }
        ),
        Tool(
            name="dfu_save",
            description="Save a DFU (Dynamic Fuzzy Unit) to the MCP database. Overwrites if dfu_id exists.",
            inputSchema={
                "type": "object",
                "properties": {
                    "dfu_id": {"type": "string", "description": "DFU ID (key)"},
                    "name": {"type": "string", "description": "DFU name"},
                    "description": {"type": "string", "description": "Optional description", "default": ""},
                    "triggers": {"type": "array", "description": "Trigger rules (declarative JSON), exact match only"},
                    "prompt": {"type": "string", "description": "Prompt shown to orchestrator", "default": ""},
                    "allowed_resolutions": {"type": "array", "description": "Allowed resolution types", "items": {"type": "string"}}
                },
                "required": ["dfu_id", "name", "triggers"]
            }
        ),
        Tool(
            name="dfu_list",
            description="List DFUs from the MCP database.",
            inputSchema={
                "type": "object",
                "properties": {"limit": {"type": "integer", "default": 100}}
            }
        ),
        Tool(
            name="dfu_load",
            description="Load a DFU by dfu_id from the MCP database.",
            inputSchema={
                "type": "object",
                "properties": {"dfu_id": {"type": "string"}},
                "required": ["dfu_id"]
            }
        ),
        Tool(
            name="dfu_delete",
            description="Delete a DFU by dfu_id from the MCP database.",
            inputSchema={
                "type": "object",
                "properties": {"dfu_id": {"type": "string"}},
                "required": ["dfu_id"]
            }
        ),
        Tool(
            name="session_list",
            description="List sessions from the MCP database.",
            inputSchema={
                "type": "object",
                "properties": {"limit": {"type": "integer", "default": 100}}
            }
        ),
        Tool(
            name="session_get",
            description="Get session steps by session_id.",
            inputSchema={
                "type": "object",
                "properties": {"session_id": {"type": "string"}},
                "required": ["session_id"]
            }
        ),
        Tool(
            name="script_binding_set",
            description="Bind an external job_id (binding_key) to a script task_id, with optional default vars and description.",
            inputSchema={
                "type": "object",
                "properties": {
                    "binding_key": {"type": "string", "description": "External job identifier (e.g. OpenClaw job_id)"},
                    "script_task_id": {"type": "string", "description": "ZeroToken script task_id"},
                    "description": {"type": "string", "description": "Optional human-readable description"},
                    "default_vars": {"type": "object", "description": "Optional default vars for this binding"}
                },
                "required": ["binding_key", "script_task_id"]
            }
        ),
        Tool(
            name="script_binding_get",
            description="Get a script binding by binding_key (job_id).",
            inputSchema={
                "type": "object",
                "properties": {"binding_key": {"type": "string"}},
                "required": ["binding_key"]
            }
        ),
        Tool(
            name="script_binding_list",
            description="List script bindings.",
            inputSchema={
                "type": "object",
                "properties": {"limit": {"type": "integer", "default": 100}}
            }
        ),
        Tool(
            name="script_binding_delete",
            description="Delete a script binding by binding_key.",
            inputSchema={
                "type": "object",
                "properties": {"binding_key": {"type": "string"}},
                "required": ["binding_key"]
            }
        ),
        Tool(
            name="browser_init",
            description="Initialize the browser (call once before using other browser tools). Use stealth=True to reduce automation detection (launch args + fingerprint masking).",
            inputSchema={
                "type": "object",
                "properties": {
                    "headless": {"type": "boolean", "description": "Run in headless mode", "default": True},
                    "viewport_width": {"type": "integer", "description": "Viewport width", "default": 1920},
                    "viewport_height": {"type": "integer", "description": "Viewport height", "default": 1080},
                    "stealth": {"type": "boolean", "description": "Enable stealth mode: hide automation flags and mask fingerprint", "default": False}
                }
            }
        ),
        Tool(
            name="browser_close",
            description="Close the browser and cleanup resources",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
    ]


def _error_response(
    error: str,
    code: str | None = None,
    retryable: bool | None = None,
    hint: str | None = None,
) -> str:
    """Build structured error JSON for MCP tools."""
    out = {"success": False, "error": error}
    if code is not None:
        out["code"] = code
    if retryable is not None:
        out["retryable"] = retryable
    if hint is not None:
        out["hint"] = hint
    return json.dumps(out, indent=2, ensure_ascii=False)


def _format_operation_record(record, include_screenshot: bool = True) -> str:
    """Format operation record as JSON string. If include_screenshot is False, omit screenshot to reduce payload."""
    d = record.to_dict()
    if not include_screenshot:
        d.pop("screenshot", None)
    return json.dumps(d, indent=2, ensure_ascii=False)


# 工具执行处理
@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    global _current_trajectory

    controller = get_controller()
    recorder = get_trajectory_recorder()
    record_trajectory = arguments.pop("record_trajectory", True)
    include_screenshot = arguments.pop("include_screenshot", True)

    try:
        if name == "browser_init":
            headless = arguments.get("headless", True)
            viewport = {
                "width": arguments.get("viewport_width", 1920),
                "height": arguments.get("viewport_height", 1080)
            }
            stealth = arguments.get("stealth", False)
            await controller.start(headless=headless, viewport=viewport, stealth=stealth)
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": True,
                    "message": "Browser initialized",
                    "config": controller.get_config()
                }, indent=2)
            )]

        elif name == "browser_close":
            await controller.stop()
            return [TextContent(
                type="text",
                text=json.dumps({"success": True, "message": "Browser closed"}, indent=2)
            )]

        elif name == "browser_open":
            url = arguments["url"]
            wait_until = arguments.get("wait_until", "networkidle")
            record = await controller.open(url, wait_until=wait_until)
            if record_trajectory:
                recorder.ensure_current_trajectory()
                recorder.record_operation(record)
            return [TextContent(
                type="text",
                text=_format_operation_record(record, include_screenshot)
            )]

        elif name == "browser_click":
            selector = arguments["selector"]
            timeout = arguments.get("timeout")
            wait_after = arguments.get("wait_after", 0.5)
            auto_save = arguments.get("auto_save", False)
            adaptive = arguments.get("adaptive", False)
            identifier = arguments.get("identifier")
            record = await controller.click(
                selector, timeout=timeout, wait_after=wait_after,
                auto_save=auto_save, adaptive=adaptive, identifier=identifier
            )
            if record_trajectory:
                recorder.ensure_current_trajectory()
                recorder.record_operation(record)
            return [TextContent(
                type="text",
                text=_format_operation_record(record, include_screenshot)
            )]

        elif name == "browser_input":
            selector = arguments["selector"]
            text = arguments["text"]
            delay = arguments.get("delay", 50)
            clear_first = arguments.get("clear_first", True)
            auto_save = arguments.get("auto_save", False)
            adaptive = arguments.get("adaptive", False)
            identifier = arguments.get("identifier")
            record = await controller.input(
                selector, text, delay=delay, clear_first=clear_first,
                auto_save=auto_save, adaptive=adaptive, identifier=identifier
            )
            if record_trajectory:
                recorder.ensure_current_trajectory()
                recorder.record_operation(record)
            return [TextContent(
                type="text",
                text=_format_operation_record(record, include_screenshot)
            )]

        elif name == "browser_get_text":
            selector = arguments["selector"]
            attr = arguments.get("attr", "text")
            auto_save = arguments.get("auto_save", False)
            adaptive = arguments.get("adaptive", False)
            identifier = arguments.get("identifier")
            record = await controller.get_text(
                selector, attr=attr,
                auto_save=auto_save, adaptive=adaptive, identifier=identifier
            )
            if record_trajectory:
                recorder.ensure_current_trajectory()
                recorder.record_operation(record)
            return [TextContent(
                type="text",
                text=_format_operation_record(record, include_screenshot)
            )]

        elif name == "browser_get_html":
            selector = arguments.get("selector")
            auto_save = arguments.get("auto_save", False)
            adaptive = arguments.get("adaptive", False)
            identifier = arguments.get("identifier")
            record = await controller.get_html(
                selector=selector,
                auto_save=auto_save, adaptive=adaptive, identifier=identifier
            )
            if record_trajectory:
                recorder.ensure_current_trajectory()
                recorder.record_operation(record)
            return [TextContent(
                type="text",
                text=_format_operation_record(record, include_screenshot)
            )]

        elif name == "browser_screenshot":
            path = arguments.get("path")
            full_page = arguments.get("full_page", False)
            selector = arguments.get("selector")
            record = await controller.screenshot(path=path, full_page=full_page, selector=selector)
            if record_trajectory:
                recorder.ensure_current_trajectory()
                recorder.record_operation(record)
            # Don't include full screenshot data in response (too large)
            result = record.to_dict()
            if result.get("screenshot"):
                result["screenshot_preview"] = "base64 image data available"
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "browser_wait_for":
            condition = arguments["condition"]
            value = arguments.get("value")
            timeout = arguments.get("timeout")
            record = await controller.wait_for(condition, value, timeout=timeout)
            if record_trajectory:
                recorder.ensure_current_trajectory()
                recorder.record_operation(record)
            return [TextContent(
                type="text",
                text=_format_operation_record(record, include_screenshot)
            )]

        elif name == "browser_extract_data":
            schema = arguments["schema"]
            record = await controller.extract_data(schema)
            recorder.ensure_current_trajectory()
            recorder.record_operation(record)
            return [TextContent(
                type="text",
                text=_format_operation_record(record, include_screenshot)
            )]

        elif name == "trajectory_start":
            task_id = arguments["task_id"]
            goal = arguments["goal"]
            trajectory = recorder.start_trajectory(task_id, goal)
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": True,
                    "task_id": task_id,
                    "goal": goal,
                    "message": "Trajectory recording started"
                }, indent=2)
            )]

        elif name == "trajectory_complete":
            export_for_ai = arguments.get("export_for_ai", True)
            trajectory = recorder.complete_trajectory()
            if trajectory:
                recorder.save_trajectory(trajectory)
                if export_for_ai:
                    ai_prompt = trajectory.to_ai_prompt_format()
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "success": True,
                            "task_id": trajectory.task_id,
                            "operations_count": len(trajectory.operations),
                            "ai_prompt": ai_prompt
                        }, indent=2)
                    )]
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "success": True,
                        "task_id": trajectory.task_id,
                        "operations_count": len(trajectory.operations),
                        "trajectory": trajectory.to_dict()
                    }, indent=2)
                )]
            return [TextContent(
                type="text",
                text=_error_response("No active trajectory", code="NO_ACTIVE_TRAJECTORY", retryable=False)
            )]

        elif name == "trajectory_get":
            fmt = arguments.get("format", "json")
            trajectory = recorder.get_current_trajectory()
            if trajectory:
                if fmt == "ai_prompt":
                    return [TextContent(type="text", text=trajectory.to_ai_prompt_format())]
                else:
                    return [TextContent(type="text", text=json.dumps(trajectory.to_dict(), indent=2))]
            return [TextContent(
                type="text",
                text=_error_response("No active trajectory", code="NO_ACTIVE_TRAJECTORY", retryable=False)
            )]

        elif name == "trajectory_list":
            storage = get_storage()
            limit = arguments.get("limit", 20)
            since = arguments.get("since")
            items = storage.trajectory_list(limit=limit, since=since)
            return [TextContent(
                type="text",
                text=json.dumps({"trajectories": items}, indent=2, ensure_ascii=False)
            )]

        elif name == "trajectory_load":
            task_id = arguments.get("task_id")
            fmt = arguments.get("format", "json")
            if not task_id:
                return [TextContent(
                    type="text",
                    text=_error_response("task_id is required", code="INVALID_PARAMS", retryable=False)
                )]
            storage = get_storage()
            traj_data = storage.trajectory_load_by_task_id(task_id)
            if traj_data is None:
                return [TextContent(
                    type="text",
                    text=_error_response(f"No saved trajectory for task_id: {task_id}", code="TRAJECTORY_NOT_FOUND", retryable=False)
                )]
            if fmt == "ai_prompt":
                from zerotoken.trajectory import Trajectory
                t = Trajectory(traj_data["task_id"], traj_data["goal"])
                t.operations = traj_data["operations"]
                t.metadata = traj_data.get("metadata") or {}
                return [TextContent(
                    type="text",
                    text=json.dumps({"success": True, "ai_prompt": t.to_ai_prompt_format()}, indent=2, ensure_ascii=False)
                )]
            return [TextContent(
                type="text",
                text=json.dumps({"success": True, "trajectory": traj_data}, indent=2, ensure_ascii=False)
            )]

        elif name == "trajectory_delete":
            task_id = arguments.get("task_id")
            if not task_id:
                return [TextContent(
                    type="text",
                    text=_error_response("task_id is required", code="INVALID_PARAMS", retryable=False)
                )]
            deleted = get_storage().trajectory_delete_by_task_id(task_id)
            return [TextContent(
                type="text",
                text=json.dumps({"success": True, "deleted": deleted}, indent=2)
            )]

        elif name == "trajectory_to_script":
            task_id = arguments.get("task_id")
            script_task_id = arguments.get("script_task_id")
            prepend_init = arguments.get("prepend_init", True)
            stealth = arguments.get("stealth", False)
            if not task_id:
                return [TextContent(
                    type="text",
                    text=_error_response("task_id is required", code="INVALID_PARAMS", retryable=False)
                )]
            storage = get_storage()
            traj_data = storage.trajectory_load_by_task_id(task_id)
            if traj_data is None:
                return [TextContent(
                    type="text",
                    text=_error_response(f"No saved trajectory for task_id: {task_id}", code="TRAJECTORY_NOT_FOUND", retryable=False)
                )]
            operations = traj_data.get("operations") or []
            if len(operations) == 0:
                return [TextContent(
                    type="text",
                    text=_error_response(
                        "Trajectory has no operations, cannot generate valid script. Record browser actions before completing trajectory.",
                        code="INVALID_TRAJECTORY",
                        retryable=False,
                    )
                )]
            out_task_id = save_script_from_trajectory(
                traj_data,
                storage,
                task_id=script_task_id or task_id,
                prepend_init=prepend_init,
                stealth=stealth,
            )
            return [TextContent(
                type="text",
                text=json.dumps({"success": True, "task_id": out_task_id, "message": "Script saved from trajectory"}, indent=2, ensure_ascii=False)
            )]

        elif name == "script_save":
            task_id = arguments.get("task_id")
            goal = arguments.get("goal", "")
            steps = arguments.get("steps", [])
            if not task_id:
                return [TextContent(type="text", text=_error_response("task_id is required", code="INVALID_PARAMS", retryable=False))]
            get_storage().script_save(task_id, goal=goal, steps=steps)
            return [TextContent(type="text", text=json.dumps({"success": True, "task_id": task_id}, indent=2))]

        elif name == "script_list":
            limit = arguments.get("limit", 100)
            items = get_storage().script_list(limit=limit)
            return [TextContent(type="text", text=json.dumps({"scripts": items}, indent=2, ensure_ascii=False))]

        elif name == "script_load":
            task_id = arguments.get("task_id")
            if not task_id:
                return [TextContent(type="text", text=_error_response("task_id is required", code="INVALID_PARAMS", retryable=False))]
            script = get_storage().script_load(task_id)
            if script is None:
                return [TextContent(type="text", text=_error_response(f"No script for task_id: {task_id}", code="SCRIPT_NOT_FOUND", retryable=False))]
            return [TextContent(type="text", text=json.dumps({"success": True, "script": script}, indent=2, ensure_ascii=False))]

        elif name == "script_delete":
            task_id = arguments.get("task_id")
            if not task_id:
                return [TextContent(type="text", text=_error_response("task_id is required", code="INVALID_PARAMS", retryable=False))]
            ok = get_storage().script_delete(task_id)
            return [TextContent(type="text", text=json.dumps({"success": True, "deleted": ok}, indent=2))]

        elif name == "run_script":
            task_id = arguments.get("task_id")
            session_id = arguments.get("session_id")
            if bool(task_id) == bool(session_id):
                return [
                    TextContent(
                        type="text",
                        text=_error_response(
                            "Provide exactly one of task_id or session_id",
                            code="INVALID_PARAMS",
                            retryable=False,
                        ),
                    )
                ]
            storage = get_storage()
            if task_id:
                vars_map = arguments.get("vars") or {}
                script = storage.script_load(task_id)
                if script is None:
                    return [TextContent(type="text", text=_error_response(f"No script for task_id: {task_id}", code="SCRIPT_NOT_FOUND", retryable=False))]
                engine = ScriptEngine(vars_map=vars_map)
                result = await engine.run_script_start(script, controller, storage)
                return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]
            resolution = arguments.get("resolution")
            if resolution is None:
                return [TextContent(type="text", text=_error_response("resolution is required for resume", code="INVALID_PARAMS", retryable=False))]
            engine = ScriptEngine(vars_map={})
            result = await engine.run_script_resume(session_id, resolution, controller, storage)
            return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

        elif name == "run_script_by_job_id":
            binding_key = arguments.get("binding_key")
            if not binding_key:
                return [TextContent(type="text", text=_error_response("binding_key is required", code="INVALID_PARAMS", retryable=False))]
            storage = get_storage()
            binding = storage.script_binding_get(binding_key)
            if binding is None:
                return [TextContent(
                    type="text",
                    text=_error_response(
                        f"No binding for key: {binding_key}. Use script_binding_set to bind job_id to script first.",
                        code="SCRIPT_BINDING_NOT_FOUND",
                        retryable=False,
                    )
                )]
            script_task_id = binding.get("script_task_id")
            default_vars = binding.get("default_vars") or {}
            vars_arg = arguments.get("vars") or {}
            vars_map = {**default_vars, **vars_arg}
            script = storage.script_load(script_task_id)
            if script is None:
                return [TextContent(
                    type="text",
                    text=_error_response(
                        f"No script for task_id: {script_task_id}",
                        code="SCRIPT_NOT_FOUND",
                        retryable=False,
                        hint="Script was deleted. Re-run trajectory_to_script(script_task_id) to regenerate from trajectory, then retry run_script_by_job_id.",
                    )
                )]
            controller = get_controller()
            engine = ScriptEngine(vars_map=vars_map)
            result = await engine.run_script_start(script, controller, storage)
            return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

        elif name == "dfu_save":
            dfu_id = arguments.get("dfu_id")
            name_ = arguments.get("name")
            triggers = arguments.get("triggers")
            if not dfu_id or not name_ or triggers is None:
                return [TextContent(type="text", text=_error_response("dfu_id, name, triggers are required", code="INVALID_PARAMS", retryable=False))]
            get_storage().dfu_save(
                dfu_id,
                name=name_,
                description=arguments.get("description", "") or "",
                triggers=triggers,
                prompt=arguments.get("prompt", "") or "",
                allowed_resolutions=arguments.get("allowed_resolutions") or [],
            )
            return [TextContent(type="text", text=json.dumps({"success": True, "dfu_id": dfu_id}, indent=2, ensure_ascii=False))]

        elif name == "dfu_list":
            limit = arguments.get("limit", 100)
            items = get_storage().dfu_list(limit=limit)
            return [TextContent(type="text", text=json.dumps({"dfus": items}, indent=2, ensure_ascii=False))]

        elif name == "dfu_load":
            dfu_id = arguments.get("dfu_id")
            if not dfu_id:
                return [TextContent(type="text", text=_error_response("dfu_id is required", code="INVALID_PARAMS", retryable=False))]
            dfu = get_storage().dfu_load(dfu_id)
            if dfu is None:
                return [TextContent(type="text", text=_error_response(f"No dfu for dfu_id: {dfu_id}", code="DFU_NOT_FOUND", retryable=False))]
            return [TextContent(type="text", text=json.dumps({"success": True, "dfu": dfu}, indent=2, ensure_ascii=False))]

        elif name == "dfu_delete":
            dfu_id = arguments.get("dfu_id")
            if not dfu_id:
                return [TextContent(type="text", text=_error_response("dfu_id is required", code="INVALID_PARAMS", retryable=False))]
            ok = get_storage().dfu_delete(dfu_id)
            return [TextContent(type="text", text=json.dumps({"success": True, "deleted": ok}, indent=2, ensure_ascii=False))]

        elif name == "session_list":
            limit = arguments.get("limit", 100)
            items = get_storage().session_list(limit=limit)
            return [TextContent(type="text", text=json.dumps({"sessions": items}, indent=2, ensure_ascii=False))]

        elif name == "session_get":
            session_id = arguments.get("session_id")
            if not session_id:
                return [TextContent(type="text", text=_error_response("session_id is required", code="INVALID_PARAMS", retryable=False))]
            steps = get_storage().session_get(session_id)
            return [TextContent(type="text", text=json.dumps({"success": True, "steps": steps}, indent=2, ensure_ascii=False))]

        elif name == "script_binding_set":
            binding_key = arguments.get("binding_key")
            script_task_id = arguments.get("script_task_id")
            if not binding_key or not script_task_id:
                return [TextContent(type="text", text=_error_response("binding_key and script_task_id are required", code="INVALID_PARAMS", retryable=False))]
            storage = get_storage()
            script = storage.script_load(script_task_id)
            if script is None:
                return [TextContent(
                    type="text",
                    text=_error_response(
                        f"No script for task_id: {script_task_id}. Create script via trajectory_to_script or script_save first.",
                        code="SCRIPT_NOT_FOUND",
                        retryable=False,
                    )
                )]
            storage.script_binding_set(
                binding_key,
                script_task_id=script_task_id,
                description=arguments.get("description", "") or "",
                default_vars=arguments.get("default_vars") or {},
            )
            return [TextContent(type="text", text=json.dumps({"success": True, "binding_key": binding_key, "script_task_id": script_task_id}, indent=2, ensure_ascii=False))]

        elif name == "script_binding_get":
            binding_key = arguments.get("binding_key")
            if not binding_key:
                return [TextContent(type="text", text=_error_response("binding_key is required", code="INVALID_PARAMS", retryable=False))]
            binding = get_storage().script_binding_get(binding_key)
            if binding is None:
                return [TextContent(type="text", text=_error_response(f"No binding for key: {binding_key}", code="SCRIPT_BINDING_NOT_FOUND", retryable=False))]
            return [TextContent(type="text", text=json.dumps({"success": True, "binding": binding}, indent=2, ensure_ascii=False))]

        elif name == "script_binding_list":
            limit = arguments.get("limit", 100)
            items = get_storage().script_binding_list(limit=limit)
            return [TextContent(type="text", text=json.dumps({"bindings": items}, indent=2, ensure_ascii=False))]

        elif name == "script_binding_delete":
            binding_key = arguments.get("binding_key")
            if not binding_key:
                return [TextContent(type="text", text=_error_response("binding_key is required", code="INVALID_PARAMS", retryable=False))]
            ok = get_storage().script_binding_delete(binding_key)
            return [TextContent(type="text", text=json.dumps({"success": True, "deleted": ok}, indent=2, ensure_ascii=False))]

        else:
            return [TextContent(
                type="text",
                text=_error_response(f"Unknown tool: {name}", code="UNKNOWN_TOOL", retryable=False)
            )]

    except Exception as e:
        err_msg = str(e)
        code = "INTERNAL_ERROR"
        retryable = False
        if "Timeout" in err_msg or "timeout" in err_msg.lower():
            code = "TIMEOUT"
            retryable = True
        if "Target closed" in err_msg or "browser" in err_msg.lower() and "closed" in err_msg.lower():
            code = "BROWSER_NOT_INIT"
            retryable = False
        if "not found" in err_msg.lower() or "selector" in err_msg.lower():
            retryable = True
        return [TextContent(
            type="text",
            text=_error_response(err_msg, code=code, retryable=retryable)
        )]


async def main():
    """Run the MCP server"""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


def run():
    """Entry point for zerotoken-mcp console script."""
    asyncio.run(main())


if __name__ == "__main__":
    run()
