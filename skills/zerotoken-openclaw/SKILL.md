---
name: zerotoken-openclaw
description: Use when using ZeroToken MCP via OpenClaw for browser automation, trajectory recording and low-token replay, especially for recurring or scheduled browser tasks.
---

# ZeroToken 浏览器自动化（OpenClaw）

教会 Agent 使用 ZeroToken MCP 做浏览器自动化、轨迹录制与脚本重放。旨在让 **OpenClaw 执行定时/重复任务时尽量少消耗 Token**。

ZeroToken 项目主页：`https://github.com/AMOS144/zerotoken`

## 何时使用 / 何时不该用

- **适合使用**：
  - 需要通过 OpenClaw + ZeroToken MCP 做浏览器自动化，并且未来会 **重复 / 定时执行** 的任务。
  - 已经有一次完整的浏览器操作轨迹，希望将其 **转成低 Token 消耗的脚本** 来复用。
- **不适合使用**：
  - 只想临时操作一次、没有复用需求的场景（直接用 ZeroToken MCP 即可）。
  - 页面强依赖人工决策，大量步骤都需要 `fuzzy_point` 介入、无人值守难以兜底的任务。

## 前置条件

- ZeroToken MCP Server 已安装，并在当前环境中注册为 `zerotoken`（或等价的 MCP server id）。
- 执行浏览器操作前需先 `browser_init`；完成后可选 `browser_close`。

## MCP 未配置时的处理

当调用 ZeroToken 相关 MCP 工具失败，并出现类似以下症状时：

- 找不到名为 `zerotoken` 的 MCP server；
- `browser_init` / `trajectory_start` 等工具报「tool not found」或「MCP server unavailable」；

Agent 应：

1. 明确告知用户：**ZeroToken MCP 尚未在当前环境安装或启用，无法直接使用浏览器自动化能力。**
2. 询问用户当前所用平台（如「Cursor / OpenClaw / 其他支持 MCP 的客户端」），并请用户：
   - 在其平台的 MCP Marketplace / 设置页中搜索并安装 `ZeroToken`；
   - 或按 ZeroToken 官方文档在本地启动 `mcp_server.py`，并将该服务注册为 id 为 `zerotoken` 的 MCP server。
3. 在用户确认安装 / 启用完成后，再从 `browser_init` 开始重新执行 ZeroToken 相关步骤。

## MCP 工具与流程

### 工具清单（与 MCP 对齐）

- **browser**：`browser_init`（可选 `stealth: true` 反爬）、`browser_close`、`browser_open`、`browser_click`、`browser_input`、`browser_get_text`、`browser_get_html`、`browser_screenshot`、`browser_wait_for`、`browser_extract_data`
- **trajectory**：`trajectory_start`、`trajectory_complete`、`trajectory_get`、`trajectory_list`、`trajectory_load`、`trajectory_delete`
- **script**：
  - `script_save`、`script_list`、`script_load`、`script_delete`
  - `run_script`：无 LLM 回放脚本执行  
    - **Start 模式**：`{ "task_id": "...", "vars"?: {...} }`
    - **Resume 模式（高级用法）**：`{ "session_id": "...", "resolution": {...} }`（由上层编排器在 DFU/模糊点暂停后恢复）
- **session**：`session_list`、`session_get(session_id)`：查询录制 / 回放会话明细，用于 debug、审计、定时任务复盘

脚本、轨迹与会话均由 MCP 后端存储在 **SQLite 数据库** 中，通过上述工具访问，不依赖本地文件路径。

可选参数：`include_screenshot: false` 减少响应体积；`auto_save: true` / `adaptive: true` 用于自适应元素定位。

### Quick Reference

| 工具 / action                | 典型用途                                      |
|-----------------------------|-----------------------------------------------|
| browser_init                | 初始化浏览器会话（可选 headless/stealth）    |
| browser_open                | 打开登录页或任意目标页面                      |
| browser_click               | 点击按钮、链接、tab 等                        |
| browser_input               | 在输入框内输入用户名、密码、搜索关键字等     |
| browser_get_text/get_html   | 读取文本或整段 HTML，用于后续解析             |
| browser_wait_for            | 等待某段文本出现/消失，避免页面还没加载完    |
| browser_screenshot          | 截图留档或调试                                |
| browser_extract_data        | 从列表 / 表格中抽数据                         |
| trajectory_start/complete   | 录制一次完整的浏览器操作轨迹                  |

### 典型流程

