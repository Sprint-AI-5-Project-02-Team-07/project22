import os
import json
import pickle
from pathlib import Path
from typing import List, Dict

import numpy as np
import faiss
from tqdm import tqdm
from openai import OpenAI


# =========================
# 설정
# =========================
EMBEDDING_MODEL = "text-embedding-3-small"

CLEAN_DIR = Path("C:/Users/main/Downloads/project2_data/rag_chunks_clean")
OUT_DIR = Path("C:/Users/main/Downloads/project2_data/vector_store_faiss")
OUT_DIR.mkdir(parents=True, exist_ok=True)

INDEX_PATH = OUT_DIR / "faiss.index"
META_PATH = OUT_DIR / "metadata.pkl"

BATCH_SIZE = 100   # rate limit 안정값


# =========================
# OpenAI Client
# =========================
# OPENAI_API_KEY는 환경변수에서 자동 로드
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
assert OPENAI_API_KEY, "OPENAI_API_KEY 환경변수가 필요합니다."
client = OpenAI(api_key=OPENAI_API_KEY)


import tiktoken

encoding = tiktoken.encoding_for_model("text-embedding-3-small")

MAX_TOKENS = 6000

def split_for_embedding(text: str, max_tokens: int = MAX_TOKENS):
    tokens = encoding.encode(text)
    return [
        encoding.decode(tokens[i:i + max_tokens])
        for i in range(0, len(tokens), max_tokens)
    ]



# =========================
# jsonl 전체 로드
# =========================
def load_all_chunks(clean_dir: Path) -> List[Dict]:
    chunks = []
    files = sorted(clean_dir.glob("*_clean.jsonl"))

    print(f"📂 Found {len(files)} clean jsonl files")

    for path in files:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                obj = json.loads(line)
                text = obj.get("text", "").strip()
                if text:
                    chunks.append(obj)

    return chunks


# =========================
# 임베딩 생성
# =========================
def embed_chunks(chunks):
    texts = []
    metadatas = []

    for chunk in chunks:
        text = chunk.get("text", "")
        if not text:
            continue

        sub_texts = split_for_embedding(text)

        for sub_idx, sub_text in enumerate(sub_texts):
            texts.append(sub_text)

            meta = {
                "chunk_id": chunk.get("chunk_id"),
                "sub_index": sub_idx,
                "source_pdf": chunk.get("source_pdf"),
                "section_title": chunk.get("section_title"),
                "clause_key": chunk.get("clause_key"),
                "page_start": chunk.get("page_start"),
                "page_end": chunk.get("page_end"),
            }
            metadatas.append(meta)

    embeddings = []

    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i:i + BATCH_SIZE]
        res = client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=batch
        )
        for r in res.data:
            embeddings.append(r.embedding)

    return embeddings, metadatas




# =========================
# FAISS 인덱스 생성
# =========================
def build_faiss_index(vectors):
    # 🔑 리스트 → numpy array 변환
    vectors = np.array(vectors, dtype="float32")

    dim = vectors.shape[1]
    index = faiss.IndexFlatL2(dim)
    index.add(vectors)
    return index



# =========================
# 메인 파이프라인
# =========================
def main():
    print("📥 Loading cleaned chunks...")
    chunks = load_all_chunks(CLEAN_DIR)

    print(f"총 chunk 수: {len(chunks)}")

    texts = [c["text"] for c in chunks]

    print("🧠 Creating embeddings...")
    embeddings, metadata = embed_chunks(chunks)


    print("📦 Building FAISS index...")
    index = build_faiss_index(embeddings)

    print("💾 Saving FAISS index...")
    faiss.write_index(index, str(INDEX_PATH))

    print("💾 Saving metadata...")
    metadata = [
        {
            "chunk_id": c.get("chunk_id"),
            "source_pdf": c.get("source_pdf"),
            "section_title": c.get("section_title"),
            "clause_key": c.get("clause_key"),
            "page_start": c.get("page_start"),
            "page_end": c.get("page_end"),
        }
        for c in chunks
    ]

    with META_PATH.open("wb") as f:
        pickle.dump(metadata, f)

    print("\n✅ FAISS 인덱스 구축 완료")
    print(f" - vectors: {index.ntotal}")
    print(f" - index  : {INDEX_PATH}")
    print(f" - meta   : {META_PATH}")


if __name__ == "__main__":
    main()
