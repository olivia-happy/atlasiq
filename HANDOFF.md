# 项目交接文档

## 1. 这是什么项目

**AtlasIQ**：一个面向企业出海团队的海外市场准入研究与尽调工作台。
它把「某个国家 + 某个行业要不要进」这件事，拆成可追溯的多因素影响矩阵：每个因素显示当前分值、来源、覆盖率与缺失率，
再由受控 AI 在服务端证据范围内组织成研究简报，最后由人工在决策卡上拍板是否推进。

用途：秋招 GitHub 展示 + 面试 Demo（AI 产品经理岗，体现统计学背景 + 产品思维 + 全栈工程 + 可解释 AI 边界）。

## 2. 技术栈与架构

- 后端：FastAPI + Python（本地确定性、零付费 API）
- 前端：React 18 + TypeScript + Vite + Tailwind
- 数据：SQLite 为默认存储；PostgreSQL / Redis 为可选增强
- 数据源：仅免费公开数据（PVGIS / World Bank Open Data / OWID / Open-Meteo / 公开 RSS-GDELT）
- 测试：pytest 73 个用例；前端 `tsc --noEmit` 类型校验

### 目录结构

```
atlasiq/
├── backend/            FastAPI 服务
│   ├── app/
│   │   ├── main.py          API 入口
│   │   ├── schemas.py       FactorItem / FactorSnapshot / ImpactMatrix / AdmissionAssessment ... 全部数据契约
│   │   ├── db.py            SQLAlchemy 模型与会话
│   │   └── services/        factors / market / market_packs / feature_store / projects / research /
│   │                        readiness / reports / event_extraction / news / notifications / polling /
│   │                        sources / public_data / cache / decisions
│   └── tests/               pytest 73 个用例（19 个文件）
├── frontend/           React + Vite 工作台
│   └── src/                App.tsx / types.ts / lib / styles.css
├── docs/
│   ├── ATLASIQ_PRD.md          产品需求文档（12 节）
│   ├── architecture.md         架构与工程说明（含"容易被追问的工程选择"）
│   └── interview/              面试讲述指引
├── scripts/            start-local.ps1 / verify.ps1
└── docker-compose.yml  api / web / postgres / redis
```

## 3. 当前功能状态（已完成并验证）

### 后端（73 个测试全绿）

- **八因素影响矩阵**（`services/factors.py`）：`market_growth` / `power_demand` / `solar_resource` /
  `project_economics` / `grid_absorption` / `policy_auction` / `macro_finance` / `supply_trade`
- **三态披露**：每个因素按可得性标注 `observed`（有结构化观测）/ `assumption`（有文本证据但未人工确认）/
  `insufficient`（无证据，回落 Market Pack 基线），并输出 `coverage_ratio` / `missing_ratio` / `source_ids` / `explanation`
- **Market Pack 版本化**：5 个国别包（de-pv / es-pv / fr-pv / ae-pv / sa-pv），分量配置带 `base_score` + `weight` 与版本号
- **特征仓**：`feature_store` 保存 factor snapshot 与 observation，页面与报告共用同一份快照
- **信源审计**：`refresh_feature_sources` 抓取 PVGIS / World Bank，失败时置 `degraded` 并保留上次成功时间，不静默失败
- **准入评估**：`services/projects.py` 的 `assess_project` 产出 blocker 与人工复核项，`trigger_project_reassessment` 由已确认证据触发复盘
- **受控研究简报**：LLM 只据服务端证据组织表达；不可用时确定性降级，降级回答仍带可引用证据
- **事件抽取 / 新闻 / 通知 / 轮询**：证据入库链路，所有运行写审计

### 前端

- 国别工作台：影响矩阵、研究简报、决策卡、报告导出
- TypeScript 严格类型校验（`npm run build` 内含 `tsc --noEmit`）

## 4. 本次对话总结（如何走到这一步）

### 需求演进

用户目标：秋招 AI 产品经理，统计学研究生，需要展示"统计 + 产品 + 全栈 + AI"的项目。
在多个方向中选定**企业出海市场准入尽调**——因为它天然要求"证据可追溯、缺失要披露"，
而这正好是一套统计与产品共同约束的场景，也避开了"编一组漂亮数字"的诱惑。

### 关键技术决策

