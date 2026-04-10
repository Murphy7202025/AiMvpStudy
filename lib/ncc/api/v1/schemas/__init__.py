from pydantic import BaseModel, ConfigDict


class BaseSchema(BaseModel):
    """
    项目中所有 Schema 的全局基类。
    这里配置的 Config 会被所有子类继承，实现全局统一行为。
    """
    model_config = ConfigDict(
        # 1. 最核心：允许 Pydantic 直接读取 SQLAlchemy 的 ORM 对象属性
        from_attributes=True,

        # 2. 【福利配置】自动去除字符串首尾的空格（防止前端多传了空格引发脏数据）
        str_strip_whitespace=True,

        # 3. 【福利配置】允许通过别名或原字段名进行赋值（方便后续做驼峰命名和蛇形命名转换）
        populate_by_name=True,
    )