- **录制**：`trajectory_start(task_id, goal)` → `browser_init` → `browser_open` / `browser_click` / `browser_input` 等 → `trajectory_complete(export_for_ai: true)`
- **复用**：`trajectory_list` 查 task_id → `trajectory_load(task_id, format)` 获取轨迹
- **管理**：`trajectory_delete(task_id)` 删除；browser 工具可传 `include_screenshot: false`
- **错误**：失败时返回 `success: false`、`code`、`retryable`，可按 `retryable` 决定是否重试

## 何时才生成脚本

**仅在以下情况**根据轨迹生成可复用脚本（避免徒增 Token）：

1. **重复任务**：用户明确说会多次执行（如「以后每天跑」「定时执行」「重复任务」），或 cron/上下文表明是定时/周期任务。
2. **用户明确要求**：用户说「生成可复用脚本」「保存成脚本下次用」「导出为脚本」等。

**不主动生成**：未提复用、未提定时/重复时，只做轨迹录制与保存。若用户后续要脚本再生成。

## 定时任务如何找到对应脚本（基于 job_id 绑定）

当 **OpenClaw 以定时任务触发本 Skill** 时，事件参数中会携带该任务的 `job_id`。ZeroToken 使用 `job_id` 作为绑定键（`binding_key`），并在 MCP 数据库的 `script_bindings` 表中维护「job_id ↔ 脚本」关系。

Agent 必须遵守以下约定：

1. **始终使用 `job_id` 作为 binding_key 查询绑定**：
   - 调用 `script_binding_get(binding_key=job_id)`。
2. 若返回 binding：
   - 读取 `binding.script_task_id` 与 `binding.default_vars`；
   - 合并本次任务特有的参数（如用户给定的视频 ID、时间范围）到 vars；
   - 调用 `run_script(binding.script_task_id, vars=merged_vars)` 执行脚本。
3. 若 `script_binding_get(job_id)` 返回「未找到」：
   - 提示用户「当前 job_id 尚未绑定 ZeroToken 脚本」；
   - 不要随意尝试其他脚本或自动新建脚本。
4. 对于没有 `job_id` 或未标记为定时任务的场景：
   - 视为「一次性任务」，只使用 `browser_*` + `trajectory_*` 完成当前需求，不主动查找/执行脚本。

开发者应在 ZeroToken 侧或 OpenClaw 的集成层中，使用 `script_binding_set(binding_key=job_id, script_task_id=..., default_vars?, description?)` 预先将定时任务 job_id 与脚本 `task_id` 明确绑定。本 Skill 仅通过 `job_id` 查询绑定，**不对映射关系做额外推断**。

## 脚本格式与执行方式

### 格式（存于 MCP 数据库）

脚本通过 `script_save` / `script_load` 读写，结构示例：

```json
{
  "task_id": "login_daily",
  "goal": "每日登录并拉取报表",
  "steps": [
    { "action": "browser_init", "params": { "headless": true } },
    { "action": "trajectory_start", "params": { "task_id": "login_daily", "goal": "每日登录并拉取报表" } },
    { "action": "browser_open", "params": { "url": "https://example.com/login" } },
    { "action": "browser_input", "params": { "selector": "#user", "text": "{{username}}" } },
    { "action": "browser_click", "params": { "selector": "#submit" },
      "fuzzy_point": { "reason": "验证码需识别", "hint": "可调 browser_extract_data 或等待人工输入" } },
    { "action": "browser_get_text", "params": { "selector": ".report" } }
  ]
}
```

- `steps`：有序数组；每步 `action` 对应 MCP 工具名，`params` 为该工具入参。
- 可选 `fuzzy_point`：记录该步「需要 AI/人介入」的语义信息（`reason`、`hint`），**本身不会让 ScriptEngine 自动暂停**；只有当为该步配置了匹配的 DFU / 执行点时，`run_script` 执行到该步才会返回 `status="paused"`。
- 可选参数化：`params` 中可用 `{{varname}}`，执行前由 Agent 或配置替换（如环境变量、用户输入），或在 ExecutionPoint/DFU 暂停时由上层生成 `resolution.vars` 合并进运行时变量环境。

### 执行脚本（仅在定时 / 重复任务场景）

**只有在以下两种情况下，才去查找并执行脚本：**

- 上下文/cron 明确表明是「定时 / 周期性 / 重复执行」的任务（如每日评论、每小时抓取报表）。
- 用户明确说「执行 ZeroToken 脚本 &lt;task_id&gt;」「跑一下 &lt;task_id&gt; 的脚本」等。

在这些情况下：

