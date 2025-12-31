import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Dict, Optional, Tuple

# =========================
# 설정(필요시 조정)
# =========================
MAX_CHARS_PER_CHUNK = 4500     # 임베딩/LLM 컨텍스트에 맞게 조절
MIN_CHARS_PER_CHUNK = 400      # 너무 짧은 조각 합치기 기준
SOFT_SPLIT_MAX_CHARS = 2200    # 아주 긴 chunk를 추가로 부드럽게 쪼갤 때 기준
DOT_RATIO_TH = 0.35            # 점선 비율 임계치 (Cleaning)
MIN_TEXT_LEN_CLEAN = 50        # Cleaning 단계 최소 길이

# =========================
# Cleaning Logic (from old text_cleaner.py)
# =========================
def remove_decorative_lines(text: str) -> str:
    """점선/장식 위주 라인 제거"""
    lines = []
    for line in text.splitlines():
        l = line.strip()
        if not l: continue
        if re.fullmatch(r"[·\.\-\s]+", l): continue
        lines.append(line)
    return "\n".join(lines).strip()

def is_toc_chunk(text: str) -> bool:
    """목차(TOC) 휴리스틱 판별"""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines: return True
    if any("목 차" in l or "목차" in l for l in lines[:3]): return True

    dot_lines = sum(1 for l in lines if "·" in l)
    digit_lines = sum(1 for l in lines if any(c.isdigit() for c in l))
    long_text_lines = sum(1 for l in lines if len(l) >= 25 and "·" not in l)

    if dot_lines / len(lines) > DOT_RATIO_TH and long_text_lines < 3: return True
    if digit_lines / len(lines) > 0.7 and long_text_lines < 3: return True
    return False

def clean_text_block(text: str) -> str | None:
    """
    텍스트 블록 정제. 
    의미가 없으면 None 반환.
    """
    # 1) 장식 제거
    cleaned = remove_decorative_lines(text)
    
    # 2) TOC 체크
    if is_toc_chunk(cleaned):
        return None
        
    # 3) 길이 체크
    if len(cleaned) < MIN_TEXT_LEN_CLEAN:
        return None
        
    return cleaned


# =========================
# Splitting Logic (from old json2jsonl.py)
# =========================

# 1) 섹션/헤더 후보
SECTION_TITLE_PATTERNS = [
    r"사업\s*개요", r"사업\s*목적", r"추진\s*배경",
    r"사업\s*범위", r"과업\s*범위", r"과업\s*내용", r"업무\s*범위",
    r"제안\s*요청\s*사항", r"제안\s*서\s*작성", r"제안서\s*작성",
    r"평가\s*기준", r"평가\s*방법", r"선정\s*기준", r"심사\s*기준",
    r"제출\s*서류", r"입찰\s*참가", r"입찰\s*방법", r"계약\s*조건",
    r"일정", r"추진\s*일정", r"수행\s*일정",
    r"유의\s*사항", r"기타\s*사항", r"참고\s*사항",
    r"질의\s*응답", r"문의처",
]
SECTION_TITLE_RE = re.compile(
    r"^(?:#+\s*)?(?P<title>(" + "|".join(SECTION_TITLE_PATTERNS) + r"))\s*$"
)
CLAUSE_RE = re.compile(r"^(?P<key>제\s*\d+\s*조)\b.*$")
NUMBERED_RE = re.compile(
    r"^(?P<key>(?:\(?\d+\)?[.)]|(?:\d+\s*-\s*\d+)|[①②③④⑤⑥⑦⑧⑨⑩]))\s+.*$"
)
APPENDIX_RE = re.compile(r"^(?P<key>(?:부록|별첨|첨부|붙임))\b.*$")

@dataclass
class Page:
    page: int
    content: str
    metadata: Dict

@dataclass
class Chunk:
    source_pdf: str
    chunk_id: str
    section_title: Optional[str]
    clause_key: Optional[str]
    page_start: int
    page_end: int
    text: str # content

def load_pages(parsed_json_path: Path) -> List[Page]:
    with parsed_json_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    
    pages: List[Page] = []
    for item in data:
        # page: global page (top-level) 를 우선 사용
        p = int(item.get("page") or item.get("metadata", {}).get("global_page") or 0)
        content = item.get("content") or ""
        md = item.get("metadata") or {}
        pages.append(Page(page=p, content=content, metadata=md))
    pages.sort(key=lambda x: x.page)
    return pages

def normalize_line(line: str) -> str:
    return line.rstrip()

def is_markdown_table_line(line: str) -> bool:
    return "|" in line

def detect_boundary(line: str) -> Tuple[Optional[str], Optional[str]]:
    l = line.strip()
    if not l: return None, None

    m = SECTION_TITLE_RE.match(l)
    if m: return m.group("title"), None

    m = CLAUSE_RE.match(l)
    if m: return None, m.group("key").replace(" ", "")

    m = APPENDIX_RE.match(l)
    if m: return None, m.group("key")

    m = NUMBERED_RE.match(l)
    if m: return None, m.group("key").replace(" ", "")

    return None, None

def soft_split_text(text: str, max_chars: int = SOFT_SPLIT_MAX_CHARS) -> List[str]:
    if len(text) <= max_chars:
        return [text]

    blocks = text.split("\n\n")
    out, buf = [], ""

    def flush():
        nonlocal buf
        if buf.strip():
            out.append(buf.strip())
        buf = ""

    for b in blocks:
        b = b.strip()
        if not b: continue

        # 표 블록 유지
        if any("|" in line for line in b.splitlines()):
            if len(buf) + len(b) > max_chars: flush()
            buf += b + "\n\n"
            continue

        # look-behind 제거한 문장 분리
        parts = re.split(r"([.?!]|다\.)\s+", b)
        sentences = []
        for i in range(0, len(parts) - 1, 2):
            sentences.append(parts[i] + parts[i + 1])

        for s in sentences:
            if len(buf) + len(s) <= max_chars:
                buf += s + " "
            else:
                flush()
                buf += s + " "
    flush()
    return out

