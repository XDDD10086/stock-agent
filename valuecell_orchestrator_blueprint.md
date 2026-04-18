# ValueCell + GPT + Gemini 本地 Orchestrator 项目蓝图

## 1. 项目目标

构建一个 **可快速落地的本地多 Agent 编排系统**，满足以下现实约束：

- **ChatGPT** 走 API，负责高质量规划、总结、裁决
- **Gemini** 走 API，负责计划审查、补充反方意见、找漏洞
- **ValueCell** 不走本地开源版，而是走 **官网版浏览器自动化**
- **前端允许自由输入任务**，但系统内部必须做结构化约束
- **后续支持定时任务**，用于定期研究、晨报、跟踪更新

本项目的核心不是“多个网页互相聊天”，而是：

> 用一个本地 orchestrator 把 GPT、Gemini、ValueCell 官网、浏览器自动化、任务调度和结果存储统一起来。

---

## 2. 核心原则

### 2.1 外层自由，内层约束

- 用户前端输入：自由自然语言
- GPT 输出：结构化计划 JSON
- Gemini 输出：结构化审查 JSON
- 最终执行：结构化 execution pack
- 浏览器层：只执行，不思考

### 2.2 模型负责推理，代码负责控制

- LLM 不直接控制整个浏览器流程
- 浏览器自动化不直接吃自然语言
- 业务状态、失败重试、任务生命周期都由 orchestrator 控制

### 2.3 官网版 ValueCell 作为特殊外部研究员

- 不是主控
- 不是调度中心
- 只是一个被 orchestrator 调用的“外部网页研究服务”

### 2.4 第一版先做单机 MVP

不要一开始做：
- 多用户
- 分布式 worker
- 复杂权限系统
- 漂亮但沉重的产品级前端

第一版只做：
- 单用户
- 本地运行
- 可重跑
- 可查看日志
- 可设置定时任务

---

## 3. 最终推荐架构

```text
Frontend (自由输入 + 状态查看)
    ↓
FastAPI Orchestrator
    ├─ GPT Planner
    ├─ Gemini Reviewer
    ├─ GPT Finalizer
    ├─ ValueCell Runner (Playwright)
    ├─ Result Parser / Arbiter
    ├─ Task Store (SQLite)
    └─ Scheduler (APScheduler)
```

### 3.1 技术选型

- **后端 / orchestrator**: Python + FastAPI
- **GPT 调用**: OpenAI Responses API
- **Gemini 调用**: Google GenAI SDK
- **浏览器自动化**: Playwright
- **前端**: Streamlit（第一版）
- **数据库**: SQLite（第一版）
- **定时任务**: APScheduler
- **本地保活**: macOS launchd（后续）

---

## 4. 为什么这样选

### 4.1 为什么用 FastAPI 做 orchestrator

因为 orchestrator 本质是一个本地后端服务，不是前端，也不是 IDE。

它要负责：
- 接收前端任务
- 调用多个模型
- 串联浏览器自动化
- 存储状态
- 触发重试
- 调度定时任务

### 4.2 为什么 GPT 用 OpenAI Responses API

因为它适合：
- 结构化输出
- 工具调用
- 有状态交互
- 规划与裁决类任务

### 4.3 为什么 Gemini 只做 Review，不做主控

Gemini 在这里最适合扮演：
- 第二意见
- 漏项检查器
- 风险审查器
- 反方分析器

不要让 Gemini 直接当浏览器执行主控，否则链路会复杂很多。

### 4.4 为什么 ValueCell 用 Playwright 而不是本地复刻

因为你已经验证：
- 官网版好用
- 本地开源版当前不够强
- 官网版更像一个“可调用的外部研究引擎”

所以最短路径不是重建 ValueCell，而是：
- 用 Playwright 自动登录并复用账号
- 提交任务
- 等结果
- 把结果抓回来

### 4.5 为什么默认不用 browser-use

browser-use 更适合开放式网页探索。

