# ZeroToken 自适应元素定位设计

## 1. 目标与范围

- **目标**：在现有 BrowserController 上增加「自适应元素定位」——选择器首次命中时可选保存元素指纹；之后若选择器因改版失效，用相似度在当页重定位同一逻辑元素，无需改代码。
- **范围**：本期只做自适应；反爬/云盾留到下一期。不新增 Fetcher 类，MCP 保持现有 browser_* 工具，通过可选参数（`adaptive`、`auto_save`）控制行为。

## 2. 架构思路

采用 **指纹 + 相似度**（对齐 Scrapling）：

- 首次用某选择器成功找到元素且 `auto_save=True` 时，将该元素的「指纹」（父节点 tag/属性/文本、自身 tag/属性/文本、兄弟 tag、路径 tag 等）按 `(domain, identifier)` 存入本地。
- 之后同一选择器失效且 `adaptive=True` 时，从存储取出指纹，对当前页候选元素做相似度打分，取最高分元素执行操作。

后续可优化：先尝试存储的备选选择器（若与 SmartSelector 结合）再跑相似度，减少计算。

## 3. 存储与指纹内容

- **存储**：本地 SQLite，单表 `(domain, identifier, fingerprint_json, updated_at)`。文件置于项目目录下（如 `zerotoken_adaptive.db`）或可配置路径。
- **identifier**：默认用当前选择器；可选允许调用方传入自定义 identifier（同一页多元素不同逻辑名）。
- **指纹内容**（与 Scrapling 对齐）：
  - 父节点：tag、属性名与值、直接文本
  - 自身：tag、属性名与值、文本、兄弟节点 tag 列表、从根到该节点的 tag 路径
  - 存为 JSON，便于比较与调试。

## 4. Controller 与 MCP 集成

- **Controller**：`click(selector, ..., auto_save=False, adaptive=False)` 及 `get_text` / `input` / `get_html` 等需定位元素的方法，增加可选参数 `auto_save`、`adaptive`。
  - 先按 selector 正常定位。
  - 成功且 `auto_save=True`：以当前 page 的 domain 与 selector（或传入 identifier）保存元素指纹。
  - 失败且 `adaptive=True`：用 domain + selector 查存储取指纹，对当前页元素做相似度搜索；若有唯一最佳匹配，用该元素执行本次操作（可选本次成功时再 auto_save 更新指纹）。
- **MCP**：`browser_click`、`browser_input`、`browser_get_text`、`browser_get_html` 等增加可选参数 `auto_save`、`adaptive`（默认 false），透传 Controller，不改变现有调用语义。

## 5. 错误与边界

- 选择器失效且未传 `adaptive=True`：行为与现有一致，直接返回失败。
- 选择器失效且 `adaptive=True`：若存储中无该 identifier 的指纹，或相似度搜索无结果/多个同分候选，均视为失败，返回明确错误（如 "element not found (adaptive: no stored fingerprint)" 或 "adaptive: multiple candidates"），OperationRecord 中可注明曾尝试 adaptive。
- 同一 identifier 多次 `auto_save`：覆盖更新该 (domain, identifier) 的指纹与 updated_at。

## 6. 测试

- **单元**：指纹序列化/反序列化；相似度函数（给定两段指纹得分合理）；存储读写与覆盖。
- **集成**：用简单 HTML，先 `click(selector, auto_save=True)` 成功并断言指纹已存；改 HTML 结构/class 使原 selector 失效，再 `click(selector, adaptive=True)`，断言仍能点到预期元素或 get_text 拿到预期内容。
