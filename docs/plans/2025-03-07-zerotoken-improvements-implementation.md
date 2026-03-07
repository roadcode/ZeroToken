# ZeroToken 功能与体验改进 - 实现计划

**Goal:** 落地 trajectory_delete、截图可选（include_screenshot）、错误结构化，并更新文档（含轨迹数量管理约定）。

**设计文档:** `docs/plans/2025-03-07-zerotoken-improvements-design.md`

---

## Task 1: MCP 工具 trajectory_delete

**Files:** `mcp_server.py`

1. 在 `list_tools()` 中、`trajectory_load` 之后增加 Tool `trajectory_delete`：name、description、inputSchema 必填 `task_id` (string)。
2. 在 `call_tool` 中增加分支 `name == "trajectory_delete"`：取 `arguments.get("task_id")`，缺省则返回结构化错误；调用 `recorder.delete_trajectory(task_id)`，返回 `{ "success": true, "deleted": bool }`。
3. 若已引入统一错误响应辅助（见 Task 3），此处失败路径使用该辅助。
4. Commit: `feat: MCP tool trajectory_delete`

---

## Task 2: 截图可选（include_screenshot）

**Files:** `mcp_server.py`

1. 在以下 browser 工具的 inputSchema 中增加可选参数 `include_screenshot`（boolean，default true）：`browser_open`, `browser_click`, `browser_input`, `browser_get_text`, `browser_get_html`, `browser_wait_for`, `browser_extract_data`。
2. 在 `call_tool` 中，对这些工具从 arguments 中 pop `include_screenshot`（默认 True）。在将 OperationRecord 返回给客户端时：若 `include_screenshot is False`，则对 `record.to_dict()` 的副本去掉 `screenshot` 键或置为 None，再序列化返回；轨迹记录仍使用完整 record（不变）。
3. 可选（后续优化）：将 `include_screenshot` 透传给 controller 的 `take_screenshot` 覆盖，使为 false 时不执行截图以节省耗时；本阶段可仅做 MCP 响应层过滤。
4. Commit: `feat: browser tools optional include_screenshot to reduce response size`

---

## Task 3: 错误结构化

**Files:** `mcp_server.py`

1. 新增辅助函数，例如 `_error_response(error: str, code: str = None, retryable: bool = None) -> str`，返回 `json.dumps({ "success": False, "error": error, "code": code, "retryable": retryable })`，仅包含非 None 的字段。
2. 将所有返回 `{ "success": false, "error": "..." }` 的地方改为调用该辅助，并视情况填入 `code`、`retryable`：
   - 参数缺失（如 task_id required）→ code=INVALID_PARAMS, retryable=false
   - 无当前/已保存轨迹 → code=TRAJECTORY_NOT_FOUND 或 NO_ACTIVE_TRAJECTORY, retryable=false
   - Unknown tool → code=UNKNOWN_TOOL, retryable=false
3. 在顶层 `except Exception as e` 中：根据异常类型或消息映射 code 与 retryable（如 TimeoutError、与 selector/navigation 相关 → retryable=true；ValueError、参数相关 → retryable=false），再调用辅助返回。
4. Commit: `feat: structured MCP error responses with code and retryable`

---

## Task 4: 文档更新

**Files:** `CLAUDE.md`, `README.md`

1. **trajectory_delete**：在 Trajectory Tools 列表中补充 `trajectory_delete(task_id)` 的说明。
2. **include_screenshot**：在 Browser Tools 说明或「注意事项」中注明：browser 类工具支持可选 `include_screenshot`（默认 true），设为 false 可减少响应体积。
3. **错误响应**：增加一小节说明失败时统一返回格式：`success`, `error`, 可选 `code`, `retryable`，并给出示例。
4. **轨迹数量**：在使用建议或注意事项中增加：建议通过 `trajectory_list` 查看已保存轨迹，对不需要的 `task_id` 调用 `trajectory_delete`，避免本地记录过多。
5. Commit: `docs: trajectory_delete, include_screenshot, error format, trajectory management`
