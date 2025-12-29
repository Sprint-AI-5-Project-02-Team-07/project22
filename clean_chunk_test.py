import json
import random
from pathlib import Path


CLEAN_DIR = Path("C:/Users/main/Downloads/project2_data/rag_chunks_clean")
NUM_FILES = 3      # 랜덤으로 뽑을 파일 수
TEXT_PREVIEW = 500 # 출력할 텍스트 길이


def sample_random_chunks(clean_dir: Path, num_files: int = 3):
    files = list(clean_dir.glob("*_clean.jsonl"))

    if not files:
        print("❌ clean jsonl 파일이 없습니다.")
        return

    selected_files = random.sample(files, min(num_files, len(files)))

    for file_path in selected_files:
        print("\n" + "=" * 80)
        print(f"📄 File: {file_path.name}")

        with file_path.open("r", encoding="utf-8") as f:
            lines = f.readlines()

        if not lines:
            print("⚠️ 파일이 비어 있습니다.")
            continue

        line = random.choice(lines)
        obj = json.loads(line)

        print("-" * 80)
        print(f"Section : {obj.get('section_title')}")
        print(f"Clause  : {obj.get('clause_key')}")
        print(f"Pages   : {obj.get('page_start')} ~ {obj.get('page_end')}")
        print("-" * 80)
        print(obj.get("text", ""))
        print("\n")


if __name__ == "__main__":
    sample_random_chunks(CLEAN_DIR, NUM_FILES)
