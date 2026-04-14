"""
构建三月七角色 RAG 知识库
数据来源：
- march7th_settings.txt (High)
- role_settings.txt (High)
- background_settings.txt (High)
- relationship_net.txt (High)
- plot_settings.txt (High)
- dialogue_data.txt assistant消息 (High)
"""
import os

import env_setup

import re
import json
from sentence_transformers import SentenceTransformer
import chromadb
from pathlib import Path

import config

RAG_DIR = Path(__file__).parent / "rag_db"
EMBEDDING_MODEL = config.EMBEDDING_MODEL
DATA_DIR = Path(__file__).parent / "resources" / "rag"


def split_into_chunks(text: str, chunk_size: int = 500, overlap: int = 50) -> list:
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk.strip())
        start += chunk_size - overlap

    return chunks


def load_march7th_settings():
    documents = []
    file_path = DATA_DIR / "march7th_settings.txt"

    if not file_path.exists():
        print(f"警告: {file_path} 不存在")
        return documents

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    paragraphs = content.split('\n\n')

    current_section = "开场介绍"

    evaluation_keywords = [
        '丹恒对三月七的评价', '姬子对三月七的评价',
        '瓦尔特·杨对三月七的评价', '叽米对三月七的评价',
        '云璃对三月七的评价', '白露对三月七的评价', '飞霄对三月七的评价'
    ]

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        lines = para.split('\n')
        first_line = lines[0].strip()

        is_evaluation = False
        for keyword in evaluation_keywords:
            if first_line.startswith(keyword):
                is_evaluation = True
                current_section = keyword
                break

        if first_line and not is_evaluation and len(first_line) < 15:
            current_section = first_line

        chunks = split_into_chunks(para)
        for i, chunk in enumerate(chunks):
            documents.append({
                "content": chunk,
                "source": "march7th_settings",
                "type": "role_background",
                "quality": "high",
                "section": current_section,
                "chunk_id": i
            })

    print(f"  march7th_settings: {len(documents)} 条")
    return documents


def load_role_settings():
    documents = []
    file_path = DATA_DIR / "role_settings.txt"

    if not file_path.exists():
        print(f"警告: {file_path} 不存在")
        return documents

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    pattern = r'\*?\*?从三月七的视角看[^\*\n]+'

    matches = list(re.finditer(pattern, content))

    for i, match in enumerate(matches):
        start = match.start()
        end = match.end()

        header = match.group(0).strip('*').strip()

        next_start = matches[i+1].start() if i + \
            1 < len(matches) else len(content)
        role_content = content[end:next_start].strip()

        if role_content and len(role_content) > 10:
            chunks = split_into_chunks(role_content)
            for j, chunk in enumerate(chunks):
                documents.append({
                    "content": f"【{header}】{chunk}",
                    "source": "role_settings",
                    "type": "role_relationship",
                    "quality": "high",
                    "role": header.replace('从三月七的视角看', ''),
                    "chunk_id": j
                })

    print(f"  role_settings: {len(documents)} 条")
    return documents


def load_background_settings():
    documents = []
    file_path = DATA_DIR / "background_settings.txt"

    if not file_path.exists():
        print(f"警告: {file_path} 不存在")
        return documents

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    paragraphs = content.split('\n\n')

    current_section = "基础设定"
    current_subsection = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        lines = para.split('\n')
        first_line = lines[0].strip()

        if first_line.startswith('**') and first_line.endswith('**'):
            current_subsection = first_line[2:-2]
            body = '\n'.join(lines[1:]).strip()
            if body:
                chunks = split_into_chunks(body)
                for i, chunk in enumerate(chunks):
                    documents.append({
                        "content": chunk,
                        "source": "background_settings",
                        "type": "world_knowledge",
                        "quality": "high",
                        "section": current_section,
                        "subsection": current_subsection,
                        "chunk_id": i
                    })
        elif first_line.startswith('**') and '——' in para:
            parts = para.split('**')
            if len(parts) >= 2:
                current_subsection = parts[1].split('**')[0]
                body = para[len('**' + parts[1] + '**'):].strip()
                if body.startswith('——'):
                    body = body[1:].strip()
                if body:
                    chunks = split_into_chunks(body)
                    for i, chunk in enumerate(chunks):
                        documents.append({
                            "content": chunk,
                            "source": "background_settings",
                            "type": "world_knowledge",
                            "quality": "high",
                            "section": current_section,
                            "subsection": current_subsection,
                            "chunk_id": i
                        })
        else:
            chunks = split_into_chunks(para)
            for i, chunk in enumerate(chunks):
                documents.append({
                    "content": chunk,
                    "source": "background_settings",
                    "type": "world_knowledge",
                    "quality": "high",
                    "section": current_section,
                    "subsection": current_subsection,
                    "chunk_id": i
                })

    print(f"  background_settings: {len(documents)} 条")
    return documents