1. **AI 不碰分数**：市场评分、情景、敏感性由确定性规则计算，模型不许改分。理由：可复现，且分数一旦被模型改写就无法回溯。
2. **三态披露而非单一分值**：`observed / assumption / insufficient`。理由：把"我们不知道"显式表达出来，比给一个假精确的数字更有决策价值。
3. **同一份 factor snapshot 供页面与报告**：避免两处各算一遍导致口径漂移。
4. **信源失败降级而非失败关闭**：`degraded` 状态 + 保留上次成功时间，让用户知道数据的新鲜度。
5. **AI 不可用也要能跑**：受控 LLM 为可选，确定性降级路径始终存在。
6. **准入决策永远由人拍板**：系统永不自动准入、淘汰或改变项目阶段。

### 已实现的重要模块

| 模块 | 说明 |
| --- | --- |
| factors + market_packs | 八因素快照与可版本化的国别基线配置 |
| feature_store | 观测与快照持久化，页面/报告共用 |
| sources / public_data | 公开数据适配器 + 信源健康审计 |
| projects | 项目准入、blocker 归集、证据触发复盘 |
| research | 受控研究简报与确定性降级 |
| reports | 带证据 ID 的报告导出 |

### 已知风险与待办

1. **演示基线不是真实结论**：Market Pack 的 `base_score` 是种子基线，只有 `solar_resource` / `macro_finance`
   两个因素接入了真实观测数据并做区间修正（±8 / ±6）。其余六个因素在无观测时**回落基线而非模型估计**，
   页面上以 `assumption` / `insufficient` 明示。**不要把演示分值当成真实市场判断。**
2. **覆盖率没到 100%**：每个因素只接了 1–2 个指标，`coverage_ratio` 多数 < 1.0。
   接入更多公开指标（且必须可回溯到 source）是下一步的主要工作量。
3. **事件抽取未做人工标注集**：`event_extraction` 有测试但缺一个固定的 gold set，
   无法给出准确率——目前只能声明"规则可复现"。
4. **单机单人形态**：无多租户、无权限体系，PostgreSQL/Redis 仅作可选增强，未做并发压测。
5. **公开数据源有配额与限流**：`refresh_feature_sources` 失败会走降级，但没有指数退避与任务队列。

## 5. 新电脑安装环境（完整步骤）

> 只需 Python 3.11+ 与 Node.js 20+。

### 5.1 后端

```powershell
cd D:\path\to\atlasiq\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 5.2 前端

```powershell
cd D:\path\to\atlasiq\frontend
npm install
```

### 5.3 启动

```powershell
# 一键启动
powershell -ExecutionPolicy Bypass -File scripts\start-local.ps1

# 或分别启动
cd backend; .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
cd frontend; npm run dev
```

### 5.4 Docker 方式

```powershell
docker compose up --build
```

### 5.5 跑测试

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests -q
```

### 5.6 验证

```powershell
powershell -ExecutionPolicy Bypass -File scripts\verify.ps1
```

## 6. 常见问题

- **SQLite 被锁**：`backend/atlasiq.db` 与 `atlasiq-test.db` 已隔离，测试与演示库不互相污染；若仍报锁，确认没有残留 uvicorn 进程。
- **前端类型报错**：先跑 `npm run lint`（= `tsc --noEmit`）定位，再看 `frontend/src/types.ts` 的契约定义。
- **公开数据源请求失败**：属预期路径，信源会标 `degraded` 并保留上次成功值，不影响页面打开。
- **端口占用**：默认 API 8000 / Web 5173（Vite）；docker compose 会映射 postgres 与 redis，注意本机已有实例冲突。

## 7. 面试叙事要点

1. **用户与痛点**：出海团队做国别研究时，信息来源散、口径不一，最难的是"哪一条结论有证据、哪一条是猜的"。
2. **为什么做影响矩阵而不做一份报告**：报告是一次性产物，矩阵是可持续刷新的对象；而且矩阵能显式表达"缺失"。
3. **为什么 AI 不许改分**：统计模块负责数字，AI 只负责组织表达。这条边界是可解释性的地基。
4. **三态披露怎么落地**：`observed / assumption / insufficient` 三档 + 覆盖率 + 来源 ID，全部进了数据契约（`schemas.py`），不是文案层装饰。
5. **降级不是失败**：信源挂掉标 `degraded`、模型不可用走确定性降级——用户能看到"我在用什么在回答"。
6. **工程闭环**：73 个 pytest 用例覆盖评分/特征仓/准入/复盘/降级/报告；页面与报告共用同一份快照，避免口径漂移。
