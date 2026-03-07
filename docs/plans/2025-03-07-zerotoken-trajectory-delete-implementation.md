# trajectory_delete 实现计划

**Goal:** 新增 MCP 工具 `trajectory_delete`，按 task_id 删除已保存轨迹，防止记录过多。

**设计文档:** `docs/plans/2025-03-07-zerotoken-trajectory-delete-design.md`

---

## Task 1: MCP 工具 trajectory_delete

**Files:** `mcp_server.py`

1. 在 `list_tools()` 中、`trajectory_load` 之后增加 Tool `trajectory_delete`：
   - name: `"trajectory_delete"`
   - description: 按 task_id 删除已保存的轨迹，用于清理不再需要的记录
   - inputSchema: 必填 `task_id` (string)

2. 在 `call_tool` 中增加分支 `name == "trajectory_delete"`：
   - 取 `arguments.get("task_id")`，缺省则返回 `{ "success": false, "error": "task_id is required" }`
   - 调用 `recorder.delete_trajectory(task_id)`
   - 返回 `{ "success": true, "deleted": bool }`（True 表示至少删了一个文件）

3. Run: 手动或现有测试验证 MCP 调用行为。

4. Commit: `feat: MCP tool trajectory_delete`

---

## Task 2: 文档更新

**Files:** `CLAUDE.md`, `README.md`

1. 在 Trajectory Tools / 轨迹管理 列表中补充：
   - `trajectory_delete(task_id)` - 按 task_id 删除已保存轨迹，防止记录过多

2. Commit: `docs: document trajectory_delete`