但 ValueCell 官网任务流程相对固定，更适合：
- DOM 明确
- 可重复
- 可调试
- 可截图
- 可回放

因此：
- **主链路：Playwright**
- **可选 fallback：browser-use**

---

## 5. 多 Agent 角色分工

这是你项目最关键的一部分。

### Agent 1: GPT Planner

**职责**
- 理解用户自由输入
- 把需求拆成明确步骤
- 识别目标、约束、预期输出
- 生成第一版结构化计划

**输入**
- 用户自然语言任务
- 系统规则
- 当前上下文（可选）

**输出**
- `plan_v1.json`

**不负责**
- 直接操控浏览器
- 最终网页执行
- 长循环自主讨论

---

### Agent 2: Gemini Reviewer

**职责**
- 审查 GPT 的计划
- 找漏项、歧义、风险
- 判断是否需要修正
- 给出最小修订意见

**输入**
- `plan_v1.json`

**输出**
- `review_v1.json`

**输出风格要求**
- 只指出问题
- 不重写全部计划
- 不新增无关内容

**不负责**
- 直接产出执行步骤
- 执行浏览器流程
- 最终结果总结

---

### Agent 3: GPT Finalizer

**职责**
- 基于 `plan_v1 + review_v1`
- 生成最终可执行的 `execution_pack.json`
- 生成 ValueCell 提交 prompt
- 定义预期返回字段

**输入**
- `plan_v1.json`
- `review_v1.json`

**输出**
- `execution_pack.json`

**这是浏览器执行前最后一道 LLM 关。**

---

### Agent 4: ValueCell Runner

**本质**
- 不是 LLM agent
- 是一个浏览器执行 agent / automation runner

**职责**
- 打开 ValueCell 官网
- 检查登录态
- 提交 prompt
- 等待任务完成
- 提取结果
- 截图留档
- 存 HTML / 纯文本 / 结构化结果

**输入**
- `execution_pack.json`

**输出**
- `valuecell_result_raw.json`
- `screenshots/*`

---

### Agent 5: Parser / Arbiter

**职责**
- 解析 ValueCell 页面文本
- 抽取标题、摘要、表格、风险评级、结论
- 和 GPT/Gemini 中间结果统一成 schema
- 给前端返回最终结果

**输出**
- `final_result.json`

---

### Agent 6: Scheduler Agent（可选）

**职责**
- 管理定时任务定义
- 触发已有任务模板再次运行
- 跟踪下次执行时间
- 支持 cron / interval / one-off

**注意**
第一版不需要单独做成 LLM，直接用代码实现即可。

---

## 6. 每个 LLM 的明确分工

### ChatGPT（OpenAI API）

定位：**主规划者 + 最终定稿者 + 可选总裁判**

适合做：
- 任务理解
- 计划生成
- Prompt 归一化
- 执行包生成
- 最终摘要
- 结果对齐

不适合做：
- 直接执行网页
- 代替行情接口算所有指标

---

### Gemini（Google API）

定位：**独立审稿人 / 风险质检员 / 第二意见模型**

适合做：
- 计划审查
- 漏项提示
- 风险提醒
- 与 GPT 形成交叉检查

不建议第一版让它做：
- 主规划者
- 主状态机
- 浏览器自动化控制器

---

### ValueCell 官网版

定位：**外部研究引擎 / 金融分析网页服务**

适合做：
- 证券研究报告生成
- 股票扫描
- 风险评估
- 对比分析

不适合做：
- 调度系统主脑
- 长期任务状态管理
- 你项目内部唯一真相源

---

## 7. 全链路工作流

### 单次任务流程

```text
1. 用户在前端输入自然语言任务
2. Frontend 调用 POST /tasks
3. Orchestrator 创建 task_id
4. GPT Planner 生成 plan_v1.json
5. Gemini Reviewer 审查并输出 review_v1.json
6. GPT Finalizer 输出 execution_pack.json
7. ValueCell Runner 用 Playwright 提交任务到官网
8. 等待网页任务完成
9. Parser 抽取结果
10. Arbiter 统一输出 final_result.json
11. 前端展示结果
12. 数据库存档
```

