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


@retry_request()
def generate_answer_with_search(question: str, context: str = "", model: str = None) -> str:
    """智能体问答：带联网搜索能力的生成器"""
    model = model or get_model_name()

    # 如果有本地 context，就让它结合；如果没有，就纯靠自己和联网
    prompt_text = question
    if context:
        prompt_text = f"参考资料：\n{context}\n\n基于资料，并结合你的知识或联网搜索，回答：{question}"

    try:
        response = client.models.generate_content(
            model=model,
            contents=prompt_text,
            config=types.GenerateContentConfig(
                temperature=0.4,
                # 💡 核心魔法：直接赋予大模型谷歌搜索的能力！
                tools=[{"google_search": {}}],
            )
        )
        return response.text
    except Exception as e:
        print(f"--- ❌ 联网生成回答失败: {e} ---")
        raise e


@retry_request()
def generate_answer_with_memory(question: str, context: str, history: list, model: str = None) -> str:
    """
    企业级多轮对话生成器：融合 RAG 上下文与短期记忆
    :param question: 用户当前的最新提问
    :param context: 从向量数据库检索出的文本（如果没有则为空字符串）
    :param history: 格式化后的历史对话列表 [{"role": "user", "parts": ["..."]}, ...]
    :param model: 使用的 Gemini 模型名称，默认从配置获取
    :return: AI 生成的回答文本
    """
    model = model or get_model_name()

    try:
        # 1. 转换历史记录格式
        # 严格遵守 google-genai SDK 规范，将普通字典转换为 types.Content 对象
        formatted_history = []
        for msg in history:
            formatted_history.append(
                types.Content(
                    role=msg["role"],
                    parts=[types.Part.from_text(text=msg["parts"][0])]
                )
            )

        # 2. 设置系统人设 (System Instruction)
        # 规定 AI 的行为边界和回答偏好
        sys_instruct = (
            "你是一个专业的企业级知识库与业务助手。请结合上下文和历史对话回答问题。\n"
            "要求：\n"
            "1. 优先使用'参考资料'中的信息来回答。\n"
            "2. 如果参考资料无法完全涵盖，请结合你的常识和前文对话回答。\n"
            "3. 保持专业、客观的语气。"
        )

        # 3. 动态组装当前 Prompt
        # 将 RAG 检索到的内容作为“外挂插件”悄悄放在用户问题的前面
        current_prompt = question
        if context:
            current_prompt = f"以下是系统刚刚为你检索到的内部参考资料：\n{context}\n\n基于以上资料和我们的历史对话，请回答我的问题：{question}"

        # 4. 实例化自带记忆的 Chat Session
        chat = client.chats.create(
            model=model,
            config=types.GenerateContentConfig(
                system_instruction=sys_instruct,
                temperature=0.3,  # 降低发散性，保证 RAG 问答的严谨度
            ),
            history=formatted_history
        )

        # 5. 发送请求
        # print(f"--- 🤖 正在调用 Gemini，当前附带了 {len(formatted_history)} 条历史记忆 ---")
        response = chat.send_message(current_prompt)

        return response.text

    except Exception as e:
        print(f"--- ❌ 多轮对话生成失败: {e} ---")
        raise e


def format_chat_history(history: list) -> list[types.Content]:
    """将数据库字典格式转换为 Gemini SDK 原生 Content 对象"""
    return [
        types.Content(
            role=msg["role"],
            parts=[types.Part.from_text(text=msg["parts"][0])]
        ) for msg in history
    ]


# --- 辅助函数：Prompt 拼装 ---
def build_rag_prompt(question: str, context: str) -> str:
    """根据是否拥有上下文，动态生成 Prompt"""
    if not context:
        return question
    return f"检索到的参考资料：\n{context}\n\n结合资料和历史对话，回答：{question}"


# --- 主调用函数 ---
@retry_request()
def generate_answer_with_memory(question: str, history: list, model: str = None) -> str:
    """基础Chat生成器"""
    chat = client.chats.create(
        model=model or get_model_name(),
        config=types.GenerateContentConfig(
            temperature=0.3,
        ),
        history=format_chat_history(history)
    )

    response = chat.send_message(question)
    return response.text
