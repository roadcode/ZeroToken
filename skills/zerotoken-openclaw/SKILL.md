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

### 工具清单

- **browser**：`browser_init`（可选 `stealth: true` 反爬）、`browser_close`、`browser_open`、`browser_click`、`browser_input`、`browser_get_text`、`browser_get_html`、`browser_screenshot`、`browser_wait_for`、`browser_extract_data`
- **trajectory**：`trajectory_start`、`trajectory_complete`、`trajectory_get`、`trajectory_list`、`trajectory_load`、`trajectory_delete`

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

**不主动生成**：单次录制、只说「录一下」未提复用、未提定时/重复时，只做轨迹录制与保存。若用户后续要脚本再生成。

## 脚本格式与执行方式

### 格式（zerotoken_scripts/<task_id>.json）

脚本为 Agent 可读取的 **JSON**，结构示例：

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
- 可选 `fuzzy_point`：该步需 AI/人介入，含 `reason`、`hint`；执行时 Agent 在此步根据当前页面做决策（如 `browser_extract_data` 或等待人工）再继续。
- 可选参数化：`params` 中可用 `{{varname}}`，执行前由 Agent 或配置替换（如环境变量、用户输入）。

### 执行脚本

当用户或 cron 消息为「执行 ZeroToken 脚本 &lt;task_id&gt;」或「跑一下 &lt;task_id&gt; 的脚本」时：

1. 读取 `zerotoken_scripts/<task_id>.json`（若无则提示先根据轨迹生成脚本）。
2. 按 `steps` 顺序执行：无 `fuzzy_point` 则直接调用对应 MCP 并传入 `params`；有 `fuzzy_point` 则根据当前页面与 hint 做一次推理（如截图、提取、输入），再调用 MCP，然后继续。
3. 全部步骤完成后结束。

脚本是「数据驱动的 MCP 调用序列」，Agent 按表执行 + 模糊点介入，Token 消耗低。

### 模糊点执行约定

- **有 Agent 在场**：遇到 `fuzzy_point` 步骤时，Agent 根据 reason/hint 与当前页面决定调用哪个 MCP（如 `browser_extract_data`、`browser_input`），然后继续。
- **无人值守**：该步可能无法自动化，可跳过或失败告警；含模糊点的脚本在无人值守下可能需人工兜底。

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
3. **输出**：生成并保存：
   - **主格式**：`zerotoken_scripts/<task_id>.json`，steps 中 action 用映射后的 MCP 名，params 与轨迹一致，fuzzy_point 从轨迹带出。
   - **可选**：`zerotoken_scripts/<task_id>.md`，同序步骤的可读列表。
4. 若目录不存在，先创建 `zerotoken_scripts/` 再写入。

## 保存位置与复用查找

- **默认**：`zerotoken_scripts/<task_id>.json`
- **查找**：当用户或 cron 要求「执行/复用某任务」时，先 `trajectory_list` 得到 task_id，再检查 `zerotoken_scripts/<task_id>.json` 是否存在；若有则读取并按 steps 执行，若无则提示「该任务尚无脚本，是否根据轨迹生成？」。
- **可选**：`zerotoken_scripts/manifest.json` 维护 `[{ "task_id", "path", "goal", "created_at" }]`，可先读 manifest 再定位。

## 安装

将本 Skill 放入 OpenClaw 的 skills 目录之一：

- 工作区：`./skills/zerotoken-openclaw/`（仅当前项目）
- 本地共享：`~/.openclaw/skills/zerotoken-openclaw/`
- 或通过 ClawHub：`clawhub install zerotoken-browser`（若已发布）

从本仓库安装示例：克隆后复制 `skills/zerotoken-openclaw/` 到上述路径之一。

## 常见坑

- 忘记先调用 `browser_init` 就直接使用 `browser_open` / `browser_click`，导致第一次调用失败或异常。
- 录制轨迹时未使用 `export_for_ai: true`，后续生成脚本时需要额外处理轨迹数据。
- `task_id` 在 trajectory 与 `zerotoken_scripts/<task_id>.json` 文件名中不一致，导致执行时找不到对应脚本。
- 无人值守场景仍然依赖包含大量 `fuzzy_point` 的脚本，容易在模糊点步骤卡住；这类任务应提前评估是否需要人工兜底。