1. 调用 `script_load(task_id)` 从 MCP 数据库读取脚本；若无则提示先根据对应轨迹生成并 `script_save`（否则不要擅自造脚本）。
2. 调用 `run_script(task_id, vars?)` 由 **MCP 内的 ScriptEngine 自动按 `steps` 顺序执行脚本**，无需 LLM，执行过程写入 session；返回形如 `{"success": ..., "status": "success|paused|failed", "session_id": ...}`。
3. 若返回 `status="paused"`（例如命中 DFU / 执行点 / 失败重试上限）：
   - 上层 Agent 阅读 `pause_event`（包含 step_index、dfu_id、提示文案与需要生成的 vars），做一次决策或生成 vars；
   - 再调用 `run_script(session_id=..., resolution={...})` 恢复执行，由 ScriptEngine 继续顺序执行后续 steps。

非定时/一次性任务：**优先只用 browser_* + trajectory_* 录制与完成当前任务，不主动查找/执行脚本。**

脚本是「数据驱动的 MCP 调用序列」，**存于 MCP 数据库，由 ScriptEngine 自动化回放**，Token 消耗低且可通过 session 追踪每次执行。

### 模糊点 / DFU 执行约定

- **有 Agent 在场（手动调用 browser_* 时）**：遇到带 `fuzzy_point` 的 OperationRecord / 步骤时，可把 `reason`、`hint` 视作提示，根据当前页面决定是否额外调用 `browser_extract_data`、`browser_input` 等，再继续。
- **使用 `run_script`（ScriptEngine 自动回放）时**：是否暂停由 DFU/执行点规则决定（`dfu_*` 配置 + trigger 匹配），而不是单靠 `fuzzy_point`。若某步既有 `fuzzy_point` 又命中 DFU，则 ScriptEngine 会在该步返回 `status="paused"` + `pause_event`，由上层 Agent 决定 `resolution` 后再恢复。
- **无人值守**：不建议依赖大量需要强人工判断的步骤；含模糊点但未配置 DFU 的脚本，在纯 `run_script` 模式下会直接按脚本跑完，可能需要通过 session 结果+日志事后审计。

## 根据轨迹生成脚本（流程）

1. **输入**：`trajectory_load(task_id, format="json")` 或 `format="ai_prompt"`；必要时先用 `trajectory_list` 选 task_id。
2. **action 映射**：轨迹中的 `operations[].action` 为内部名，生成脚本时必须映射为 MCP 工具名；执行时按 MCP 工具名调用。

   | 轨迹 action | 脚本/MCP action |
   |-------------|-----------------|
   | open | browser_open |
   | click | browser_click |
   | input | browser_input |
   | get_text | browser_get_text |
   | get_html | browser_get_html |
   | screenshot | browser_screenshot |
   | wait_for | browser_wait_for |
   | extract_data | browser_extract_data |

   轨迹不包含 `browser_init`、`trajectory_start`；生成脚本时在 steps 开头补上这两步（若需录制回放）。
3. **输出**：调用 `script_save(task_id, goal, steps)` 写入 MCP 数据库；steps 中 action 用映射后的 MCP 名，params 与轨迹一致，`selector_candidates`、`fuzzy_point` 从轨迹带出。（当前 MCP 未直接暴露「轨迹 → 脚本」工具，以上映射逻辑需在上层/Agent 侧实现或复用本仓库的 Python 辅助函数。）

## 保存位置与复用查找

- **脚本与轨迹**：均由 MCP 后端存储在数据库（SQLite）中，不依赖本地文件路径。
- **查找**：执行/复用某任务时，用 `trajectory_list` 或 `script_list` 得到 task_id，用 `script_load(task_id)` 取脚本；若无则提示「该任务尚无脚本，是否根据轨迹生成？」并可用 `trajectory_load` + 生成逻辑 + `script_save` 写入。
- **会话**：每次 `run_script` 或录制产生 session，用 `session_list`、`session_get(session_id)` 查看。

## 安装

将本 Skill 放入 OpenClaw 的 skills 目录之一：

- 工作区：`./skills/zerotoken-openclaw/`（仅当前项目）
- 本地共享：`~/.openclaw/skills/zerotoken-openclaw/`
- 或通过 ClawHub：`clawhub install zerotoken-browser`（若已发布）

从本仓库安装示例：克隆后复制 `skills/zerotoken-openclaw/` 到上述路径之一。

## 常见坑

- 忘记先调用 `browser_init` 就直接使用 `browser_open` / `browser_click`，导致第一次调用失败或异常。
- 录制轨迹时未使用 `export_for_ai: true`，后续生成脚本时需要额外处理轨迹数据。
- `task_id` 在 trajectory 与 script 中不一致，导致 `script_load(task_id)` 找不到对应脚本。
- 无人值守场景仍然依赖包含大量 `fuzzy_point` 的脚本，容易在模糊点步骤卡住；这类任务应提前评估是否需要人工兜底。
