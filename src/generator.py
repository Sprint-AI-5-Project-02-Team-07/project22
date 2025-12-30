from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

def format_docs(docs):
    """검색된 문서들을 포맷팅하여 컨텍스트 문자열로 변환"""
    return "\n\n".join(
        f"--- [출처: {doc.metadata['source']}] ---\n{doc.page_content}" 
        for doc in docs
    )

def create_bidmate_chain(retriever, config):
    # 1. LLM 설정
    llm = ChatOpenAI(
        model=config['model']['llm'],
        temperature=config['model']['temperature']
    )

    # 2. 프롬프트 템플릿 (System Message 활용)
    template = """당신은 제안요청서(RFP) 분석 전문가 '입찰메이트 AI'입니다. 
아래 [Context]에 있는 내용만을 근거로 답변하세요.
답변 시 정보의 출처(파일명)를 괄호 안에 명시하세요.

[Context]
{context}

질문: {question}
"""
    prompt = ChatPromptTemplate.from_template(template)

    # 3. LCEL 체인 구성 (RAG Pipeline)
    # Retriever -> Context Formatting -> Prompt -> LLM -> String Output
    rag_chain = (
        {
            "context": retriever | format_docs, 
            "question": RunnablePassthrough()
        }
        | prompt
        | llm
        | StrOutputParser()
    )
    
    return rag_chain