### 定时任务流程

```text
1. 用户创建 schedule
2. 保存到 scheduler_jobs 表
3. APScheduler 到点触发
4. Orchestrator 按预设参数重跑任务
5. 结果保存并可选通知前端
```

---

## 8. 项目目录结构建议

```text
ai-research-orchestrator/
├─ app/
│  ├─ main.py
│  ├─ config.py
│  ├─ dependencies.py
│  ├─ orchestrator/
│  │  ├─ task_service.py
│  │  ├─ planner_service.py
│  │  ├─ review_service.py
│  │  ├─ finalize_service.py
│  │  ├─ execution_service.py
│  │  └─ scheduler_service.py
│  ├─ providers/
│  │  ├─ openai_client.py
│  │  ├─ gemini_client.py
│  │  └─ valuecell_runner.py
│  ├─ parsers/
│  │  ├─ valuecell_parser.py
│  │  └─ result_normalizer.py
│  ├─ schemas/
│  │  ├─ task.py
│  │  ├─ plan.py
│  │  ├─ review.py
│  │  ├─ execution_pack.py
│  │  ├─ result.py
│  │  └─ schedule.py
│  ├─ routes/
│  │  ├─ tasks.py
│  │  ├─ schedules.py
│  │  └─ health.py
│  ├─ db/
│  │  ├─ models.py
│  │  ├─ session.py
│  │  └─ migrations/
│  ├─ scheduler/
│  │  └─ apscheduler_setup.py
│  ├─ prompts/
│  │  ├─ planner_system.md
│  │  ├─ reviewer_system.md
│  │  ├─ finalizer_system.md
│  │  └─ valuecell_task_template.md
│  ├─ utils/
│  │  ├─ logger.py
│  │  ├─ retry.py
│  │  ├─ ids.py
│  │  └─ time.py
│  └─ frontend/
│     └─ streamlit_app.py
├─ sessions/
│  └─ valuecell_profile/
├─ logs/
├─ screenshots/
├─ data/
│  └─ app.db
├─ tests/
├─ AGENTS.md
├─ ARCHITECTURE.md
├─ TASKS.md
├─ PROMPTS.md
├─ RUNBOOK.md
├─ SCHEDULER.md
├─ .env.example
├─ requirements.txt
└─ README.md
```

---

## 9. API 设计建议

### 9.1 任务接口

#### `POST /tasks`
创建新任务

请求体：
```json
{
  "input": "对水晶光电、歌尔股份、立讯精密做深度扫描，并输出红黄绿灯风险判断"
}
```

返回：
```json
{
  "task_id": "task_001",
  "status": "created"
}
```

#### `POST /tasks/{task_id}/run`
执行任务

#### `GET /tasks/{task_id}`
获取任务状态

#### `GET /tasks/{task_id}/result`
获取最终结果

#### `GET /tasks`
查看任务列表

---

### 9.2 定时任务接口

#### `POST /schedules`
创建定时任务

```json
{
  "name": "daily_ai_hardware_scan",
  "task_input": "每天扫描我的 AI 硬件组合并输出风险摘要",
  "trigger_type": "cron",
  "cron": "0 9 * * 1-5"
}
```

#### `GET /schedules`
查看定时任务

#### `POST /schedules/{id}/pause`
暂停任务

#### `POST /schedules/{id}/resume`
恢复任务

#### `DELETE /schedules/{id}`
删除任务

---

## 10. 核心数据结构

### 10.1 plan_v1.json

```json
{
  "objective": "...",
  "constraints": [],
  "required_outputs": [],
  "steps": [],
  "risk_flags": [],
  "needs_review": true
}
```

### 10.2 review_v1.json

```json
{
  "approved": false,
  "missing_items": [],
  "ambiguities": [],
  "risk_flags": [],
  "suggested_changes": []
}
```

### 10.3 execution_pack.json

