# CLAUDE.md

本仓库的 Claude Code 项目指令。通用内容在 `AGENTS.md`（跨工具标准），本文件补充 Claude Code 特有的用法。

@AGENTS.md

## 在这个仓库里怎么干活

- **改后端先跑测试**：`cd backend; ..\.venv\Scripts\python.exe -m pytest tests -q`（73 个用例）。
  只改前端 UI 可以只跑 `cd frontend; npm run lint`。
- **动 `schemas.py` 是跨端改动**。改完必须同时验证后端测试与前端 `tsc --noEmit`，因为契约是两端共享的。
- **别在展示层补状态文案**。因素的三态（observed / assumption / insufficient）来自 `schemas.py`，
  要在数据层维护，不要在 UI 里硬编码判断。
- **评分链路里不许出现模型调用**。这是本项目的核心产品决策，见下方红线。

## 红线（改代码前先确认没踩）

- AI 不许改分：评分/情景/敏感性永远走确定性规则（`services/market.py`、`services/market_packs.py`）
- 修正量必须有 clamp 区间（`services/factors.py`，光照 ±8、宏观 ±6）
- 回落基线要标注 `assumption` / `insufficient`，不许伪装成实测
- 信源失败置 `degraded` + 保留 `last_success_at`，不清空、不静默
- 页面与报告共用同一份 factor snapshot，不重算
- 决策永远由人拍板，系统不自动改项目状态

## 常用文件定位

| 要找什么 | 去这里 |
| --- | --- |
| 数据契约（所有 schema） | `backend/app/schemas.py` |
| 八因素与三态逻辑 | `backend/app/services/factors.py` |
| 评分分量与权重 | `backend/app/services/market_packs.py` |
| 国别包（5 国） | `backend/app/services/market_packs.py` → `COUNTRY_PACKS` |
| 特征仓读写 | `backend/app/services/feature_store.py` |
| 信源抓取与审计 | `backend/app/services/public_data.py`、`sources.py` |
| 准入评估与 blocker | `backend/app/services/projects.py` |
| 受控研究简报 | `backend/app/services/research.py` |
| API 入口 | `backend/app/main.py` |
| 前端契约类型 | `frontend/src/types.ts` |
| 产品文档 | `docs/ATLASIQ_PRD.md`、`docs/architecture.md` |
| 人类接手 | `HANDOFF.md` |

## 自产方法论 Skill

`skills/evidence-graded-assessment/SKILL.md` —— 本项目八因素方法论抽成的可复用 Skill
（三态证据披露）。改评估逻辑时应同步更新它。
注意：`skills/@user_*/` 是第三方导入的 Skill，**不要改、也不要当作本项目产出**。

## 提交

中文提交信息，格式 `类型: 说明`（`feat` / `fix` / `docs` / `chore`）。
不要提交 `.env`、`backend/*.db`、`.venv/`、`node_modules/`。
