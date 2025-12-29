import json
import re
from pathlib import Path
from typing import Dict


# =========================
# 설정
# =========================
IN_DIR = Path("C:/Users/main/Downloads/project2_data/rag_chunks")          # chunks.jsonl 폴더
OUT_DIR = Path("C:/Users/main/Downloads/project2_data/rag_chunks_clean")   # clean jsonl 폴더
OUT_DIR.mkdir(parents=True, exist_ok=True)

MIN_TEXT_LEN = 200     # 이보다 짧으면 제거
DOT_RATIO_TH = 0.35    # 점선 비율 임계치


# =========================
# 유틸
# =========================
def remove_decorative_lines(text: str) -> str:
    """점선/장식 위주 라인 제거"""
    lines = []
    for line in text.splitlines():
        l = line.strip()

        # 점선/장식만 있는 줄 제거
        if not l:
            continue
        if re.fullmatch(r"[·\.\-\s]+", l):
            continue

        lines.append(line)

    return "\n".join(lines).strip()


def is_toc_chunk(text: str) -> bool:
    """목차(TOC) 휴리스틱 판별"""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines:
        return True

    # 명시적 목차 키워드
    if any("목 차" in l or "목차" in l for l in lines[:3]):
        return True

    dot_lines = sum(1 for l in lines if "·" in l)
    digit_lines = sum(1 for l in lines if any(c.isdigit() for c in l))
    long_text_lines = sum(1 for l in lines if len(l) >= 25 and "·" not in l)

    # 점선/숫자 위주 + 실제 문장 거의 없음
    if dot_lines / len(lines) > DOT_RATIO_TH and long_text_lines < 3:
        return True
    if digit_lines / len(lines) > 0.7 and long_text_lines < 3:
        return True

    return False


def is_meaningful(text: str) -> bool:
    """의미 있는 텍스트인지 판단"""
    if len(text) < MIN_TEXT_LEN:
        return False

    # 조사/서술어 기반 간단 체크
    keywords = ["한다", "함", "한다.", "기준", "대상", "방법", "제출", "평가", "수행"]
    if not any(k in text for k in keywords):
        return False

    return True


# =========================
# 정제 파이프라인
# =========================
def clean_chunk(chunk: Dict) -> Dict | None:
    raw_text = chunk.get("text", "").strip()
    if not raw_text:
        return None

    # 1) 장식 제거
    text = remove_decorative_lines(raw_text)

    # 2) TOC 제거
    if is_toc_chunk(text):
        return None

    # 3) 의미 없는 chunk 제거
    if not is_meaningful(text):
        return None

    # 통과
    chunk["text"] = text
    return chunk


def process_file(in_path: Path, out_path: Path):
    kept = 0
    removed = 0

    with in_path.open("r", encoding="utf-8") as fin, \
        out_path.open("w", encoding="utf-8") as fout:

        for line in fin:
            chunk = json.loads(line)
            cleaned = clean_chunk(chunk)

            if cleaned is None:
                removed += 1
                continue

            fout.write(json.dumps(cleaned, ensure_ascii=False) + "\n")
            kept += 1

    print(f"✅ {in_path.name}: kept={kept}, removed={removed}")


def main():
    files = sorted(IN_DIR.glob("*.jsonl"))
    print(f"📂 Found {len(files)} chunk files")

    for f in files:
        out = OUT_DIR / f.name.replace(".jsonl", "_clean.jsonl")
        process_file(f, out)


if __name__ == "__main__":
    main()
