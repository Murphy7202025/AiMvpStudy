from google import genai
from google.genai import types
from dotenv import load_dotenv

# 确保环境变量已加载
load_dotenv()

# 初始化全新版 Gemini 客户端
# 💡 贴心特性：只要你的 .env 里配置了 GEMINI_API_KEY，Client() 会自动读取，不需要手动传参了
client = genai.Client()


def get_text_embedding(text: str) -> list[float]:
    """
    调用 Gemini 接口，将文本转化为向量 (基于最新版 google-genai SDK)
    """
    try:
        # 新版 SDK 的调用方式统一收口在 client.models 下
        response = client.models.embed_content(
            model="text-embedding-004",
            contents=text,
            # 新版 SDK 使用强类型的 Config 对象来传递额外参数
            config=types.EmbedContentConfig(
                task_type="RETRIEVAL_DOCUMENT"
            )
        )

        # 新版 SDK 的返回值是一个强类型对象，不再是普通字典
        # 我们提取第一个 embedding 结果的 values 数组 (即 768 维的浮点数列表)
        return response.embeddings[0].values

    except Exception as e:
        print(f"--- ❌ 生成 Embedding 失败: {e} ---")
        raise e
