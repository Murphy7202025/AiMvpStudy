import time
import socket
import traceback
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from lib.database.utils import create_database_if_not_exists, session, engine
# 导入 v1 注册逻辑
from lib.ncc.api import register_blueprints


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时：自动化建库
    create_database_if_not_exists()
    yield
    # 关闭时：清理 scoped_session
    session.remove()
    engine.dispose()


def create_app(description: str, version: str = "1.0.0"):
    app = FastAPI(title=description, version=version, lifespan=lifespan)

    # 1. 跨域配置
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 2. 调用注册函数 (核心修改)
    register_blueprints(app)

    # 3. 模拟 after_request 日志逻辑
    @app.middleware("http")
    async def log_middleware(request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        duration = round(time.time() - start_time, 6)
        print(f"[{request.method}] {request.url.path} - {response.status_code} ({duration}s)")
        return response

    # 4. 全局异常捕捉
    @app.exception_handler(Exception)
    async def handle_500(request: Request, exc: Exception):
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"message": "An unknown error has occurred"})

    return app
