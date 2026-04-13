from models.document_models import Document, DocumentChunk
from lib.ai.google_api.gemini_client import get_text_embedding

from fastapi import UploadFile, HTTPException
from sqlalchemy.orm import Session
from langchain_text_splitters import RecursiveCharacterTextSplitter
from typing import Optional, Type
import os
import re
import fitz


# --- 1. 原子工具：PDF 文本提取 ---
async def extract_text_from_pdf(file: UploadFile) -> str:
    """从 PDF 字节流中提取纯文本"""
    file_bytes = await file.read()
    pdf_doc = fitz.open(stream=file_bytes, filetype="pdf")

    text = "\n\n".join([page.get_text("text") for page in pdf_doc])
    pdf_doc.close()

    if not text.strip():
        raise HTTPException(status_code=400, detail="未能从 PDF 中提取有效文字")
    return text


# --- 2. 原子工具：智能文本切片 ---
def split_text_into_chunks(text: str, chunk_size: int = 800, overlap: int = 150) -> list[str]:
    """将长文本切分为带有重叠区的片段"""
    splitter = RecursiveCharacterTextSplitter(
        separators=["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""],
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        length_function=len
    )
    return splitter.split_text(text)


# --- 3. 原子工具：批量向量化入库 ---
def save_doc_with_chunks(db: Session, title: str, source: str, texts: list[str]) -> Document:
    """保存父文档并生成子分块向量入库"""
    doc = Document(title=title, source=source)
    db.add(doc)
    db.flush()

    for i, segment in enumerate(texts):
        chunk = DocumentChunk(
            document_id=doc.id, content=segment, content_length=len(segment),
            chunk_index=i, embedding=get_text_embedding(segment)
        )
        db.add(chunk)
    return doc


async def extract_text_from_txt(file: UploadFile) -> str:
    """提取 TXT 纯文本"""
    file_bytes = await file.read()
    # 大多数中文系统使用 utf-8，部分旧文件可能是 gbk
    try:
        return file_bytes.decode('utf-8')
    except UnicodeDecodeError:
        return file_bytes.decode('gbk')


# --- 4. 业务编排：上传并处理 PDF ---
def generate_default_title(filename: str) -> str:
    """智能提取标题：去除文件后缀，并将下划线、中划线替换为空格"""
    # 1. 剥离后缀名 (例如: "2024_Q1-Report.pdf" -> "2024_Q1-Report")
    base_name = os.path.splitext(filename)[0]

    # 2. 正则替换：将常见的连接符变为空格，使其更像一个标题
    clean_title = re.sub(r'[-_]', ' ', base_name)

    return clean_title.strip()


async def process_and_store_document(db: Session, file: UploadFile, custom_title: Optional[str] = None) -> Document:
    """编排服务：支持多格式读取 -> 切片 -> 入库"""
    filename = file.filename
    lower_filename = filename.lower()

    # --- 1. 确定最终标题与来源 ---
    # 如果前端传了 title 并且不为空白，就用用户的；否则智能提取
    final_title = custom_title if custom_title and custom_title.strip() else generate_default_title(filename)

    doc_source = filename

    # --- 2. 策略模式：读取文本 ---
    if lower_filename.endswith('.pdf'):
        full_text = await extract_text_from_pdf(file)
    elif lower_filename.endswith('.txt'):
        full_text = await extract_text_from_txt(file)
    else:
        raise HTTPException(status_code=400, detail="目前仅支持 PDF 和 TXT 格式")

    # --- 3. 切片与入库 ---
    chunks = split_text_into_chunks(full_text)

    # 传入确定的 final_title 和 doc_source
    doc = save_doc_with_chunks(db, final_title, doc_source, chunks)

    db.commit()
    db.refresh(doc)
    return doc


def get_document_preview(document: [Document, Type[Document]], max_length: int = 50) -> str:
    """
    Get text preview from the first chunk of a document.

    :param document: Document SQLAlchemy model instance
    :param max_length: Maximum characters for the preview (default: 50)
    :return: Preview string ending with '...' if truncated, or empty string
    """
    if not document.chunks:
        return ""

    # Find the first chunk safely
    first_chunk = next((c for c in document.chunks if c.chunk_index == 0), document.chunks[0])
    content = first_chunk.content

    # Truncate and append ellipsis if necessary
    if len(content) > max_length:
        return content[:max_length] + "..."

    return content


def get_similar_chunks_with_distance(db: Session, query_vector: list[float], limit: int = 3):
    """
    核心查询工具：根据向量搜索相似的文档切片，并附带余弦距离。
    专门供 /ask 接口做阈值判断使用。
    """
    return (
        db.query(
            DocumentChunk,
            DocumentChunk.embedding.cosine_distance(query_vector).label("distance")
        )
        .order_by("distance")
        .limit(limit)
        .all()
    )


def search_documents_by_vector(db: Session, query_vector: list[float], limit: int = 5):
    """
    [Public] 核心查询工具：跨表联查文档和切片。
    专门供前端 /search 搜索列表展示使用。
    """
    results = (
        db.query(
            DocumentChunk.id,
            DocumentChunk.content,
            DocumentChunk.document_id,
            Document.title.label("document_title"),  # Join parent title
            # 计算当前文档与用户问题的余弦距离，并将其命名为 distance
            DocumentChunk.embedding.cosine_distance(query_vector).label("distance")
        )
        .join(Document, DocumentChunk.document_id == Document.id)
        # 按距离从小到大排序（距离越小，语义越接近）
        .order_by(DocumentChunk.embedding.cosine_distance(query_vector))
        # 限制返回条数
        .limit(limit)
        .all()
    )

    return results


def get_top_chunk_with_score(db: Session, query_vector: list[float]):
    """[Public] 获取最匹配的一个分块及其距离，用于 Agent 决策"""
    return (
        db.query(
            DocumentChunk,
            DocumentChunk.embedding.cosine_distance(query_vector).label("distance")
        )
        .order_by("distance")
        .first()  # 只取第一名，用于快速判断阈值
    )