```json
{
  "target": "valuecell_web",
  "valuecell_prompt": "...",
  "expected_sections": ["summary", "table", "risk_rating"],
  "browser_steps": [
    {"action": "open_dashboard"},
    {"action": "create_task"},
    {"action": "fill_prompt", "content": "..."},
    {"action": "submit"},
    {"action": "wait_until_completed"}
  ],
  "timeout_seconds": 900
}
```

### 10.4 final_result.json

```json
{
  "task_id": "...",
  "status": "completed",
  "summary": "...",
  "highlights": [],
  "table": [],
  "risk_rating": "yellow",
  "raw_sources": [],
  "screenshots": []
}
```

---

## 11. `.md` 文件应该怎么写

这是你今晚交给 Codex 最重要的部分。

---

### 11.1 `README.md`

**作用**
- 给人类和 Codex 一个项目入口
- 说明项目做什么
- 如何安装
- 如何运行
- 当前版本到什么程度

**建议结构**

```md
# Project Name

## Overview
这个项目是一个本地多 Agent orchestrator，用于将 ChatGPT API、Gemini API 和 ValueCell 官网自动化统一起来。

## Goals
- 支持自由输入任务
- 支持 GPT 规划 + Gemini 审查 + ValueCell 执行
- 支持定时任务

## Tech Stack
- FastAPI
- Playwright
- OpenAI API
- Google GenAI SDK
- SQLite
- APScheduler

## Quick Start
1. 安装依赖
2. 配置 .env
3. 安装浏览器
4. 运行 FastAPI
5. 运行 Streamlit

## Current Status
- [ ] GPT Planner
- [ ] Gemini Reviewer
- [ ] ValueCell Runner
- [ ] Result Parser
- [ ] Scheduler
```

---

### 11.2 `AGENTS.md`

**作用**
- 给 Codex 明确项目规则
- 约束 agent 怎么工作
- 避免它乱改架构

**建议结构**

```md
# AGENTS.md

## Mission
构建一个本地 orchestrator，将 GPT、Gemini 与 ValueCell 官网自动化整合。

## Non-Goals
- 不要重建 ValueCell 本地分析引擎
- 不要用网页 UI 自动化去替代 OpenAI/Gemini API
- 不要让浏览器直接执行自然语言

## System Rules
1. 前端允许自由输入，但执行层必须结构化。
2. GPT 负责 planner/finalizer。
3. Gemini 只负责 reviewer。
4. Playwright 是默认执行层。
5. ValueCell 官网通过持久化浏览器上下文操作。
6. 第一版使用 SQLite。
7. 第一版前端使用 Streamlit。

## Required Outputs
- plan_v1.json
- review_v1.json
- execution_pack.json
- final_result.json

## Coding Constraints
- Python 3.11+
- 所有 schema 使用 Pydantic
- 所有 provider 调用必须封装在 providers/
- 不允许把 prompt 文本硬编码在 service 内
- 所有 prompt 放在 prompts/

## Logging Rules
- 所有任务必须记录 task_id
- 所有 ValueCell 执行必须保存截图
- 所有失败必须记录 error_type / message / step
```

---

### 11.3 `ARCHITECTURE.md`

**作用**
- 解释整体系统设计
- 让 Codex 不要偏离既定架构

**建议结构**

```md
# ARCHITECTURE.md

## Overview
系统采用本地 orchestrator 架构。

## Components
- Frontend
- FastAPI Orchestrator
- GPT Planner
- Gemini Reviewer
- GPT Finalizer
- ValueCell Runner
- Parser / Arbiter
- Scheduler

## Data Flow
用户输入 -> GPT Planner -> Gemini Reviewer -> GPT Finalizer -> Playwright -> Parser -> Final Result

## Storage
SQLite 存储任务、结果、定时任务定义。

## Browser Automation Policy
- 仅操作用户自己的 ValueCell 账号
- 使用持久化 profile
- 不做风控绕过
- 出现验证码或登录异常时停止自动化
```

---

