import os
from dotenv import load_dotenv

load_dotenv()

# Base Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "files")
METADATA_PATH = os.path.join(BASE_DIR, "data_list.csv")
VECTOR_DB_PATH = os.path.join(BASE_DIR, "chroma_db")
LOG_DIR = os.path.join(BASE_DIR, "logs")

# Cache Settings
CACHE_VERSION = "v2.0" # Updated for Robust CSV Encoding & Fuzzy Match (Final Fix)

# Vector DB Settings
COLLECTION_NAME = "rfp_collection"

# Model Settings
EMBEDDING_MODEL_NAME = "text-embedding-3-small"
LLM_MODEL_NAME = "gpt-5-mini"
UPSTAGE_API_KEY = os.getenv("UPSTAGE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Retrieval Settings
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
TOP_K = 15

