# GeminiClaw — 企业级 RAG 知识库问答系统（后端）

基于 RAG（检索增强生成）架构的 AI 知识库问答系统后端服务。支持 PDF/TXT 文档上传、智能分块向量化、语义检索、多轮流式对话，并具备 Agentic 路由决策能力（本地知识库优先，不命中时自动联网搜索）。

> 🚧 **本项目持续迭代中，部分功能仍在开发完善，未达到生产可用状态。**

---

## 技术栈

| 类别 | 技术 |
|------|------|
| Web 框架 | FastAPI + Uvicorn |
| 数据库 | PostgreSQL 17 + pgvector（向量检索） |
| ORM | SQLAlchemy 2.0 + Alembic（迁移管理） |
| AI 模型 | Google Gemini API（google-genai SDK） |
| 文档处理 | PyMuPDF（PDF 解析）+ LangChain Text Splitter（智能分块） |
| 环境管理 | Pipenv |
| 容器化 | Docker + Docker Compose |

---

## 项目结构

```
AiMvpStudy/
├── main.py                         # 应用入口
├── Pipfile                         # 依赖管理
├── docker-compose.yml              # 数据库容器配置
├── alembic.ini                     # Alembic 配置
│
├── lib/
│   ├── app/
│   │   └── utils.py                # FastAPI 应用工厂（lifespan、中间件、异常处理）
│   ├── database/
│   │   └── utils.py                # 数据库连接、Session 管理
│   ├── ai/
│   │   └── google_api/
│   │       └── gemini_client.py    # Gemini API 封装（Embedding、生成、流式、联网搜索）
│   ├── ncc/
│   │   └── api/
│   │       ├── __init__.py         # Blueprint 注册
│   │       └── v1/
│   │           ├── chat_controller.py      # 流式对话接口
│   │           ├── document_controller.py  # 文档管理接口
│   │           ├── schemas/                # Pydantic 请求/响应模型
│   │           └── services/              # 业务逻辑层
│   │               ├── chat_services.py
│   │               └── document_services.py
│   └── utils.py                    # 公共工具（retry 装饰器、get_model_name）
│
├── models/
│   ├── base.py                     # DeclarativeBase + BlameMixin + DeletableMixin
│   ├── document_models.py          # Document / DocumentChunk
│   └── chat_models.py              # ChatSession / ChatMessage
│
└── migrations/
    └── versions/                   # Alembic 迁移版本文件
```

---

## 核心功能

### RAG 知识库问答
- 文档上传（PDF / TXT），自动解析并智能分块（800字/块，150字重叠防上下文断裂）
- 每个分块独立向量化（Gemini `gemini-embedding-001`，768维）并存入 pgvector
- 用户提问时，将问题向量化后进行余弦相似度检索，过滤距离 > 0.4 的无关结果
- 检索结果拼接为上下文，组装 Prompt 调用 Gemini 生成最终回答

### Agentic 路由
- 检索最相关分块，若余弦距离 > 0.6 则判定本地知识库无匹配
- 自动降级至 Google Search Tool 联网搜索，兜底本地知识库覆盖不到的问题

### 多轮流式对话
- 对话历史持久化至 `chat_sessions` / `chat_messages` 表
- 每轮请求加载最近 10 条历史注入 Gemini Chat Session，保持上下文连贯
- 基于 SSE（Server-Sent Events）实现流式输出，后端将 Gemini chunk 按字符拆分推送，解决大粒度 chunk 导致的"块状输出"体验问题

---

## 快速开始

### 1. 环境要求

- Python 3.10+
- Docker & Docker Compose
- Pipenv

### 2. 克隆项目

```bash
git clone https://github.com/your-username/GeminiClaw.git
cd GeminiClaw
```

### 3. 配置环境变量

在项目根目录创建 `.env` 文件：

```env
# 数据库配置
DB_USER=postgres
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5433
DB_NAME=ai_db

# Gemini API
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL_NAME=gemini-2.5-flash
```

### 4. 启动数据库

```bash
docker-compose up -d
```

启动后 PostgreSQL 运行在 `localhost:5433`（宿主机端口），容器内部端口为 5432。

### 5. 安装依赖

```bash
pipenv install --skip-lock
```

### 6. 执行数据库迁移

```bash
pipenv run alembic upgrade head
```

迁移脚本会自动完成以下操作：
- 启用 `pgvector` 扩展
- 创建 `system_configs`、`documents`、`document_chunks`、`chat_sessions`、`chat_messages` 表
- 为向量字段创建 HNSW 余弦距离索引（`vector_cosine_ops`）

### 7. 启动服务

```bash
pipenv run python main.py
```

服务默认运行在 `http://0.0.0.0:8000`，热重载已开启。

---

## API 文档

启动服务后访问 Swagger UI：

```
http://localhost:8000/docs
```

### 主要接口

| 方法 | 路径 | 描述 |
|------|------|------|
| `GET` | `/api/v1/documents` | 获取所有文档列表（含内容预览） |
| `POST` | `/api/v1/documents` | 新增文档（文本，自动分块向量化） |
| `POST` | `/api/v1/documents/upload` | 上传文件（PDF / TXT） |
| `POST` | `/api/v1/documents/search` | 语义向量搜索 |
| `POST` | `/api/v1/documents/ask` | RAG 知识库问答 |
| `POST` | `/api/v1/documents/research` | Agentic 问答（本地 + 联网兜底） |
| `POST` | `/api/v1/chat` | 多轮流式对话（SSE） |

---

## 数据库设计

```
documents                    # 文档元数据
├── id
├── title
├── source                   # 文件名 / 来源
└── created_at / updated_at / created_by / updated_by

document_chunks              # 文档分块 + 向量
├── id
├── document_id (FK)
├── content                  # 分块文本
├── content_length
├── chunk_index              # 块在原文中的顺序
├── embedding                # 768维向量（HNSW 余弦索引）
└── created_at / updated_at / created_by / updated_by

chat_sessions                # 对话会话
├── id
├── title
└── ...

chat_messages                # 对话消息
├── id
├── session_id (FK)
├── role                     # user / model
├── content
└── ...
```

---

## 工程规范

- **三层架构**：Controller（路由）→ Service（业务逻辑）→ Model（数据模型），职责清晰
- **BlameMixin**：所有表统一继承审计字段（`created_at`、`created_by`、`updated_at`、`updated_by`）
- **DeletableMixin**：软删除支持（`is_deleted` 字段）
- **Alembic 版本管理**：所有数据库变更通过迁移脚本管理，禁止手动修改表结构
- **指数退避重试**：`@retry_request` 装饰器封装 Gemini API 调用，最大重试 3 次，退避系数 2，解决网络抖动问题
- **连接池配置**：`pool_size=10`，`max_overflow=20`，`pool_pre_ping=True` 防止 stale connection

---

## 环境变量说明

| 变量名 | 必填 | 说明 |
|--------|------|------|
| `DB_USER` | ✅ | 数据库用户名 |
| `DB_PASSWORD` | ✅ | 数据库密码 |
| `DB_HOST` | ✅ | 数据库地址（Docker 环境填 `localhost`） |
| `DB_PORT` | ✅ | 宿主机映射端口（默认 `5433`） |
| `DB_NAME` | ✅ | 数据库名称 |
| `GEMINI_API_KEY` | ✅ | Google Gemini API Key |
| `GEMINI_MODEL_NAME` | ❌ | 使用的模型名（默认 `gemini-2.5-flash`） |