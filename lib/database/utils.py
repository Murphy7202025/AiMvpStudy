import os
import logging
from contextlib import contextmanager
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, scoped_session
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 设置日志：开发环境下 WARNING 足够，避免向量数据刷屏
logging.basicConfig()
logger = logging.getLogger('sqlalchemy.engine')
logger.setLevel(logging.WARNING)


def database_url():
    """拼接 SQLAlchemy 连接字符串"""
    user = os.getenv('DB_USER')
    password = os.getenv('DB_PASSWORD')
    host = os.getenv('DB_HOST')
    port = os.getenv('DB_PORT')
    db_name = os.getenv('DB_NAME')
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{db_name}"


# 1. 全局 Engine 配置
engine = create_engine(
    database_url(),
    echo=False,
    pool_size=100,
    max_overflow=100,
    pool_pre_ping=True
)

# 2. 统一会话工厂
# 所有 Session 均由此产生，保证配置一致
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# 3. 提供给 FastAPI 的依赖注入函数 (最推荐用法)
def get_db():
    """
    用于 FastAPI Depends(get_db)。
    由 FastAPI 自动管理连接的开启、异常处理和关闭。
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# 4. 事务范围上下文管理器 (用于脚本、定时任务或不便使用 Depends 的地方)
@contextmanager
def session_scope():
    """
    用法:
    with session_scope() as db:
        db.query(...)
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()


# 5. 线程安全 Session (备用方案)
# 如果你有些旧代码必须直接调用全局对象，保留这个 scoped_session
# 但请注意：在 FastAPI 的 async 函数中尽量避免直接使用它
session = scoped_session(SessionLocal)


# 6. 数据库初始化逻辑
def init_db_extensions():
    """初始化 pgvector 扩展"""
    try:
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()
            print("--- ✅ pgvector extension is ready. ---")
    except Exception as e:
        print(f"--- ❌ Failed to create pgvector extension: {e} ---")


def create_database_if_not_exists():
    """自动化物理建库逻辑"""
    db_name = os.getenv('DB_NAME')
    user = os.getenv('DB_USER')
    password = os.getenv('DB_PASSWORD')
    host = os.getenv('DB_HOST')
    port = os.getenv('DB_PORT')

    admin_url = f"postgresql+psycopg://{user}:{password}@{host}:{port}/postgres"
    temp_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")

    try:
        with temp_engine.connect() as conn:
            query = text("SELECT 1 FROM pg_database WHERE datname = :db_name")
            exists = conn.execute(query, {"db_name": db_name}).scalar()

            if not exists:
                print(f"--- ⚠️ Database '{db_name}' not found, creating... ---")
                conn.execute(text(f'CREATE DATABASE "{db_name}"'))
                print(f"--- ✅ Database '{db_name}' created successfully. ---")

            # 库检查完毕后，立即初始化向量扩展
            init_db_extensions()

    except Exception as e:
        print(f"--- ❌ Error during database auto-creation: {e} ---")
    finally:
        temp_engine.dispose()