def split_pages_into_chunks(pages: List[Page], source_pdf: str) -> List[Chunk]:
    chunks: List[Chunk] = []

    current_section: Optional[str] = None
    current_clause: Optional[str] = None

    buf_lines: List[str] = []
    buf_page_start: Optional[int] = None
    buf_page_end: Optional[int] = None

    def start_buffer(page_no: int):
        nonlocal buf_page_start, buf_page_end
        if buf_page_start is None:
            buf_page_start = page_no
        buf_page_end = page_no

    def flush_buffer(force: bool = False):
        nonlocal buf_lines, buf_page_start, buf_page_end, chunks
        
        # 🟢 Apply cleaning before making chunk
        raw_text = "\n".join(buf_lines).strip()
        cleaned_text = clean_text_block(raw_text) # can be None if empty/garbage
        
        if not cleaned_text:
            # Reset buffer only
            buf_lines = []
            buf_page_start = None
            buf_page_end = None
            return

        # 너무 짧으면 이전 chunk에 합치기(가능할 때)
        if len(cleaned_text) < MIN_CHARS_PER_CHUNK and chunks and not force:
            prev = chunks[-1]
            prev.text = (prev.text.rstrip() + "\n\n" + cleaned_text).strip()
            prev.page_end = max(prev.page_end, buf_page_end or prev.page_end)
        else:
            chunk_id = f"{Path(source_pdf).stem}__p{buf_page_start:04d}-{buf_page_end:04d}__{len(chunks)+1:05d}"
            chunks.append(Chunk(
                source_pdf=source_pdf,
                chunk_id=chunk_id,
                section_title=current_section,
                clause_key=current_clause,
                page_start=buf_page_start or 0,
                page_end=buf_page_end or (buf_page_start or 0),
                text=cleaned_text # Use cleaned Text
            ))

        buf_lines = []
        buf_page_start = None
        buf_page_end = None

    for page in pages:
        page_no = page.page
        content = page.content or ""
        # 🟢 Basic Line Normalization
        lines = [normalize_line(x) for x in content.splitlines()]

        if not any(l.strip() for l in lines): continue

        for line in lines:
            sec, clause = detect_boundary(line)

            if sec or clause:
                in_table_context = (
                    len(buf_lines) >= 2
                    and is_markdown_table_line(buf_lines[-1])
                    and is_markdown_table_line(buf_lines[-2])
                )
                if not in_table_context:
                    flush_buffer()

                if sec:
                    current_section = sec
                    current_clause = None
                if clause:
                    current_clause = clause

            start_buffer(page_no)
            buf_lines.append(line)

            if sum(len(x) for x in buf_lines) > MAX_CHARS_PER_CHUNK:
                flush_buffer(force=True)

    flush_buffer(force=True)
    
    # Final Size Check & Soft Split
    final_chunks: List[Chunk] = []
    for c in chunks:
        if len(c.text) <= MAX_CHARS_PER_CHUNK:
            final_chunks.append(c)
        else:
            parts = soft_split_text(c.text, max_chars=SOFT_SPLIT_MAX_CHARS)
            for idx, part in enumerate(parts, start=1):
                cid = f"{c.chunk_id}__s{idx:02d}"
                # content key for loader
                final_chunks.append(Chunk(
                    source_pdf=c.source_pdf,
                    chunk_id=cid,
                    section_title=c.section_title,
                    clause_key=c.clause_key,
                    page_start=c.page_start,
                    page_end=c.page_end,
                    text=part
                ))
    return final_chunks

# =========================
# Main Execution
# =========================
def process_file(parsed_json_path: Path, out_path: Path):
    try:
        pages = load_pages(parsed_json_path)
    except Exception as e:
        print(f"Error loading {parsed_json_path}: {e}")
        return

    # source_pdf 추론
    source_pdf = None
    if pages:
        source_pdf = pages[0].metadata.get("source_pdf")
    source_pdf = source_pdf or (parsed_json_path.stem.replace("_parsed", "") + ".pdf")

    chunks = split_pages_into_chunks(pages, source_pdf=source_pdf)
    
    # Save as JSONL
    # Loader expects: content, page, metadata
    with out_path.open("w", encoding="utf-8") as f:
        for c in chunks:
            # Map Chunk -> Loader Compatible Dict
            out_obj = {
                "content": c.text,
                "page": c.page_start, # Representative page
                "metadata": {
                    "source_pdf": c.source_pdf,
                    "chunk_id": c.chunk_id,
                    "section_title": c.section_title,
                    "clause_key": c.clause_key,
                    "page_start": c.page_start,
                    "page_end": c.page_end
                }
            }
            f.write(json.dumps(out_obj, ensure_ascii=False) + "\n")
            
    print(f"✅ Chunked: {parsed_json_path.name} -> {len(chunks)} chunks")

def run_chunking(input_dir: str, output_dir: str):
    in_dir = Path(input_dir)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(in_dir.glob("*_parsed.json"))
    print(f"[Chunker] Found {len(files)} parsed files in {in_dir}")

    for f in files:
        out_name = f.stem.replace("_parsed", "_clean") + ".jsonl"
        out_path = out_dir / out_name
        process_file(f, out_path)
