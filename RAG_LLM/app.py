import streamlit as st
import time
import os
from dotenv import load_dotenv

# Load Env
load_dotenv()

# Internal Modules
from src.loader import load_data
from src.retrieval import initialize_hybrid_retriever, retrieve_documents
from src.generation import generate_answer
from src.query_extractor import extract_filters
from src.session_manager import get_merged_filters, update_context
from src.decomposition import decompose_query

# ---------------------------------------------------------
# Page Config
# ---------------------------------------------------------
st.set_page_config(
    page_title="RAG Chatbot",
    page_icon="🤖",
    layout="wide"
)

st.title("🤖 AI 사업 공고 분석 챗봇")

# ---------------------------------------------------------
# Sidebar: Settings & Manual Filters
# ---------------------------------------------------------
with st.sidebar:
    st.header("⚙️ 설정 (Settings)")
    
    # Force Reload Button
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 캐시 초기화"):
            st.cache_resource.clear()
            st.rerun()
            
    with col2:
        if st.button("🗑️ 대화 초기화"):
            st.session_state.messages = []
            # Remove session file
            import src.session_manager as sm
            if os.path.exists(sm.SESSION_FILE):
                os.remove(sm.SESSION_FILE)
            st.rerun()
        
    st.divider()
    
    st.subheader("🔍 수동 필터 (Optional)")
    manual_agency = st.text_input("기관명 (Agency)", placeholder="예: 평택시")
    manual_amount = st.number_input("최소 금액 (Amount)", min_value=0, step=1000000, value=0)

# ---------------------------------------------------------
# Initialization (Cached)
# ---------------------------------------------------------
@st.cache_resource
def get_cached_documents(version):
    # version param is used purely to force cache invalidation when changed in config
    st.write(f"Cache Version: {version} - Reloading Data...")
    return load_data(use_cache=True)

@st.cache_resource
def get_cached_retriever(_docs):
    # This function builds the retriever and returns it.
    # Streamlit will cache the resulting object.
    initialize_hybrid_retriever(_docs)
    from src.retrieval import _hybrid_retriever
    return _hybrid_retriever

def initialize_system():
    with st.spinner("시스템 초기화 중... (문서 로딩 & 인덱싱)"):
        # 1. Load Data
        docs = get_cached_documents(config.CACHE_VERSION)
        
        # 2. Init Retriever (Cached)
        # We need to ensure the global variable in src.retrieval is set
        # because retrieve_documents() uses it.
        retriever = get_cached_retriever(docs)
        
        # FORCE set the global variable in src.retrieval
        import src.retrieval
        src.retrieval._hybrid_retriever = retriever
        
        return True

# ---------------------------------------------------------
# Chat History Management
# ---------------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display Chat History
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        # If there are source documents (only for assistant), show them
        if message.get("sources"):
             with st.expander("📚 참고 문서 (Sources) 확인하기"):
                for idx, doc in enumerate(message["sources"]):
                    st.markdown(f"**{idx+1}. [{doc['metadata'].get('agency', 'Unknown')}] {doc['metadata'].get('title', 'Untitled')}**")
                    st.text(doc['page_content'][:300] + "...")
                    st.divider()

# ---------------------------------------------------------
# Chat Logic
# ---------------------------------------------------------
if query := st.chat_input("질문을 입력하세요... (예: 평택시 버스 예산 얼마야?)"):
    # 1. User Message
    with st.chat_message("user"):
        st.markdown(query)
    st.session_state.messages.append({"role": "user", "content": query})

    # 2. Assistant Logic
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        
        with st.spinner("답변 생성 중..."):

            # A. Auto-Filter Extraction
            # We extract filters for the *original* query to capture context (like agency if mentioned globally)
            # But decomposition handles specific entities better.
            auto_filters = extract_filters(query)
            
            # B. Merge with Session
            merged_filters = get_merged_filters(auto_filters)
            if manual_agency:
                merged_filters['agency'] = manual_agency
            if manual_amount > 0:
                merged_filters['min_amount'] = manual_amount
                
            if merged_filters:
                st.caption(f"💡 **기본 필터**: {merged_filters}")
                update_context(merged_filters, query)

            # C. Query Decomposition & Retrieval
            sub_queries = decompose_query(query)
            
            all_retrieved_docs = []
            seen_contents = set()
            
            # Progress bar if multiple steps
            if len(sub_queries) > 1:
                st.info(f"🧩 복잡한 질문이네요! 다음 {len(sub_queries)}가지로 나누어 검색합니다: {sub_queries}")
                my_bar = st.progress(0)
            
            for i, sub_q in enumerate(sub_queries):
                # For sub-queries, we might NOT want to enforce the global sticky agency filter 
                # if the sub-query explicitly mentions a different agency.
                # However, our retrieval logic's deep fallback uses the filter.
                # For simplicity, let's use the merged filter BUT be aware.
                # Actually, if sub-query is "Ulsan budget", and sticky filter is "Pyeongtaek", 
                # we have a conflict.
                # Ideally, decomposition should override filters. 
                # Let's pass 'None' for filters if sub-queries are used, 
                # OR let the retrieval logic handle it.
                # Current Decision: Pass merged_filters. If conflict, retrieval might fail, but fallback searches vector.
                
                # BETTER: Modify extractor to run on sub-query? 
                # Let's just run retrieval with merged_filters for now.
                
                docs = retrieve_documents(sub_q, filter_criteria=merged_filters if len(sub_queries) == 1 else None)
                
                for doc in docs:
                    if doc.page_content not in seen_contents:
                        seen_contents.add(doc.page_content)
                        all_retrieved_docs.append(doc)
                
                if len(sub_queries) > 1:
                    my_bar.progress((i + 1) / len(sub_queries))
            
            if len(sub_queries) > 1:
                my_bar.empty()
            
            # --- DEBUG: Show All Retrieved Candidates ---
            with st.expander("🕵️ 디버깅: 검색된 모든 문서 (Reranking 전후)", expanded=False):
                st.write(f"Total Candidates: {len(all_retrieved_docs)}")
                for i, doc in enumerate(all_retrieved_docs):
                    st.text(f"[{i+1}] {doc.page_content[:100]}...")
            # --------------------------------------------
            
            # D. Generate Answer (Synthesis)
            # We pass the ORIGINAL query, but with ALL retrieved documents.
            if not all_retrieved_docs:
                st.warning("⚠️ 검색된 문서가 없습니다.")
                answer = "관련 문서를 찾지 못했습니다."
            else:
                answer = generate_answer(query, all_retrieved_docs)
            
            message_placeholder.markdown(answer)
            
            # Prepare source metadata for history
            sources_clean = []
            for doc in all_retrieved_docs:
                sources_clean.append({
                    "page_content": doc.page_content,
                    "metadata": doc.metadata
                })
            
            # E. Show Sources in Expander (Current Turn)
            with st.expander("📚 참고 문서 (Sources) - Click to expand"):
                for idx, doc in enumerate(all_retrieved_docs):
                    st.markdown(f"**{idx+1}. [{doc.metadata.get('agency', 'Unknown')}] {doc.metadata.get('title', 'Unknown')}**")
                    st.caption(f"Score/Rank: {idx+1}")
                    st.text(doc.page_content[:400] + "...")
                    st.divider()

    # 3. Save Assistant Message
    st.session_state.messages.append({
        "role": "assistant", 
        "content": answer,
        "sources": sources_clean
    })
