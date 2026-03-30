# ZeroToken 录制与重放流程

## 核心文件

| 文件 | 职责 |
|------|------|
| `zerotoken/controller.py` | 浏览器控制（单例），每次操作产出 OperationRecord |
| `zerotoken/trajectory.py` | 轨迹录制器，绑定 Controller 自动记录 |
| `zerotoken/storage_sqlite.py` | SQLite 持久化（trajectories/scripts/sessions/fingerprints 等表） |
| `zerotoken/engine/script_generator.py` | 轨迹 → 脚本转换 |
| `zerotoken/engine/script_engine.py` | 确定性重放引擎（无 LLM） |
| `mcp_server.py` | MCP 工具入口，串联上述模块 |
| `skills/zerotoken-openclaw/SKILL.md` | OpenClaw 集成编排指南 |

## 阶段一：录制

1. AI Agent 调用 MCP 工具（browser_click 等）
2. `BrowserController` 执行操作 → 返回 `OperationRecord`（含 step/action/params/result/page_state/screenshot/selector_candidates/fuzzy_point）
3. `TrajectoryRecorder.record_operation()` 追加到 `Trajectory.operations[]`，可选 auto_save 立即持久化
4. `trajectory_complete` 完成录制，保存到 SQLite，可导出 `to_ai_prompt_format()`（含模糊点标记）

关键：
- `extract_data` 默认设置 `fuzzy_point.requires_judgment = True`
- `SmartSelectorGenerator` 为每步生成多个备选选择器（含稳定性评分）
- `ensure_current_trajectory()` 支持隐式创建轨迹

## 阶段二：脚本生成

MCP 工具 `trajectory_to_script` → `script_generator.trajectory_to_script()`：

1. 动作名映射：`open` → `browser_open` 等
2. 可选前置 `browser_init` + `trajectory_start`
3. 保留 `selector_candidates`、`fuzzy_point`
4. 支持 `{{varname}}` 模板占位符
5. 保存到 `scripts` 表，`source_trajectory_id` 回溯原始轨迹

## 阶段三：重放

MCP 工具 `run_script` / `run_script_by_job_id` → `ScriptEngine`：

### 启动（run_script_start）
- 创建 session_id，初始化运行时（cursor=0, status="running"）
- 加载 DFU 规则

### 执行循环（_run_from_cursor）
每步：
1. 解析 `{{varname}}` 模板变量
2. DFU 匹配 → 匹配则暂停（pause_event）
3. 通过 BrowserController 执行动作
4. click/input 按稳定性评分依次尝试 selector_candidates
5. 日志写入 session_steps 表
6. 推进 cursor

### 暂停恢复（run_script_resume）
resolution 类型：abort / skip_step / retry_step / patch_step / human_done

### Job 绑定（run_script_by_job_id）
- script_bindings 表查找 job_id → script
- 合并 default_vars + caller vars

## 数据库表（zerotoken.db）

| 表 | 用途 |
|----|------|
| trajectories | 保存的轨迹 |
| scripts | 生成的脚本 |
| session_headers / session_steps | 重放会话日志 |
| session_runtime | 暂停/恢复状态 |
| dfus | Dynamic Fuzzy Unit 规则 |
| script_bindings | 外部 job_id → script 映射 |
| fingerprints | 元素指纹（自适应定位） |

## 关键设计特点

- **录制即脚本**：轨迹可直接转换，选择器候选和模糊点完整保留
- **容错重放**：多选择器按稳定性评分依次尝试
- **人/AI 在环**：DFU + pause_event 暂停等待判断
- **模板化参数**：同一脚本适配不同输入
