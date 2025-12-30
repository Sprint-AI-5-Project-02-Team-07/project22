from typing import Optional
from pydantic import BaseModel, Field
from langchain_core.runnables import RunnableLambda
from langchain_openai import ChatOpenAI
import datetime

# 1. 스키마 확장 (마감일 추가)
class SearchQuery(BaseModel):
    query: str = Field(..., description="검색할 핵심 키워드")
    organization: Optional[str] = Field(None, description="발주 기관명")
    min_budget: Optional[float] = Field(None, description="최소 예산 (원)")
    max_budget: Optional[float] = Field(None, description="최대 예산 (원)")
    # [추가] 마감일 기준 검색 (예: 2024-12-01 이후 마감)
    deadline_after: Optional[str] = Field(None, description="이 날짜 이후에 마감되는 사업 (YYYY-MM-DD)")
    deadline_before: Optional[str] = Field(None, description="이 날짜 이전에 마감되는 사업 (YYYY-MM-DD)")

def get_advanced_retriever(vectorstore, config):
    llm = ChatOpenAI(
        model=config['model']['llm'], 
        temperature=0
    ).with_structured_output(SearchQuery)

    # 2. 필터 변환 로직 (날짜 처리 추가)
    def create_chroma_filter(search_query: SearchQuery):
        filters = []
        
        # 기관명
        if search_query.organization:
            filters.append({"organization": {"$eq": search_query.organization}})
        
        # 예산
        if search_query.min_budget is not None:
            filters.append({"budget": {"$gte": search_query.min_budget}})
        if search_query.max_budget is not None:
            filters.append({"budget": {"$lte": search_query.max_budget}})
            
        # [추가] 마감일 (문자열 비교: ISO 포맷 날짜는 문자열 비교 가능)
        if search_query.deadline_after:
            filters.append({"deadline": {"$gte": search_query.deadline_after}})
        if search_query.deadline_before:
            filters.append({"deadline": {"$lte": search_query.deadline_before}})
            
        if not filters: return None
        elif len(filters) == 1: return filters[0]
        else: return {"$and": filters}

    def retriever_func(inputs):
        chroma_filter = create_chroma_filter(inputs)
        
        # 디버깅: 오늘 날짜와 함께 검색 조건 출력
        today = datetime.date.today().isoformat()
        print(f"\n[Query Analysis] (Today: {today})")
        print(f" - 검색어: '{inputs.query}'")
        print(f" - 필터: {chroma_filter}")
        
        return vectorstore.similarity_search(
            inputs.query, k=3, filter=chroma_filter
        )

    return llm | RunnableLambda(retriever_func)