# ZeroToken 功能与体验改进设计（方案二 + 错误结构化）

## 目标

在功能 (a) 与稳定性/体验 (b) 上做一批改进：落地 trajectory_delete、截图可选、错误结构化，并约定轨迹数量管理方式。

## 一、trajectory_delete 与轨迹数量

- **trajectory_delete**：按既有设计实现 MCP 工具 `trajectory_delete(task_id)`，内部调用 `recorder.delete_trajectory(task_id)`，返回 `{ "success": true, "deleted": bool }`；无匹配时 `deleted: false`，异常时 `success: false` 并走统一错误结构。
- **轨迹数量控制**：不新增自动删旧或配置项。在 CLAUDE.md / README 中约定：建议模型在调用 `trajectory_list` 后，对不再需要的 `task_id` 主动调用 `trajectory_delete`，避免本地轨迹过多。`trajectory_list` 已有 `limit` 参数，沿用即可。

## 二、截图可选（include_screenshot）

- 在所有会返回 OperationRecord 的 browser 类 MCP 工具中增加可选参数 **include_screenshot**（boolean，默认 **true**）。
- 当 **include_screenshot == false** 时：
  - **MCP 响应**：在返回给客户端的 JSON 中，将 record 的 `screenshot` 字段置为 `null` 或省略，减少单次响应的 token。
  - **轨迹记录**：仍按当前逻辑记录完整 OperationRecord（含截图），不改变 TrajectoryRecorder 行为。
- 实现方式：在 MCP 层，从 controller 拿到 record 后，若 `include_screenshot is False`，则在序列化前将 `record.to_dict()` 中的 `screenshot` 置为 None 或删除该键再返回。可选地，将 `include_screenshot` 透传给 controller 的 `take_screenshot`/`auto_screenshot` 覆盖，使为 false 时不执行截图以节省耗时（为后续优化，可在实现计划中单列一步）。

## 三、错误结构化

- **统一失败响应格式**：所有 MCP 工具在失败时返回同一结构的 JSON：
  - `success`: false（必填）
  - `error`: 人类可读的简短描述（必填）
  - `code`: 可选，机器可读错误码，便于模型或上层做分支（如 `TRAJECTORY_NOT_FOUND`, `SELECTOR_TIMEOUT`, `BROWSER_NOT_INIT`, `INVALID_PARAMS`）
  - `retryable`: 可选，boolean，表示是否建议模型重试（如超时、元素未找到、网络类可标 true；参数错误、浏览器已关闭标 false）
- **适用范围**：所有 MCP 工具（browser + trajectory）。当前仅返回 `{ "success": false, "error": "..." }` 的路径改为上述结构；成功响应保持现有格式，不增加 code/retryable。
- **实现**：在 `mcp_server.py` 中提供 1～2 个辅助函数（如 `error_response(error, code=None, retryable=None)`），统一构造错误 JSON；在 catch 到异常时，根据异常类型映射为固定 code 与 retryable（例如超时 → code=TIMEOUT, retryable=true；参数缺失 → code=INVALID_PARAMS, retryable=false）。

## 四、文档

- 在 CLAUDE.md / README 的 MCP 工具列表中补充：`trajectory_delete` 的说明；`include_screenshot` 的说明；错误响应中 `code`、`retryable` 的约定与示例。
- 在「使用建议」或「注意事项」中增加：建议通过 `trajectory_list` + `trajectory_delete` 管理轨迹数量，避免记录过多。
