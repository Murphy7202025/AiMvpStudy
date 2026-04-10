from lib.utils import retry_request, get_model_name

from google import genai
from google.genai import types
from dotenv import load_dotenv


# 确保环境变量已加载
load_dotenv()

# 初始化全新版 Gemini 客户端
# 💡 贴心特性：只要你的 .env 里配置了 GEMINI_API_KEY，Client() 会自动读取，不需要手动传参了
client = genai.Client()


@retry_request()
def get_text_embedding(text: str, is_query: bool = False, model="gemini-embedding-001") -> list[float]:
    """
    调用 Gemini 接口，将文本转化为 768 维特征向量 (Embedding)。
    内部自动应用了 MRL 降维策略，确保返回的向量维度与数据库表结构(768维)完美兼容。

    :param text: 需要转化为向量的源文本。
    :param is_query: 标识当前是否为“搜索提问”场景。
                     - True: 针对用户输入的搜索问题，使用 RETRIEVAL_QUERY 优化检索意图。
                     - False (默认): 针对存入知识库的文档资料，使用 RETRIEVAL_DOCUMENT 优化存储特征。
    :param model: 使用的 Gemini 向量模型名称，默认为最新的原生多模态模型 "Gemini-embedding-001"。
    :return: 包含 768 个浮点数的特征向量列表 (List[float])。
    :raises Exception: 当 API 调用失败或网络异常时抛出。
    """
    try:
        # 根据是否是查询，动态切换任务类型
        current_task_type = "RETRIEVAL_QUERY" if is_query else "RETRIEVAL_DOCUMENT"

        response = client.models.embed_content(
            model=model,
            contents=text,
            config=types.EmbedContentConfig(
                task_type=current_task_type,
                output_dimensionality=768
            )
        )
        return response.embeddings[0].values

    except Exception as e:
        print(f"--- ❌ 生成 Embedding 失败: {e} ---")
        raise e


@retry_request()
def generate_answer_from_context(question: str, context: str, model: str = None) -> str:
    """
    根据提供的背景资料，调用 Gemini Flash 回答用户问题
    """
    model = model or get_model_name()

    # 构建极其重要的 Prompt (提示词)
    prompt = f"""
        你是一个专业的知识库问答助手。请严格根据以下提供的【背景资料】来回答用户的【问题】。
        要求：
        1. 如果背景资料中没有相关信息，请直接回答“知识库中没有找到相关答案”，绝对不要自己瞎编。
        2. 回答要清晰、简洁、有条理。
        
        【背景资料】：
        {context}
        
        【问题】：
        {question}
    """
    try:
        response = client.models.generate_content(
            model=model,
            contents=prompt
        )
        return response.text

    except Exception as e:
        print(f"--- ❌ 生成回答失败: {e} ---")
        raise e