### 11.4 `TASKS.md`

**作用**
- 把开发拆成可执行任务
- 让 Codex 一项一项做

**建议按阶段写**

```md
# TASKS.md

## Phase 1 - Scaffold
- [ ] 初始化 FastAPI 项目
- [ ] 初始化 Streamlit 页面
- [ ] 建立项目目录结构
- [ ] 配置 .env.example
- [ ] 定义基础 schema

## Phase 2 - LLM Layer
- [ ] 实现 OpenAI client
- [ ] 实现 Gemini client
- [ ] 实现 planner service
- [ ] 实现 review service
- [ ] 实现 finalizer service

## Phase 3 - Browser Layer
- [ ] 实现 ValueCell 登录态复用
- [ ] 实现创建任务流程
- [ ] 实现等待任务完成
- [ ] 实现结果抓取
- [ ] 实现截图保存

## Phase 4 - Result Layer
- [ ] 实现 parser
- [ ] 实现 final result normalizer
- [ ] 实现任务状态更新

## Phase 5 - Scheduler
- [ ] 接入 APScheduler
- [ ] 实现创建/暂停/恢复 schedule
- [ ] 支持 cron 触发

## Phase 6 - Hardening
- [ ] 错误处理
- [ ] 重试机制
- [ ] 日志
- [ ] 回归测试
```

---

### 11.5 `PROMPTS.md`

**作用**
- 定义 prompt 的原则和版本管理

**建议结构**

```md
# PROMPTS.md

## Planner Prompt Requirements
- 必须输出 JSON
- 不允许输出散文
- 必须包含 objective / constraints / steps / outputs

## Reviewer Prompt Requirements
- 只审查，不重写
- 必须指出 missing_items / ambiguities / risk_flags

## Finalizer Prompt Requirements
- 基于 plan + review 输出 execution_pack
- execution_pack 必须稳定、简洁、可执行

## Prompt Versioning
- planner_system_v1
- reviewer_system_v1
- finalizer_system_v1
```

---

### 11.6 `RUNBOOK.md`

**作用**
- 发生问题时怎么排查
- 让你和 Codex 有统一排障手册

**建议结构**

```md
# RUNBOOK.md

## Common Issues

### 1. ValueCell 未登录
症状：跳转到登录页
处理：手动登录并保存持久化 profile

### 2. 页面结构变化
症状：找不到按钮/输入框
处理：更新 selector 或改用更稳的 locator 策略

### 3. GPT 返回非 JSON
症状：解析失败
处理：增加 schema 校验 + 自动重试一次

### 4. Gemini Review 为空
症状：review 输出缺字段
处理：补默认值并记录 warning

### 5. 定时任务未触发
症状：任务未执行
处理：检查 APScheduler 是否启动、时区是否正确
```

---

### 11.7 `SCHEDULER.md`

**作用**
- 单独描述定时任务设计

**建议结构**

```md
# SCHEDULER.md

## Goals
支持 one-off / interval / cron 三类任务。

## Trigger Types
- date
- interval
- cron

## Stored Fields
- schedule_id
- name
- task_input
- trigger_type
- trigger_payload
- enabled
- timezone
- next_run_at

## Execution Flow
scheduler trigger -> orchestrator run_task -> store result
```

---

## 12. prompt 文件建议内容

### `prompts/planner_system.md`

```md
You are the Planner.
Your task is to convert the user's natural-language request into a structured execution plan.
Output must be valid JSON.
Do not produce narrative prose.
Required keys:
- objective
- constraints
- required_outputs
- steps
- risk_flags
- needs_review
```

### `prompts/reviewer_system.md`

```md
You are the Reviewer.
Review the plan for missing items, ambiguity, and execution risk.
Do not rewrite the whole plan.
Output must be valid JSON.
Required keys:
- approved
- missing_items
- ambiguities
- risk_flags
- suggested_changes
```

### `prompts/finalizer_system.md`