def load_relationship_net():
    documents = []
    file_path = DATA_DIR / "relationship_net.txt"

    if not file_path.exists():
        print(f"警告: {file_path} 不存在")
        return documents

    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    for line in lines:
        line = line.rstrip('\n').strip()

        if not line or '——' not in line:
            continue

        parts = line.split('——', 1)
        if len(parts) == 2:
            role = parts[0].strip()
            desc = parts[1].strip()

            if role and desc:
                documents.append({
                    "content": f"{role}：{desc}",
                    "source": "relationship_net",
                    "type": "relationship",
                    "quality": "high",
                    "role": role
                })

    print(f"  relationship_net: {len(documents)} 条")
    return documents


def load_plot_settings():
    documents = []
    file_path = DATA_DIR / "plot_settings.txt"

    if not file_path.exists():
        print(f"警告: {file_path} 不存在")
        return documents

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    paragraphs = content.split('\n\n')

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        colon_idx = para.find('：')
        if colon_idx == -1:
            colon_idx = para.find(':')

        if colon_idx > 0 and colon_idx < 30:
            chapter = para[:colon_idx]
            body = para[colon_idx+1:].strip()
            if body:
                chunks = split_into_chunks(body)
                for i, chunk in enumerate(chunks):
                    documents.append({
                        "content": chunk,
                        "source": "plot_settings",
                        "type": "plot",
                        "quality": "high",
                        "chapter": chapter,
                        "chunk_id": i
                    })
        else:
            chunks = split_into_chunks(para)
            for i, chunk in enumerate(chunks):
                documents.append({
                    "content": chunk,
                    "source": "plot_settings",
                    "type": "plot",
                    "quality": "high",
                    "chapter": "未分类",
                    "chunk_id": i
                })

    print(f"  plot_settings: {len(documents)} 条")
    return documents


def load_dialogue_data():
    documents = []
    file_path = DATA_DIR / "dialogue_data.txt"

    if not file_path.exists():
        print(f"警告: {file_path} 不存在")
        return documents

    with open(file_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            try:
                data = json.loads(line)
                messages = data.get("messages", [])

                for msg in messages:
                    if msg.get("role") == "assistant":
                        content = msg.get("content", "").strip()
                        if content:
                            documents.append({
                                "content": content,
                                "source": "dialogue_data",
                                "type": "original_dialogue",
                                "quality": "high",
                                "line_num": line_num
                            })
            except json.JSONDecodeError:
                continue

    print(f"  dialogue_data (assistant): {len(documents)} 条")
    return documents


def build_vector_store(documents: list, persist_dir: Path):
    if not documents:
        print("警告: 没有文档可添加")
        return None, None, None

    print(f"\n加载 Embedding 模型: {EMBEDDING_MODEL}")
    embedding_model = SentenceTransformer(EMBEDDING_MODEL, device="cuda")

    print("初始化 ChromaDB...")
    client = chromadb.PersistentClient(path=str(persist_dir))

    try:
        client.delete_collection("march7th_knowledge")
    except:
        pass

    collection = client.create_collection("march7th_knowledge")

    print(f"添加 {len(documents)} 条文档到向量数据库...")
    batch_size = 100
    for i in range(0, len(documents), batch_size):
        batch = documents[i:i+batch_size]
        texts = [d["content"] for d in batch]
        metadatas = []
        for d in batch:
            meta = {
                "source": d["source"],
                "type": d["type"],
                "quality": d["quality"]
            }
            for key in ["section", "category", "chapter", "chunk_id", "line_num"]:
                if key in d:
                    meta[key] = str(d[key])
            metadatas.append(meta)

        ids = [f"doc_{d['source']}_{i}_{j}"
               for j, d in enumerate(batch)]

        embeddings = embedding_model.encode(texts, show_progress_bar=False)

        collection.add(
            documents=texts,
            embeddings=embeddings.tolist(),
            metadatas=metadatas,
            ids=ids
        )

        if (i // batch_size + 1) % 5 == 0:
            print(
                f"  已处理: {min(i + batch_size, len(documents))}/{len(documents)}")

    return collection, embedding_model


def test_retrieval(collection, embedding_model, query: str, k: int = 5):
    if collection is None:
        return

    print(f"\n查询: {query}")
    print("-" * 50)

    query_embedding = embedding_model.encode([query])

    results = collection.query(
        query_embeddings=query_embedding.tolist(),
        n_results=k
    )

    for i, (doc, meta) in enumerate(zip(results["documents"][0],
                                        results["metadatas"][0]), 1):
        print(f"\n[结果 {i}]")
        print(
            f"来源: {meta.get('source', 'unknown')} | 类型: {meta.get('type', 'unknown')}")
        if 'chapter' in meta:
            print(f"章节: {meta['chapter']}")
        if 'section' in meta:
            print(f"主题: {meta['section']}")
        print(f"内容: {doc[:150]}...")


def build_character_rag(character_id: str, character_name: str, collection_name: str,
                         text_content: str, persist_dir: Path = None):
    if persist_dir is None:
        persist_dir = RAG_DIR

    if not text_content.strip():
        print("警告: 没有文本内容可添加")
        return None, None

    documents = []
    chunks = split_into_chunks(text_content)
    for i, chunk in enumerate(chunks):
        if chunk.strip():
            documents.append({
                "content": chunk,
                "source": f"{character_id}_user_upload",
                "type": "character_knowledge",
                "quality": "high",
                "chunk_id": i
            })

    if not documents:
        print("警告: 分块后没有有效文档")
        return None, None

    print(f"加载 Embedding 模型: {EMBEDDING_MODEL}")
    embedding_model = SentenceTransformer(EMBEDDING_MODEL, device="cuda")

    print("初始化 ChromaDB...")
    client = chromadb.PersistentClient(path=str(persist_dir))

    try:
        client.delete_collection(collection_name)
    except:
        pass

    collection = client.create_collection(collection_name)

    print(f"添加 {len(documents)} 条文档到向量数据库...")
    batch_size = 100
    for i in range(0, len(documents), batch_size):
        batch = documents[i:i+batch_size]
        texts = [d["content"] for d in batch]
        metadatas = [{"source": d["source"], "type": d["type"], "quality": d["quality"]} for d in batch]
        ids = [f"doc_{d['source']}_{i}_{j}" for j, d in enumerate(batch)]

        embeddings = embedding_model.encode(texts, show_progress_bar=False)
        collection.add(
            documents=texts,
            embeddings=embeddings.tolist(),
            metadatas=metadatas,
            ids=ids
        )

    meta_path = persist_dir / f"{collection_name}_meta.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump({
            "character_id": character_id,
            "character_name": character_name,
            "collection_name": collection_name,
            "document_count": len(documents),
        }, f, ensure_ascii=False, indent=2)

    print(f"RAG 知识库构建完成: {len(documents)} 条文档, 集合: {collection_name}")
    return collection, embedding_model


