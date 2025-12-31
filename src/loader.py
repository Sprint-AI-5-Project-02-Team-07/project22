import os
import json
import pandas as pd
from langchain_core.documents import Document

def load_rfp_documents(config: dict):
    csv_path = config['path']['csv_file']
    # Change: Load from Clean JSON folder
    json_folder = config['path']['clean_json'] 
    
    print(f"[Loader] 메타데이터 로드: {csv_path}")
    df = pd.read_csv(csv_path)
    
    all_docs = []
    success_count = 0
    fallback_count = 0

    print(f"[Loader] JSON 데이터 로딩 시작... (대상 폴더: {json_folder})")

    for _, row in df.iterrows():
        original_name = str(row['파일명'])
        base_name = os.path.splitext(original_name)[0]
        # Change: File naming convention uses _clean.jsonl
        json_file_name = f"{base_name}_clean.jsonl"
        json_path = os.path.join(json_folder, json_file_name)
        
        # --- [안전한 타입 변환 로직] ---
        try:
            budget_val = float(row.get('사업 금액', 0))
        except:
            budget_val = 0.0

        # 공고 차수: 1.0 -> 1 로 변환
        try:
            round_val = int(float(row.get('공고 차수', 0)))
        except:
            round_val = 0
            
        base_metadata = {
            "source": original_name,
            "announcement_id": str(row.get('공고 번호', "Unknown")),
            "round": round_val,  # [추가] 공고 차수
            "project_name": row.get('사업명', "Unknown"),
            "organization": row.get('발주 기관', "Unknown"),
            "budget": budget_val,
            "pub_date": str(row.get('공개 일자', "")),      # [추가] 공개 일자
            "start_date": str(row.get('입찰 참여 시작일', "")), # [추가] 시작일
            "deadline": str(row.get('입찰 참여 마감일', "")),
            "summary": str(row.get('사업 요약', "")),
        }
        # -----------------------------

        # 1. JSONL 로드
        loaded = False
        if os.path.exists(json_path):
            try:
                # Change: Read line by line for JSONL
                with open(json_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        page_item = json.loads(line)
                        content = page_item.get('content', '')
                        page_num = page_item.get('page', 0)
                        
                        if not content.strip(): continue
                            
                        page_metadata = base_metadata.copy()
                        page_metadata['page'] = page_num
                        
                        all_docs.append(Document(page_content=content, metadata=page_metadata))
                
                success_count += 1
                loaded = True
            except Exception as e:
                print(f"[Warning] 파싱 실패 ({json_file_name}): {e}")

        # 2. Fallback
        if not loaded:
            content = str(row.get('텍스트', ''))
            if content.strip():
                all_docs.append(Document(page_content=content, metadata=base_metadata))
                fallback_count += 1

    print(f"[Loader] 완료: 성공 {success_count}건, CSV 대체 {fallback_count}건")
    return all_docs