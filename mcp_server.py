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


# 创建 MCP 服务器
server = Server("zerotoken")

# 全局状态
_controller = None
_trajectory_recorder = None
_current_trajectory = None


def get_controller() -> BrowserController:
    """Get or create global browser controller."""
    global _controller
    if _controller is None:
        _controller = BrowserController()
    return _controller


def get_trajectory_recorder() -> TrajectoryRecorder:
    """Get or create global trajectory recorder."""
    global _trajectory_recorder
    if _trajectory_recorder is None:
        # 使用 mcp_server.py 所在目录下的 trajectories，避免 MCP 子进程 cwd 不是项目根导致轨迹存到别处
        _base_dir = os.path.dirname(os.path.abspath(__file__))
        _trajectories_dir = os.path.join(_base_dir, "trajectories")
        _trajectory_recorder = TrajectoryRecorder(trajectories_dir=_trajectories_dir)
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
            description="Load a saved trajectory by task_id for script generation or analysis",
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
    retryable: bool | None = None
) -> str:
    """Build structured error JSON for MCP tools."""
    out = {"success": False, "error": error}
    if code is not None:
        out["code"] = code
    if retryable is not None:
        out["retryable"] = retryable
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
                recorder.save_trajectory()
                if export_for_ai:
                    ai_prompt = recorder.export_for_ai(trajectory.task_id)
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
            limit = arguments.get("limit", 20)
            since = arguments.get("since")
            items = recorder.list_trajectories()
            if since is not None:
                items = [t for t in items if t.get("saved_at", 0) >= since]
            items = items[:limit]
            return [TextContent(
                type="text",
                text=json.dumps({"trajectories": items}, indent=2, ensure_ascii=False)
            )]

        elif name == "trajectory_load":
            task_id = arguments.get("task_id")
            fmt = arguments.get("format", "ai_prompt")
            if not task_id:
                return [TextContent(
                    type="text",
                    text=_error_response("task_id is required", code="INVALID_PARAMS", retryable=False)
                )]
            traj = recorder.load_trajectory_by_task_id(task_id)
            if traj is None:
                return [TextContent(
                    type="text",
                    text=_error_response(f"No saved trajectory for task_id: {task_id}", code="TRAJECTORY_NOT_FOUND", retryable=False)
                )]
            if fmt == "ai_prompt":
                return [TextContent(
                    type="text",
                    text=json.dumps({"success": True, "ai_prompt": traj.to_ai_prompt_format()}, indent=2, ensure_ascii=False)
                )]
            return [TextContent(
                type="text",
                text=json.dumps({"success": True, "trajectory": traj.to_dict()}, indent=2, ensure_ascii=False)
            )]

        elif name == "trajectory_delete":
            task_id = arguments.get("task_id")
            if not task_id:
                return [TextContent(
                    type="text",
                    text=_error_response("task_id is required", code="INVALID_PARAMS", retryable=False)
                )]
            deleted = recorder.delete_trajectory(task_id)
            return [TextContent(
                type="text",
                text=json.dumps({"success": True, "deleted": deleted}, indent=2)
            )]

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


if __name__ == "__main__":
    asyncio.run(main())
