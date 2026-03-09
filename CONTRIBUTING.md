# 贡献指南

感谢你对 ZeroToken 的关注。以下是如何参与项目的方式。

## 开发环境

- Python 3.10+
- 推荐使用 [uv](https://github.com/astral-sh/uv) 管理依赖

```bash
git clone https://github.com/<your-org>/zerotoken.git
cd zerotoken
uv sync
playwright install chromium
```

## 运行测试

提交前请确保本地测试通过：

```bash
uv run pytest tests/ -v
```

CI 会在每次 push 和 PR 时自动运行测试。

## 提交变更

1. Fork 本仓库，从 `main` 拉出新分支（如 `fix/xxx`、`feat/xxx`）。
2. 修改代码并跑通测试。
3. 提交信息尽量清晰，例如：`feat(stealth): add browser_init(stealth=true)`、`fix(controller): handle timeout in click`。
4. 发起 Pull Request，描述变更动机与影响；维护者 review 后合并。

## 代码风格

- 遵循项目现有风格（async/await、类型注解、文档字符串）。
- 新功能若有设计决策，可在 `docs/plans/` 下补充设计文档。

## 问题与讨论

- **Bug 与功能建议**：请使用 [GitHub Issues](https://github.com/<your-org>/zerotoken/issues)。
- **使用问题与想法**：可到 [Discussions](https://github.com/<your-org>/zerotoken/discussions) 发帖。

再次感谢你的参与。
