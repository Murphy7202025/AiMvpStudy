from contextlib import contextmanager
from sqlalchemy import create_engine, text
from sqlalchemy.orm import scoped_session, sessionmaker
from dotenv import load_dotenv

import os
import logging

# 加载环境变量
load_dotenv()

# 设置日志，避免在生产环境输出过多调试信息
logging.basicConfig()
logger = logging.getLogger('sqlalchemy.engine')
logger.setLevel(logging.INFO)


def database_url():
    """
    拼接 SQLAlchemy 连接字符串。
    注意：此连接指向 .env 中指定的具体业务数据库（如 ai_db）。
    """
    user = os.getenv('DB_USER')
    password = os.getenv('DB_PASSWORD')
    host = os.getenv('DB_HOST')
    port = os.getenv('DB_PORT')
    db_name = os.getenv('DB_NAME')
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{db_name}"


# 1. 创建全局 Engine
# pool_size 和 max_overflow 参考了你提供的 Flask 项目配置，适合高并发场景
engine = create_engine(
    database_url(),
    echo=False,  # 如果需要查看 SQL 执行细节，可设为 True
    pool_size=100,  # 保持 100 个连接池容量
    max_overflow=100,  # 允许额外溢出 100 个连接
    pool_pre_ping=True  # 每次请求前检查连接是否失效（解决 Docker 重启后的 stale connection 问题）
)

# 2. 创建并设置 scoped_session
# 确保在 FastAPI 或多线程脚本中，每个线程都能获得独立的会话
session = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))


def create_database_if_not_exists():
    """
    自动化物理数据库建库逻辑：
    此逻辑仅在启动 main.py 时作为保障运行。
    真正的表结构、扩展（Extension）和索引应当由 Alembic 迁移脚本完成。
    """
    db_name = os.getenv('DB_NAME')
    user = os.getenv('DB_USER')
    password = os.getenv('DB_PASSWORD')
    host = os.getenv('DB_HOST')
    port = os.getenv('DB_PORT')

    # 连接到系统默认的 'postgres' 数据库以执行建库指令
    admin_url = f"postgresql+psycopg://{user}:{password}@{host}:{port}/postgres"

    # isolation_level="AUTOCOMMIT" 是必须的，因为 PostgreSQL 不允许在事务中创建数据库
    temp_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")

    try:
        with temp_engine.connect() as conn:
            # 检查数据库是否存在
            query = text("SELECT 1 FROM pg_database WHERE datname = :db_name")
            exists = conn.execute(query, {"db_name": db_name}).scalar()

            if not exists:
                print(f"--- ⚠️ Database '{db_name}' not found, creating... ---")
                # 使用 SQL 文本执行建库
                conn.execute(text(f'CREATE DATABASE "{db_name}"'))
                print(f"--- ✅ Database '{db_name}' created successfully. ---")
            else:
                # 库已存在则静默跳过，符合交付逻辑
                pass
    except Exception as e:
        print(f"--- ❌ Error during database auto-creation: {e} ---")
    finally:
        temp_engine.dispose()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
session_factory = scoped_session(SessionLocal)


@contextmanager
def session_scope():
    """
    提供一个事务范围的会话管理。
    用法:
        with session_scope() as session:
            session.add(some_object)
    """
    # 创建一个具体的 session 实例
    db_session = session_factory()
    try:
        yield db_session          # 将 session 交给 with 块内的代码使用
        db_session.commit()       # 如果没报错，自动提交事务
    except Exception as e:
        db_session.rollback()     # 🚨 一旦 with 块内发生异常，立即自动回滚，保护数据库
        raise e                # 将错误继续抛出，方便上层（如 FastAPI 拦截器）处理
    finally:
        db_session.close()
