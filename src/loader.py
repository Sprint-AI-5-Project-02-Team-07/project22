# src/loader.py
import os
import pandas as pd
from langchain_core.documents import Document
from langchain_community.document_loaders import PyPDFLoader

def load_rfp_documents(config: dict):
    csv_path = config['path']['csv_file']
    files_folder = config['path']['files_folder'] # 변환된 PDF가 담긴 폴더
    
    df = pd.read_csv(csv_path)
    all_docs = []

    print(f"[Loader] PDF 데이터 인덱싱 시작...")

    for _, row in df.iterrows():
        # CSV의 파일명(hwp)에서 확장자만 떼고 pdf 경로 생성
        base_name = os.path.splitext(str(row['파일명']))[0]
        pdf_path = os.path.join(files_folder, f"{base_name}.pdf")
        
        # 메타데이터 준비 (Self-Querying이 인식할 수 있도록 타입 변환)
        metadata = {
            "source": f"{base_name}.pdf",
            "project_name": row.get('사업명', "Unknown"),
            "organization": row.get('발주 기관', "Unknown"),
            "budget": float(row.get('사업 금액', 0)), # 반드시 float/int형으로 변환
            "deadline": row.get('입찰 참여 마감일', "Unknown")
        }

        # 1. PDF 로드
        if os.path.exists(pdf_path):
            try:
                loader = PyPDFLoader(pdf_path)
                pages = loader.load()
                for p in pages:
                    p.metadata.update(metadata)
                all_docs.extend(pages)
                continue # 성공 시 다음 문서로
            except Exception as e:
                print(f"[Error] {pdf_path} 로드 실패: {e}")

        # 2. Fallback: 파일이 없거나 로드 실패 시 CSV의 '텍스트' 컬럼 활용
        content = str(row.get('텍스트', ''))
        if content.strip():
            all_docs.append(Document(page_content=content, metadata=metadata))

    print(f"[Loader] 총 {len(all_docs)}개의 페이지/문서 로드 완료")
    return all_docs