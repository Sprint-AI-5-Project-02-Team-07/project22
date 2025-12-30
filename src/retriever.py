from typing import Optional, List
from pydantic import BaseModel, Field
from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from langchain_openai import ChatOpenAI

# 1. Pydantic을 사용해 LLM이 추출해야 할 데이터 구조 정의 (Schema)
class SearchQuery(BaseModel):
    """검색 쿼리와 필터 조건을 추출하기 위한 스키마"""
    query: str = Field(
        ..., 
        description="문서 내용을 검색할 핵심 키워드 또는 문장"
    )
    organization: Optional[str] = Field(
        None, 
        description="발주 기관명 (예: 한영대학, 한국지능정보사회진흥원 등). 없을 경우 None"
    )
    min_budget: Optional[float] = Field(
        None, 
        description="최소 예산 금액 (질문이 '1억 이상'이면 100000000). 없을 경우 None"
    )
    max_budget: Optional[float] = Field(
        None, 
        description="최대 예산 금액 (질문이 '5천만원 이하'이면 50000000). 없을 경우 None"
    )

def get_advanced_retriever(vectorstore, config):
    """
    LCEL 기반의 Modern Query Analysis Retriever
    """
    
    # 2. LLM 설정 (Structured Output 사용)
    # 최신 LangChain은 .with_structured_output()을 권장합니다.
    llm = ChatOpenAI(
        model=config['model']['llm'], 
        temperature=0
    ).with_structured_output(SearchQuery)

    # 3. 필터 변환 함수 (ChromaDB 문법으로 변환)
    def create_chroma_filter(search_query: SearchQuery):
        """Pydantic 객체를 ChromaDB용 where 절로 변환"""
        filters = []
        
        # 기관명 필터
        if search_query.organization:
            filters.append({"organization": {"$eq": search_query.organization}})
            
        # 예산 필터 (Range)
        if search_query.min_budget is not None:
            filters.append({"budget": {"$gte": search_query.min_budget}})
        if search_query.max_budget is not None:
            filters.append({"budget": {"$lte": search_query.max_budget}})
            
        # 필터 조합
        if not filters:
            return None
        elif len(filters) == 1:
            return filters[0]
        else:
            return {"$and": filters}

    # 4. 실제 검색 실행 함수
    def retriever_func(inputs):
        """
        inputs는 LLM이 반환한 SearchQuery 객체입니다.
        이를 이용해 vectorstore에서 검색을 수행합니다.
        """
        # A. 필터 생성
        chroma_filter = create_chroma_filter(inputs)
        
        # B. 검색어(Query) 확인
        search_term = inputs.query
        
        print(f"\n[Query Analysis] 검색어: '{search_term}' / 필터: {chroma_filter}")

        # C. 벡터 검색 실행
        # filter가 None이면 일반 검색, 있으면 필터링 검색
        docs = vectorstore.similarity_search(
            search_term,
            k=3, # config에서 가져와도 됨
            filter=chroma_filter
        )
        return docs

    # 5. LCEL 체인 구성: (질문 -> LLM 분석 -> 검색 실행)
    # input(str) -> llm(SearchQuery) -> retriever_func(List[Document])
    chain = (
        llm 
        | RunnableLambda(retriever_func)
    )
    
    return chain