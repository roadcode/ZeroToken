# BrowserController 与 TrajectoryRecorder 详细实现分析

## 一、BrowserController (`zerotoken/controller.py`)

### 1.1 类设计

```python
class BrowserController:
    _instance: Optional["BrowserController"] = None  # 类级单例
    _browser: Optional[Browser] = None
    _context: Optional[BrowserContext] = None
    _page: Optional[Page] = None
```

**单例模式**：通过 `__new__` + `_initialized` 标志实现。`_browser`/`_context`/`_page` 是类变量，确保全局只有一个浏览器实例。`__init__` 中用 `_initialized` 防止重复初始化。

### 1.2 核心配置

```python
self._config = {
    "auto_screenshot": True,       # 操作后自动截图
    "track_state": True,           # 跟踪页面状态
    "timeout": 30000,              # 默认超时 30s
    "wait_network_idle": True,     # 等待网络空闲
    "enable_stability": True,      # 启用稳定性增强
    "max_retries": 3,              # 最大重试次数
    "retry_delay": 1.0,            # 重试间隔
    "enable_adaptive": True,       # 启用自适应定位
}
```

通过 `set_config(**kwargs)` 动态更新。

### 1.3 稳定性模块（延迟初始化）

```python
self._selector_generator: Optional[SmartSelectorGenerator] = None  # 智能选择器
self._adaptive_storage: Optional[AdaptiveStore] = None             # 自适应存储
self._smart_wait: Optional[SmartWait] = None                       # 智能等待
self._error_recovery: Optional[ErrorRecovery] = None               # 错误恢复
self._retry_wrapper: Optional[RetryWrapper] = None                 # 重试包装
self._selector_cache: Dict[str, SmartSelector] = {}                # 选择器缓存
```

`_init_stability_modules()` 在首次使用时才初始化，避免浏览器未启动时报错。`_get_smart_selector()` 带缓存机制，同一选择器只生成一次 SmartSelector。

### 1.4 数据结构

#### PageState（第27-41行）
```
url, title, html(可选), timestamp
```
轻量页面状态快照，`to_dict()` 不含 html（减少输出体积）。

#### OperationRecord（第44-87行）
```
step, action, params, result, page_state, screenshot, error, fuzzy_point, selector_candidates, timestamp
```
- `to_dict()` 采用条件输出：screenshot/error/fuzzy_point/selector_candidates 仅在非空时序列化
- `step` 由 `_next_step()` 自增，确保步骤号连续
- `timestamp` 在构造时自动生成

### 1.5 start() 浏览器初始化（第130-175行）

**流程**：
1. 检查现有浏览器连接（断线清理 → 重新启动）
2. stealth 模式分支：
   - **stealth=True**：使用 `STEALTH_LAUNCH_ARGS` 启动参数 + `DEFAULT_STEALTH_USER_AGENT` + Sec-CH-UA 头 + `STEALTH_INIT_SCRIPT` 注入脚本
   - **stealth=False**：标准启动参数 + 普通 UA
3. 创建 context → page，重置 step_counter 和 operation_history

**设计要点**：stealth 模式覆盖反检测场景（B站、小红书等），涉及 navigator 指纹、WebGL、HTTP 头等多层面伪装。

### 1.6 各操作方法的统一模式

所有操作方法（open/click/input/get_text/get_html/screenshot/wait_for/extract_data）遵循同一模式：

```
1. step = self._next_step()
2. try:
   a. 等待元素就绪（带选择器的方法）
   b. 生成 selector_candidates（click/input）
   c. auto_save → 保存指纹（click/input/get_text/get_html）
   d. 执行浏览器操作
   e. 获取 page_state + screenshot
   f. 构造 result = {success: True, ...}
3. except:
   a. adaptive → 尝试指纹重定位（click/input/get_text/get_html）
   b. 构造 result = {success: False, error: ...}
4. 构造 OperationRecord
5. append 到 _operation_history
6. return record
```

### 1.7 自适应定位机制

