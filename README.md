# RetroFlow

研发复盘改进系统。粘贴会议原文后，提取问题、识别复发、把行动落到证据和验收。仓库分 `apps/web`（Next.js）和 `apps/api`（FastAPI），数据用 PostgreSQL + pgvector。

登录后：新建复盘 → 分析 → 确认并发布行动 → 提交证据并验收。趋势、助手、周复盘从同一套数据读出。未配置 LLM 时，登录和列表仍可用。

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

| 文件 | 变量 | 本地值 |
|------|------|--------|
| `apps/api/.env` | `DATABASE_URL` | Docker Postgres，`localhost:5433` |
| | `CORS_ORIGINS` | `http://localhost:3000` |
| | `LLM_API_KEY` | DeepSeek 密钥 |
| | `EMBEDDING_PROVIDER` | `ollama` |
| `apps/web/.env` | `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000/api/v1` |

## 演示账号

```powershell
cd apps/api
python -m app.seed_demo
```

`demo@example.com` / `demo1234`。脚本可重复跑，只会删掉并重建这个账号。

助手要搜原文需要向量索引：先启动 Ollama，再执行：

```powershell
$env:DEMO_INDEX_CONTENT="true"
python -m app.seed_demo
```

## 检查

```powershell
cd apps/api
ruff check app tests
pytest

cd ../web
pnpm lint
pnpm build
```
