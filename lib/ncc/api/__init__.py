from lib.ncc.api.v1 import document_controller
from lib.ncc.api.v1 import chat_controller


def authenticated_blueprints():
    """
    需要身份验证的路由列表 (模仿 Flask 风格)
    """
    return [
        document_controller.v1_document_bp,
        chat_controller.v1_chat_bp
    ]


def unauthenticated_blueprints():
    """
    无需身份验证的路由列表
    """
    return [
        # 后续登录等接口放在这里
    ]


def register_blueprints(app):
    """
    注册所有路由到 FastAPI 实例
    """
    # 统一挂载 v1 前缀
    for blueprint in authenticated_blueprints() + unauthenticated_blueprints():
        app.include_router(blueprint, prefix="/api/v1")
