# MCP 工具 trajectory_delete 设计

## 目标

为 ZeroToken MCP 增加按 task_id 删除已保存轨迹的能力，使模型可主动清理记录，避免轨迹过多。与现有 `TrajectoryRecorder.delete_trajectory(task_id)` 行为一致，仅暴露为 MCP 工具。

## 行为

- **工具名**：`trajectory_delete`
- **参数**：必填 `task_id` (string)
- **语义**：删除该 task_id 下所有已保存的轨迹文件（即 `trajectories_dir` 下 `{task_id}_*.json`）
- **成功**：`{ "success": true, "deleted": true }` 或未找到时 `{ "success": true, "deleted": false }`
- **失败**：缺少 task_id 或异常时 `{ "success": false, "error": "..." }`

## 使用方式

模型先通过 `trajectory_list` 获取列表，再对需要删除的 `task_id` 调用 `trajectory_delete(task_id)`。

## 实现要点

- 在 `mcp_server.py` 的 `list_tools()` 中新增 Tool `trajectory_delete`，inputSchema 必填 `task_id`。
- 在 `call_tool` 中处理 `trajectory_delete`：调用 `recorder.delete_trajectory(arguments["task_id"])`，按返回值组 JSON 响应。
- 无需修改 `zerotoken/trajectory.py`（已有 `delete_trajectory`）。
- 文档：在 CLAUDE.md / README.md 的 MCP 工具列表中补充 `trajectory_delete` 说明。
