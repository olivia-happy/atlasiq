# AGENTS.md

给在本仓库工作的 AI 编码助手（Claude Code / Codex / Cursor / Gemini CLI / Copilot 等）。
人类接手请看 `HANDOFF.md`；产品背景见 `docs/ATLASIQ_PRD.md`。

## 项目一句话

AtlasIQ：面向企业出海团队的海外市场准入研究与尽调工作台。
把「某国某行业要不要进」拆成可追溯的八因素影响矩阵，受控 AI 组织研究简报，人工在决策卡拍板。

## 环境与命令

Python 3.11+ 与 Node.js 20+。后端依赖装在 `backend/.venv`。

```powershell
# 后端：跑测试（当前 73 个用例）
cd backend
..\.venv\Scripts\python.exe -m pytest tests -q

# 前端：类型校验 + 构建
cd frontend
npm run lint      # = tsc --noEmit
npm run build     # = tsc --noEmit && vite build

# 一键全量校验（后端 pytest + 前端 build）
powershell -ExecutionPolicy Bypass -File scripts\verify.ps1
powershell -ExecutionPolicy Bypass -File scripts\verify.ps1 -BackendOnly
```

改完任何后端逻辑，**必须跑一遍 `pytest tests -q`**。改 `schemas.py` 后必须同时跑前端 `npm run lint`（契约是跨端共享的）。

## 架构红线

- **AI 不许改分**。市场评分、情景、敏感性由 `services/market.py` + `services/market_packs.py` 的确定性规则计算。
  模型只允许在服务端证据范围内组织表达（`services/research.py`）。**不要给评分引入任何模型调用。**
- **三态披露是数据契约，不是文案**。`FactorItem.status` 的 `observed / assumption / insufficient`
  定义在 `schemas.py`，与 `coverage_ratio` / `missing_ratio` / `source_ids` 一起构成对外契约。
  加分值时要一起维护这几项，**不要绕开 schema 在展示层拼状态文案**。
- **修正量必须有上限**。`services/factors.py` 里每个因素的 adjustment 都 clamp 到区间
  （光照 ±8、宏观 ±6）。新增因素时必须给区间，否则一个异常观测会污染全表。
- **回落基线必须明说**。无观测时给 `base_score` 并标注 `assumption` / `insufficient`，
  解释文案要区分「有证据未确认」和「什么都没有」——**禁止把回落值伪装成实测值**。
- **信源失败要降级不要清空**。`refresh_feature_sources` 失败时置 `degraded` 并保留 `last_success_at`，
  不要静默失败、不要清空已有观测。
- **页面与报告共用同一份 factor snapshot**。不要在 `reports.py` 里重算一遍，否则两处口径会漂移。
- **决策永远由人拍板**。系统不自动准入、淘汰或改项目阶段。`projects.py` 只产出 blocker 与复核项。

## 数据边界

- 数据源仅限免费公开数据：PVGIS / World Bank Open Data / OWID / Open-Meteo / 公开 RSS-GDELT。
  **不要引入付费 API、商业数据源或绕过反爬的抓取。**
- 新闻只保存公开标题、RSS/API 摘要与受限短摘录，不做全文镜像。
- 每条结论必须能回溯到来源 ID 与 Evidence ID。
- 默认本地 SQLite；PostgreSQL / Redis 只是可选增强，**不要让核心链路依赖它们才能跑通**。

## 代码风格

- Python：类型注解齐全（`from __future__ import annotations`），服务层按 `services/<域>.py` 切分。
- 前端：TypeScript 严格模式，`tsc --noEmit` 必须零错误。
- 提交信息用中文，格式 `类型: 说明`（`feat` / `fix` / `docs` / `chore`）。

## 不要做的事

- 不要把模型接进评分链路
- 不要在展示层编造或润色因素状态
- 不要让测试依赖真实网络或付费服务（公开数据源调用必须可 mock）
- 不要提交 `.env`、`*.db`、`.venv/`、`node_modules/`
