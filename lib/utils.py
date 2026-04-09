import time
from functools import wraps
from typing import Callable, Any


def retry_request(max_retries: int = 3, initial_delay: float = 1.0, backoff_factor: float = 2.0):
    """
    企业级网络请求重试装饰器。
    :param max_retries: 最大重试次数
    :param initial_delay: 第一次失败后的等待时间（秒）
    :param backoff_factor: 退避系数（默认2倍，即等待 1s, 2s, 4s...），有效缓解拥堵网络
    """

    def decorator(func: Callable) -> Callable:
        # @wraps 的作用是保留原函数的名字和注释，防止被装饰器覆盖（这在排查 Bug 时极其重要）
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            current_delay = initial_delay

            for attempt in range(max_retries):
                try:
                    # 尝试执行原函数
                    return func(*args, **kwargs)

                except Exception as e:
                    if attempt < max_retries - 1:
                        func_name = func.__name__
                        print(f"--- ⚠️ [{func_name}] 执行失败 (第{attempt + 1}次)。"
                              f"{current_delay}秒后重试... 错误信息: {e} ---")

                        time.sleep(current_delay)
                        # 核心：每次失败后，等待时间翻倍，防止在网络极其拥堵时疯狂敲击对方服务器
                        current_delay *= backoff_factor
                    else:
                        print(f"--- ❌ [{func.__name__}] 已达到最大重试次数 ({max_retries})，彻底放弃: {e} ---")
                        raise e

        return wrapper

    return decorator
