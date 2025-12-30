import os
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter

def build_vector_db(docs, config):
    embeddings = OpenAIEmbeddings(model=config['model']['embedding'])
    db_path = config['path']['vector_db']

    # 텍스트 분할
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=config['process']['chunk_size'],
        chunk_overlap=config['process']['chunk_overlap']
    )
    splits = text_splitter.split_documents(docs)

    # DB 구축 및 로드 (v1.0의 persistent 방식)
    vectorstore = Chroma.from_documents(
        documents=splits,
        embedding=embeddings,
        persist_directory=db_path
    )
    return vectorstore