**auto_save 流程**（click 为例，第442-445行）：
1. 查找元素成功后，调用 `extract_fingerprint(el, page)` 提取元素指纹
2. 以 `domain + identifier` 为键存入 adaptive_storage

**adaptive 流程**（click 为例，第464-490行）：
1. 主选择器失败后，调用 `relocate(page, domain, ident, storage)` 按指纹相似度重定位
2. 重定位成功 → 执行操作，result 中标记 `adaptive_used: True`
3. 重定位失败 → 返回原始错误

**支持的元素操作方法**：click、input、get_text、get_html 四种。

### 1.8 各方法特殊细节

#### open()（第335-387行）
- 使用 `page.goto(url, wait_until=...)`
- wait_until 支持 load/domcontentloaded/networkidle/commit
- 错误时仍获取 page_state（页面可能已部分加载）

#### click()（第389-510行）
- 先 wait_for_selector → query_selector → 生成 selector_candidates
- 可选 scroll_into_view
- wait_after 参数控制点击后等待时间（默认 0.5s）
- 检测 navigated（URL 是否变化）
- screenshot_before + screenshot_after（实际只存 after）

#### input()（第512-623行）
- clear_first：先清空再输入
- delay：模拟打字间隔（默认 50ms）
- 执行后读取 actual_value 验证，result 包含 match 字段

#### get_text()（第625-717行）
- 内部定义 `_get_value_from_el()` 闭包，支持 text/html/value/innerText 四种属性
- 默认不截图（take_screenshot=False）

#### get_html()（第719-801行）
- selector 为 None 时返回整页 HTML
- auto_save/adaptive 仅在 selector 有值时生效

#### screenshot()（第803-865行）
- 支持 selector（元素截图）或 full_page（整页截图）
- 可选 path 参数保存到文件

#### wait_for()（第867-931行）
- 支持 4 种 condition：selector、url、text、navigation
- text 条件使用 `json.dumps()` 转义防止注入（第900行）

#### extract_data()（第933-1024行）
- **唯一默认设置 fuzzy_point 的方法**
- schema 驱动：`{fields: [{name, selector, type}]}`
- type 支持：text/html/value/float/int
- 单字段错误不中断，记录 `{name}_error`
- result 中额外标记 `ai_node: True`

### 1.9 fuzzy_point 构造

```python
def _make_fuzzy_point(self, fuzzy_reason=None, fuzzy_hint=None):
    if fuzzy_reason is None and fuzzy_hint is None:
        return None
    return {"requires_judgment": True, "reason": ..., "hint": ...}
```
- 所有方法通过 fuzzy_reason/fuzzy_hint 参数可选设置
- extract_data 无条件设置 fuzzy_point（AI 节点能力）

---

## 二、TrajectoryRecorder (`zerotoken/trajectory.py`)

### 2.1 Trajectory 数据类（第16-78行）

```python
class Trajectory:
    task_id: str
    goal: str
    start_time: datetime
    end_time: Optional[datetime]
    operations: List[Dict[str, Any]]   # 注意：存的是 dict，不是 OperationRecord
    metadata: {browser_info, total_steps, successful_steps, failed_steps}
```

**add_operation(record: OperationRecord)**：
- 调用 `record.to_dict()` 转为 dict 后追加
- 自动更新 metadata 统计（total_steps、successful/failed_steps 根据 result.success 判断）

**to_dict()**：完整序列化，包含 duration_seconds 计算。

**to_ai_prompt_format()**：
```
Task Goal: {goal}

Operation History:
[Step {n}] {action}({params})
[Step {n}] {action}({params}) [需判断: {reason}; 提示: {hint}]
```
- fuzzy_point 标记格式：`[需判断: {reason}; 提示: {hint}]` 或 `[需判断: {reason}]`

### 2.2 TrajectoryRecorder 类（第81-239行）

#### 构造
```python
def __init__(self, trajectory_store: TrajectoryStore, auto_save: bool = True):
```
- **trajectory_store 是必填参数**（数据库持久化）
- auto_save=True 时每步操作后自动持久化

#### 核心方法

