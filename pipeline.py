import os
import yaml
import argparse
from dotenv import load_dotenv
from pathlib import Path

# Pipelines
from src.pipeline.hwp_converter import run_hwp_conversion
from src.pipeline.pdf_parser import run_pdf_parsing
from src.pipeline.chunker import run_chunking
from src.loader import load_rfp_documents
from src.indexer import build_vector_db

def load_config():
    with open("config/config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def main():
    parser = argparse.ArgumentParser(description="Integrated RAG Pipeline")
    parser.add_argument("--step", type=str, default="all", choices=["convert", "parse", "clean", "index", "all"], help="Step to run")
    args = parser.parse_args()
    
    load_dotenv()
    config = load_config()
    
    # 0. HWP Conversion
    if args.step in ["convert", "all"]:
        print("\n[Step 0] Converting HWP to PDF...")
        raw_data_path = config['path']['raw_data']
        run_hwp_conversion(raw_data_path)

    # 1. Parsing (PDF -> JSON)
    if args.step in ["parse", "all"]:
        print("\n[Step 1] PDF Parsing with Upstage...")
        raw_data_path = config['path']['raw_data'] # Same folder for PDFs
        raw_json_path = config['path']['raw_json']
        api_key = os.getenv("UPSTAGE_API_KEY")
        
        if not api_key:
            print("Error: UPSTAGE_API_KEY not found in env.")
            return

        run_pdf_parsing(raw_data_path, raw_json_path, api_key)

    # 2. Cleaning & Chunking (JSON -> JSONL)
    if args.step in ["clean", "all"]:
        print("\n[Step 2] Cleaning & Chunking...")
        raw_json_path = config['path']['raw_json']
        clean_json_path = config['path']['clean_json']
        
        run_chunking(raw_json_path, clean_json_path)

    # 3. Indexing (JSONL -> Chroma)
    if args.step in ["index", "all"]:
        print("\n[Step 3] Building Vector DB (Chroma)...")
        # Ensure folders exist
        Path(config['path']['clean_json']).mkdir(parents=True, exist_ok=True)
        
        # Load docs using refactored loader
        docs = load_rfp_documents(config)
        
        if docs:
            build_vector_db(docs, config)
            print("✅ Vector DB built successfully.")
        else:
            print("⚠️ No documents loaded. Skipping indexing.")

if __name__ == "__main__":
    main()
