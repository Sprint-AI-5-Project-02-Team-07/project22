import yaml
import os
from dotenv import load_dotenv
from src.indexer import load_vector_db  # [변경] 단순 로드용 함수
from src.retriever import get_advanced_retriever
from src.generator import create_bidmate_chain

load_dotenv()

def main():
    # 1. 설정 로드
    with open("config/config.yaml", "r") as f:
        config = yaml.safe_load(f)

    # 2. 벡터 DB 로드 (기존 DB 사용)
    vectorstore = load_vector_db(config)
    
    if not vectorstore:
        print("[Error] 벡터 DB가 없습니다. 먼저 'python pipeline.py --step all'을 실행하여 데이터를 구축하세요.")
        return
    
    # 4. Self-Querying Retriever 설정 (오류 수정됨)
    try:
        retriever = get_advanced_retriever(vectorstore, config)
    except Exception as e:
        print(f"[Warning] Self-Querying 설정 실패 (기본 검색기 사용): {e}")
        retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

    # 5. 체인 생성
    chain = create_bidmate_chain(retriever, config)

    # 6. 실행
    print("\n>>> 입찰메이트 AI (PDF 기반) 준비 완료 (종료: q)")
    while True:
        query = input("\n질문: ")
        if query.lower() in ['q', 'exit']:
            break
            
        try:
            response = chain.invoke(query)
            print(f"\n답변:\n{response}")
        except Exception as e:
            print(f"오류 발생: {e}")

if __name__ == "__main__":
    main()