##### bind_controller(controller)（第98-100行）
绑定 BrowserController，后续 complete_trajectory 时可同步 controller 的操作历史。

##### start_trajectory(task_id, goal)（第102-121行）
1. 若当前存在隐式轨迹（`_implicit_` 前缀），先完成它
2. 创建新 Trajectory
3. 清空 controller 的操作历史（`clear_history()`）

##### ensure_current_trajectory()（第123-128行）
**关键方法**——MCP server 中每个浏览器操作前调用：
- 若已有当前轨迹 → 直接返回
- 若无 → 创建隐式轨迹 `"_implicit_" + timestamp`，goal 为 "未命名会话"
- **不清理 controller history**（区别于 start_trajectory）

##### record_operation(record)（第130-136行）
1. 追加 OperationRecord 到当前轨迹
2. 若 auto_save=True → 调用 save_trajectory() 立即持久化

##### complete_trajectory()（第142-164行）
1. 标记 `trajectory.complete()`（设置 end_time）
2. **同步 controller 历史**：遍历 controller.get_operation_history()，将未记录的操作补录
   - 通过 step 编号去重
   - 调用 `_dict_to_record()` 将 dict 转回 OperationRecord
3. 将 `_current_trajectory` 置 None 并返回
4. **不在此处持久化**（由 MCP 层 trajectory_complete 工具处理，避免重复保存）

##### _dict_to_record(data)（第166-186行）
dict → OperationRecord 的反序列化：
- 重建 PageState 对象
- 保留所有字段（screenshot、error、fuzzy_point、selector_candidates）

##### save_trajectory(trajectory=None)（第188-205行）
- 可传入指定轨迹，默认保存当前轨迹
- 调用 `trajectory_store.trajectory_save(task_id, goal, operations, metadata)`
- 返回数据库 ID

##### load_trajectory_by_task_id(task_id)（第207-215行）
从 DB 加载最新轨迹 → 重建 Trajectory 对象（不恢复 start_time/end_time）。

##### list_trajectories(limit=100)（第217-228行）
返回精简列表：`{id, task_id, goal, created_at}`。

##### delete_trajectory(task_id)（第230-232行）
按 task_id 删除，返回删除数量。

##### export_for_ai(task_id)（第234-239行）
加载轨迹 → 返回 `to_ai_prompt_format()` 文本。

### 2.3 与 MCP Server 的交互

MCP server 中的典型调用流程（mcp_server.py）：

```
1. 浏览器操作工具（browser_click 等）:
   recorder.ensure_current_trajectory()   # 确保有轨迹
   record = controller.click(...)          # 执行操作，获取 OperationRecord
   recorder.record_operation(record)       # 记录（auto_save 时自动持久化）

2. trajectory_complete 工具:
   trajectory = recorder.complete_trajectory()  # 完成录制 + 同步历史
   recorder.save_trajectory(trajectory)          # 持久化到 DB
   trajectory.to_ai_prompt_format()              # 可选导出 AI 提示

3. trajectory_list / trajectory_load / trajectory_delete:
   直接调用 recorder 的对应方法
```

---

## 三、两者协作关系

```
BrowserController                    TrajectoryRecorder
      |                                      |
      |-- click() → OperationRecord          |
      |     append 到 _operation_history      |
      |                                      |
      |            ← ensure_current_trajectory()
      |               (隐式创建轨迹)
      |                                      |
      |            ← record_operation(record)
      |               append 到 trajectory.operations
      |               auto_save → DB
      |                                      |
      |-- complete_trajectory()              |
      |     同步 controller history →         |
      |     补录未记录的操作                   |
      |     _current_trajectory = None        |
```

**关键设计**：
- Controller 维护自己的 `_operation_history`，作为操作记录的**第一落点**
- Recorder 可绑定 Controller，在 `complete_trajectory()` 时同步未记录的操作
- `ensure_current_trajectory()` 保证即使没有显式调用 `trajectory_start`，操作也不会丢失
- 持久化由 Recorder 通过 TrajectoryStore 接口完成，Controller 不感知存储
