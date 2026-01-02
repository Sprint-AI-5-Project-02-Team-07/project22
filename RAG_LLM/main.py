import argparse
from src.loader import load_data
from src.retrieval import build_vector_store, retrieve_documents, initialize_hybrid_retriever
from src.generation import generate_answer

def main():
    parser = argparse.ArgumentParser(description="BidMate RAG System")
    parser.add_argument("--query", type=str, help="Question to ask the RAG system")
    parser.add_argument("--build", action="store_true", help="Build the vector store")
    parser.add_argument("--agency", type=str, help="Filter by agency name (exact match)")
    parser.add_argument("--min_amount", type=int, help="Filter by minimum project amount")
    parser.add_argument("--evaluate", action="store_true", help="Run RAG evaluation using Ragas")
    args = parser.parse_args()
    
    # 0. Evaluation Mode
    if args.evaluate:
        from src.evaluation import run_evaluation
        run_evaluation()
        return

    # 1. Load Data (Needed for BM25 and Build)
    # Using cache makes this fast for queries
    print("Loading documents...")
    documents = load_data(use_cache=True) 
    print(f"Loaded {len(documents)} documents.")

    if args.build:
        print("Building vector store...")
        build_vector_store(documents)
        print("Vector store built successfully.")
        return

    # 2. Initialize Retriever (Hybrid)
    # If filters are present, the retrieval logic handles fallback to Vector-only
    print("Initializing Hybrid Retriever...")
    initialize_hybrid_retriever(documents)

    if args.query:
        print(f"Query: {args.query}")
        
        from src.session_manager import update_context, get_merged_filters
    
        # 4. Filter Extraction (Explicit -> Auto -> Context)
        filter_criteria = {}
        
        # Explicit CLI args take precedence
        if args.agency:
            filter_criteria['agency'] = args.agency
        if args.min_amount:
            filter_criteria['min_amount'] = args.min_amount
            
        # If no explicit args, try Auto-Extraction
        if not filter_criteria:
            print("Extracting filters from query (Auto-Filtering)...")
            from src.query_extractor import extract_filters
            auto_filters = extract_filters(args.query)
            if auto_filters:
                print(f"Auto-detected filters: {auto_filters}")
                filter_criteria.update(auto_filters)
                
        # Merge with Session Context (Sticky Context)
        # e.g. If I asked about "Pyeongtaek" before, and now ask "How much?", remember Pyeongtaek.
        filter_criteria = get_merged_filters(filter_criteria)
        
        # Update Session for next turn
        update_context(filter_criteria, args.query)

        # 5. Retrieval
        print("Retrieving documents...")
        retrieved_docs = retrieve_documents(args.query, filter_criteria=filter_criteria)
        print(f"Retrieved {len(retrieved_docs)} documents.")
        
        print("Generating answer...")
        answer = generate_answer(args.query, retrieved_docs)
        print("\n=== Answer ===\n")
        print(answer)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
