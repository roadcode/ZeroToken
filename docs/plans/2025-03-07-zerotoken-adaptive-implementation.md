# ZeroToken 自适应元素定位 - 实现计划

**目标**：在 BrowserController 上增加自适应元素定位（指纹 + 相似度），选择器失效时自动重定位，无需改代码。

**设计文档**：`docs/plans/2025-03-07-zerotoken-adaptive-design.md`

---

## Task 1: 存储层（SQLite）

**文件**：新建 `zerotoken/adaptive_storage.py`（或 `zerotoken/adaptive.py` 内 Storage 类）

1. 定义表结构：`domain` (TEXT), `identifier` (TEXT), `fingerprint_json` (TEXT), `updated_at` (TEXT/INTEGER)，主键或唯一约束 (domain, identifier)。
2. 提供 `save(domain, identifier, fingerprint_dict)`、`load(domain, identifier) -> dict | None`、`delete(domain, identifier)`（可选）。
3. DB 文件路径：项目根或可配置，默认如 `zerotoken_adaptive.db` 于当前工作目录或包所在目录。
4. 单元测试：`tests/test_adaptive_storage.py` 或 `tests/test_adaptive.py` 中测试 save/load/覆盖。

**Commit**：`feat(adaptive): SQLite storage for element fingerprints`

---

## Task 2: 指纹提取

**文件**：`zerotoken/adaptive.py`（或 `zerotoken/adaptive_locator.py`）

1. 定义指纹结构（dict）：父节点 tag、属性、文本；自身 tag、属性、文本、兄弟 tag 列表、路径（tag 列表）。与设计文档一致。
2. 实现 `extract_fingerprint(element_handle, page)`：通过 Playwright 的 `element_handle.evaluate()` 或 `page.evaluate()` 在浏览器内取 DOM 信息（parent tagName/attributes/textContent、自身、siblings、path），返回可序列化为 JSON 的 dict。
3. 需在 Controller 侧能传入当前 `Page` 与定位到的 `ElementHandle`；若当前为 locator 而非 handle，需能取到 handle 或等价 DOM 信息。
4. 单元测试：用固定 HTML 字符串 + 解析出的“元素”结构 mock，测试 `extract_fingerprint` 输出结构正确；或小段真实 HTML 用 Playwright 取一次元素测一次。

**Commit**：`feat(adaptive): extract element fingerprint from DOM`

---

## Task 3: 相似度与重定位

**文件**：`zerotoken/adaptive.py`

1. 实现 `similarity_score(fingerprint_a, fingerprint_b) -> float`：对两段指纹的各维度（父、自身、兄弟、路径）做可比较表示（如字符串或归一化列表），定义加权打分规则，返回 0～1 或类似区间。
2. 实现 `relocate(page, domain, identifier, storage) -> ElementHandle | None`：从 storage 加载 (domain, identifier) 的指纹；用 `page.query_selector_all` 或等价方式取当前页候选元素（如 body 下所有可点击/含文本的节点，或按 tag 过滤）；对每个候选提取指纹并计算与存储指纹的相似度，取最高分；若最高分唯一且超过阈值则返回对应 ElementHandle，否则返回 None（并区分无指纹/无匹配/多候选）。
3. 单元测试：两段已知指纹的 similarity_score 合理；relocate 用 mock page + 预填 storage 测返回预期元素或 None。

**Commit**：`feat(adaptive): similarity score and relocate by fingerprint`

---

## Task 4: Controller 集成

**文件**：`zerotoken/controller.py`

1. 在 `click(selector, ..., auto_save=False, adaptive=False, identifier=None)` 及 `get_text`、`input`、`get_html` 等方法上增加参数 `auto_save`、`adaptive`、`identifier`（identifier 默认 None 表示用 selector 作为 identifier）。
2. 逻辑：先按 selector 定位；成功则执行操作，若 `auto_save=True` 则取当前 page 的 domain（从 `page.url` 解析）、当前元素，调用指纹提取并 storage.save；失败则若 `adaptive=True` 调用 relocate，若得到元素则用该元素执行操作（并可选本次成功时 auto_save 更新指纹），否则保持原失败行为。
3. 需在 Controller 内持有或可访问 storage、adaptive 模块；若未启用 adaptive 可懒加载/不初始化 storage。
4. 配置项：可在 `_config` 中增加 `adaptive_storage_path` 或 `enable_adaptive`，与现有 `enable_stability` 类似。

**Commit**：`feat(adaptive): Controller click/get_text/input/get_html support auto_save and adaptive`

---

## Task 5: MCP 参数透传

**文件**：`mcp_server.py`

1. 在 `browser_click`、`browser_input`、`browser_get_text`、`browser_get_html` 的 inputSchema 中增加可选参数 `auto_save` (boolean, default false)、`adaptive` (boolean, default false)、`identifier` (string, optional)。
2. 在 call_tool 对应分支中从 arguments 取出并传入 controller 的 click/input/get_text/get_html，不改变现有参数语义。

**Commit**：`feat(adaptive): MCP browser tools expose auto_save and adaptive`

---

## Task 6: 测试与文档

**文件**：`tests/test_adaptive*.py`、`CLAUDE.md` / `README.md`

1. 集成测试：启动 Playwright，打开本地或内联 HTML，先对某 selector 执行 click(selector, auto_save=True)，断言 storage 中有该 (domain, identifier) 的指纹；修改 HTML 使原 selector 失效，再 click(selector, adaptive=True)，断言仍点击到预期元素或 get_text 拿到预期内容。
2. 文档：在 CLAUDE.md/README 中说明自适应能力、`auto_save`/`adaptive` 的用法与典型流程（首次 auto_save，改版后 adaptive）。

**Commit**：`test(adaptive): integration test; docs: adaptive element locating`
