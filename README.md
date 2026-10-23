# RetroFlow

研发复盘改进系统。粘贴会议原文后，提取问题、识别复发、把行动落到证据和验收。仓库分 `apps/web`（Next.js）和 `apps/api`（FastAPI），数据用 PostgreSQL + pgvector。

登录后：新建复盘 → 分析 → 确认并发布行动 → 提交证据并验收。趋势、助手、周复盘从同一套数据读出。未配置 LLM 时，登录和列表仍可用。

## 架构

```text
浏览器 Next.js
  │  SSE  POST /api/v1/agent/chat
FastAPI
  ├─ agent/loop.py                     助手：模型选择工具，最多 6 步
  ├─ workflows/analysis.py             复盘分析：固定顺序的 LangGraph
  ├─ retrieval/search.py               向量 + jieba 分词 BM25，用 RRF 合并
  ├─ services/verify_suggestion.py     验收建议：只输出通过或退回
  ├─ providers/github.py               只读用户贴出的 Pull Request
  └─ mcp/server.py                     Cursor 只读三个工具，账号来自 MCP_USER_EMAIL
PostgreSQL + pgvector                  业务数据、原文块、运行记录、待确认操作
外部：DeepSeek、Ollama 向量、GitHub（GITHUB_TOKEN 可空）
```

助手里的写入工具只生成待确认操作。复盘发布、行动验收仍由人点击。分析的下一步由 `workflows/analysis.py` 里的边决定。

## 评测

标注在 `apps/api/evals/cases.jsonl`，共 30 条（15 问答、5 复发、5 验收、5 注入）。生成报告：

```powershell
cd apps/api
.\.venv\Scripts\python.exe -m app.evals.report
```

离线夹具上的 Recall@5：纯向量 `0/4 = 0.00`，混合检索 `4/4 = 1.00`。这 4 题是标注里 `source=chunk` 的问答。向量名次是固定的：6 条无关短文排在 3 条演示复盘前面。这个 1.00 只说明在这套固定名次下，BM25 能把关键词捞回。线上召回要等本机 Ollama 和 Postgres 再测。工具选择、引用、验收、注入、步数、耗时、Token 目前是未测量。全文在 `apps/api/evals/report.md`。

在线试用：[https://retro-flow-seven.vercel.app/zh-CN](https://retro-flow-seven.vercel.app/zh-CN)。分析依赖云端额度，用尽后分析会失败；登录和列表仍可能可用。试用实例可能随时下线。

## 环境

- Node.js 22、pnpm 9
- Python 3.12+
- Docker Desktop
- 分析 / 助手需要 DeepSeek API Key；本地向量用 Ollama（`nomic-embed-text`）

## 启动

```powershell
docker compose up -d db
```

API：

```powershell
cd apps/api
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload
```

Web（另开终端）：

```powershell
cd apps/web
Copy-Item .env.example .env
corepack enable
pnpm install --frozen-lockfile
pnpm dev
```

页面 [http://localhost:3000/zh-CN](http://localhost:3000/zh-CN)，接口 [http://localhost:8000/docs](http://localhost:8000/docs)。

在 `apps/api/.env` 填 `LLM_API_KEY`。本地 embedding：

```powershell
ollama pull nomic-embed-text
```

`.env` 从 `.env.example` 复制，不要提交。常用项：


| 文件              | 变量                         | 本地值                              |
| --------------- | -------------------------- | -------------------------------- |
| `apps/api/.env` | `DATABASE_URL`             | Docker Postgres，`localhost:5433` |
|                 | `CORS_ORIGINS`             | `http://localhost:3000`          |
|                 | `LLM_API_KEY`              | DeepSeek 密钥                      |
|                 | `EMBEDDING_PROVIDER`       | `ollama`                         |
|                 | `RAG_MODE`                 | `hybrid`（可改为 `vector`）          |
|                 | `GITHUB_TOKEN`             | 可空；只放环境变量，不进工具参数               |
|                 | `MCP_USER_EMAIL`           | `demo@example.com`；只读 MCP 绑定的账号 |
| `apps/web/.env` | `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000/api/v1`   |




## 演示账号

API 启动时会自动准备 `demo@example.com` / `demo1234`。示例是三次「发布清单遗漏」：PR 模板已验收，CI 校验待验收，回滚演练进行中。账号已存在时只校正密码，不会覆盖这个账号下已有的数据。

若要强制重建示例（会删掉并重建这个账号）：

```powershell
cd apps/api
python -m app.seed_demo
```

助手要搜原文需要向量索引：先启动 Ollama，再执行：

```powershell
$env:DEMO_INDEX_CONTENT="true"
python -m app.seed_demo
```



## 本地 MCP

Cursor 可以通过 stdio 调用三个只读工具：`search_retro_content`、`list_actions`、`get_trends`。账号是进程环境变量 `MCP_USER_EMAIL`，参数里没有 `user_id`。提议行动和改状态不在这个服务里。

配置写在 `.cursor/mcp.json`。Postgres 和 `.env` 需要在本机可用；搜索原文另外需要 Ollama。改完配置后在 Cursor 里重新加载 MCP。这次只在进程内调用了这三个工具，没有在 Cursor 聊天里点过。

## 检查

```powershell
cd apps/api
ruff check app tests
pytest
.\.venv\Scripts\python.exe -m app.evals.report

cd ../web
pnpm lint
pnpm build
```

报告写到 `apps/api/evals/report.md`。三分钟演示录像和这次代码的线上部署还没有做。已有试用地址不一定包含当前工作区里的助手循环。