```md
You are the Finalizer.
Use the planner output and reviewer output to generate a final execution pack.
The output must be valid JSON.
It will be consumed by a browser automation layer.
Required keys:
- target
- valuecell_prompt
- expected_sections
- browser_steps
- timeout_seconds
```

---

## 13. 第一版数据库表建议

### `tasks`
- id
- input_text
- status
- created_at
- updated_at
- current_step
- error_message

### `task_artifacts`
- id
- task_id
- artifact_type
- content_json
- created_at

### `schedules`
- id
- name
- task_input
- trigger_type
- trigger_payload
- timezone
- enabled
- next_run_at
- created_at

### `runs`
- id
- task_id
- source
- status
- started_at
- ended_at
- raw_output

---

## 14. 开发优先级（今晚交给 Codex 的顺序）

### Phase A：必须先完成
1. 搭项目骨架
2. 写 schema
3. 写 OpenAI client
4. 写 Gemini client
5. 写 planner/reviewer/finalizer 服务
6. 写基础 task API

### Phase B：接 ValueCell
7. 写 Playwright persistent context
8. 写 ValueCell runner
9. 写结果 parser
10. 让单次任务跑通

### Phase C：增强
11. 加日志
12. 加错误处理
13. 加截图
14. 加结果落库

### Phase D：定时任务
15. 加 APScheduler
16. 加 schedule API
17. 支持 cron / interval / one-off

### Phase E：前端
18. 用 Streamlit 做一个最小控制台
19. 展示任务列表
20. 展示结果与截图

---

## 15. Codex 执行指令建议

你今晚交给 Codex 时，不要只说“帮我做这个项目”。

你应该说：

```md
请基于本仓库中的 AGENTS.md、ARCHITECTURE.md、TASKS.md、PROMPTS.md 实现一个本地 orchestrator MVP。

要求：
1. 使用 Python + FastAPI。
2. 使用 OpenAI Responses API 作为 GPT planner/finalizer。
3. 使用 Google GenAI SDK 作为 Gemini reviewer。
4. 使用 Playwright 实现 ValueCell 官网自动化。
5. 前端先用 Streamlit。
6. 所有中间结果都使用 Pydantic schema。
7. 必须支持单次任务执行。
8. 必须预留定时任务接口和 APScheduler 接入点。
9. 优先完成 Phase A 与 Phase B。
10. 每完成一个阶段都更新 TASKS.md 的勾选状态。
```

---

## 16. 关键工程约束

### 必须做
- 所有 LLM 输出都做 JSON schema 校验
- 所有任务都保存 task_id
- 所有 ValueCell 自动化都保存截图
- 所有失败都要有明确 error step
- 所有 prompt 独立存放到 prompts/

### 不要做
- 不要让浏览器直接执行自然语言
- 不要把 prompt 写死在 service 代码里
- 不要让 Gemini 和 GPT 无限来回对话
- 不要一开始做复杂前端
- 不要把定时任务做成第二套系统

---

## 17. 第一版成功标准

满足以下条件即可视为 MVP 跑通：

1. 前端可输入一条自然语言任务
2. GPT 能生成 `plan_v1.json`
3. Gemini 能生成 `review_v1.json`
4. GPT 能生成 `execution_pack.json`
5. Playwright 能打开 ValueCell 官网并提交任务
6. 系统能等待任务完成并抓回结果
7. 结果能在前端展示
8. 任务结果能保存到 SQLite
9. 至少支持一个 cron 定时任务

---

## 18. 第二版可选增强

- 浏览器执行回放
- browser-use fallback
- 邮件 / Telegram / Discord 通知
- 多任务并发队列
- 更强的 selector 自愈
- 任务模板库
- 结果导出 Markdown / PDF
- 历史任务检索
- 多模型裁判机制

---

## 19. 最终一句话定位

> 这是一个本地多 Agent orchestrator：前端自由输入，GPT 负责规划与定稿，Gemini 负责审查，Playwright 负责操作 ValueCell 官网，调度器负责定时重跑，最终形成一个真正能落地的研究自动化系统。