def get_rag_collection_info(persist_dir: Path = None):
    if persist_dir is None:
        persist_dir = RAG_DIR

    if not persist_dir.exists():
        return []

    client = chromadb.PersistentClient(path=str(persist_dir))
    collection_names = client.list_collections()

    result = []
    for coll_name in collection_names:
        if not isinstance(coll_name, str):
            coll_name = str(coll_name)
        
        try:
            collection = client.get_collection(coll_name)
            count = collection.count()
        except Exception:
            count = 0

        meta_path = persist_dir / f"{coll_name}_meta.json"
        meta_info = {}
        if meta_path.exists():
            with open(meta_path, "r", encoding="utf-8") as f:
                meta_info = json.load(f)

        result.append({
            "collection_name": coll_name,
            "document_count": count,
            "character_id": meta_info.get("character_id", ""),
            "character_name": meta_info.get("character_name", ""),
        })

    return result


def delete_rag_collection(collection_name: str, persist_dir: Path = None):
    if persist_dir is None:
        persist_dir = RAG_DIR

    client = chromadb.PersistentClient(path=str(persist_dir))
    try:
        client.delete_collection(collection_name)
        meta_path = persist_dir / f"{collection_name}_meta.json"
        if meta_path.exists():
            meta_path.unlink()
        return True
    except Exception as e:
        print(f"删除集合失败: {e}")
        return False


def main():
    print("=" * 50)
    print("构建三月七 RAG 知识库")
    print("=" * 50)

    RAG_DIR.mkdir(parents=True, exist_ok=True)

    all_documents = []

    print("\n加载数据源...")
    all_documents.extend(load_march7th_settings())
    all_documents.extend(load_role_settings())
    all_documents.extend(load_background_settings())
    all_documents.extend(load_relationship_net())
    all_documents.extend(load_plot_settings())
    all_documents.extend(load_dialogue_data())

    print(f"\n总计加载文档: {len(all_documents)} 条")

    print("\n构建向量数据库...")
    collection, embedding_model = build_vector_store(all_documents, RAG_DIR)

    print("\n测试检索...")
    test_queries = [
        "三月七的身世是什么？",
        "她和丹恒是什么关系？",
        "在贝洛伯格发生了什么？",
        "她喜欢做什么？",
    ]

    for query in test_queries:
        test_retrieval(collection, embedding_model, query, k=3)

    print("\n" + "=" * 50)
    print(f"RAG 知识库已保存到: {RAG_DIR}")
    print(f"总计: {len(all_documents)} 条文档")
    print("=" * 50)


if __name__ == "__main__":
    main()
