import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Dict, Optional, Tuple


# -------------------------
# 설정(필요시 조정)
# -------------------------
MAX_CHARS_PER_CHUNK = 4500     # 임베딩/LLM 컨텍스트에 맞게 조절
MIN_CHARS_PER_CHUNK = 400      # 너무 짧은 조각 합치기 기준
SOFT_SPLIT_MAX_CHARS = 2200    # 아주 긴 chunk를 추가로 부드럽게 쪼갤 때 기준


# -------------------------
# 분할 키(정규식) 정의
# -------------------------
# 1) 섹션/헤더 후보: RFP에서 자주 나오는 큰 제목들
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

# 2) 조항/번호 기준: 제1조, 제2조 ...
CLAUSE_RE = re.compile(r"^(?P<key>제\s*\d+\s*조)\b.*$")

# 3) 번호 리스트: 1., 1), 1-1, (1), ① 등
NUMBERED_RE = re.compile(
    r"^(?P<key>(?:\(?\d+\)?[.)]|(?:\d+\s*-\s*\d+)|[①②③④⑤⑥⑦⑧⑨⑩]))\s+.*$"
)

# 4) "부록/별첨/첨부" 같은 경계
APPENDIX_RE = re.compile(r"^(?P<key>(?:부록|별첨|첨부|붙임))\b.*$")


# -------------------------
# 데이터 구조
# -------------------------
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
    text: str


# -------------------------
# 유틸
# -------------------------
def load_pages(parsed_json_path: Path) -> List[Page]:
    data = json.loads(parsed_json_path.read_text(encoding="utf-8"))
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
    # 공백 정리만 최소로 (표/마크다운 구조 훼손 방지)
    return line.rstrip()


def is_markdown_table_line(line: str) -> bool:
    # 아주 단순한 표 라인 감지(파이프 포함)
    return "|" in line


def detect_boundary(line: str) -> Tuple[Optional[str], Optional[str]]:
    """
    line에서 경계를 감지하면 (section_title, clause_key) 중 하나 또는 둘 다 반환.
    """
    l = line.strip()
    if not l:
        return None, None

    m = SECTION_TITLE_RE.match(l)
    if m:
        return m.group("title"), None

    m = CLAUSE_RE.match(l)
    if m:
        return None, m.group("key").replace(" ", "")

    m = APPENDIX_RE.match(l)
    if m:
        return None, m.group("key")

    m = NUMBERED_RE.match(l)
    if m:
        # 숫자 키는 너무 많아져서 clause_key로만 저장
        return None, m.group("key").replace(" ", "")

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
        if not b:
            continue

        # 표 블록은 통째로 유지
        if any("|" in line for line in b.splitlines()):
            if len(buf) + len(b) > max_chars:
                flush()
            buf += b + "\n\n"
            continue

        # ✅ look-behind 제거한 문장 분리
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


# -------------------------
# 핵심: 논리 단위 분할
# -------------------------
def split_pages_into_chunks(
    pages: List[Page],
    source_pdf: str,
) -> List[Chunk]:
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
        """
        버퍼의 텍스트를 chunk로 만들고, 너무 작으면 이전 chunk에 합치거나 유지.
        """
        nonlocal buf_lines, buf_page_start, buf_page_end, chunks
        text = "\n".join(buf_lines).strip()
        if not text:
            buf_lines = []
            buf_page_start = None
            buf_page_end = None
            return

        # 너무 짧으면 이전 chunk에 합치기(가능할 때)
        if len(text) < MIN_CHARS_PER_CHUNK and chunks and not force:
            prev = chunks[-1]
            prev.text = (prev.text.rstrip() + "\n\n" + text).strip()
            prev.page_end = max(prev.page_end, buf_page_end or prev.page_end)
            # section/clause는 유지(짧은 조각은 보통 이어지는 내용)
        else:
            chunk_id = f"{Path(source_pdf).stem}__p{buf_page_start:04d}-{buf_page_end:04d}__{len(chunks)+1:05d}"
            chunks.append(Chunk(
                source_pdf=source_pdf,
                chunk_id=chunk_id,
                section_title=current_section,
                clause_key=current_clause,
                page_start=buf_page_start or 0,
                page_end=buf_page_end or (buf_page_start or 0),
                text=text
            ))

        buf_lines = []
        buf_page_start = None
        buf_page_end = None

    for page in pages:
        page_no = page.page
        content = page.content or ""
        lines = [normalize_line(x) for x in content.splitlines()]

        # 페이지가 비어있는 경우는 스킵(필요시 따로 저장 가능)
        if not any(l.strip() for l in lines):
            continue

        for line in lines:
            sec, clause = detect_boundary(line)

            # 경계 감지: 섹션 제목/조항/번호가 나오면 이전 버퍼를 flush
            if sec or clause:
                # 단, 표의 중간에 경계로 오인된 경우를 줄이기 위해
                # 표 라인 연속 중에는 너무 공격적으로 자르지 않음
                in_table_context = (
                    len(buf_lines) >= 2
                    and is_markdown_table_line(buf_lines[-1])
                    and is_markdown_table_line(buf_lines[-2])
                )
                if not in_table_context:
                    flush_buffer()

                if sec:
                    current_section = sec
                    # 섹션이 바뀌면 clause는 리셋(선택)
                    current_clause = None
                if clause:
                    current_clause = clause

            start_buffer(page_no)
            buf_lines.append(line)

            # 버퍼가 너무 길면 소프트 분할(하지만 논리 경계가 없을 때만)
            if sum(len(x) for x in buf_lines) > MAX_CHARS_PER_CHUNK:
                # 일단 flush해서 chunk를 만들고(이 chunk는 현재 section/clause 유지)
                flush_buffer(force=True)

    flush_buffer(force=True)

    # 너무 긴 chunk는 추가 soft split
    final_chunks: List[Chunk] = []
    for c in chunks:
        if len(c.text) <= MAX_CHARS_PER_CHUNK:
            final_chunks.append(c)
        else:
            parts = soft_split_text(c.text, max_chars=SOFT_SPLIT_MAX_CHARS)
            for idx, part in enumerate(parts, start=1):
                cid = f"{c.chunk_id}__s{idx:02d}"
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


# -------------------------
# 저장
# -------------------------
def save_chunks_jsonl(chunks: List[Chunk], out_path: Path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(asdict(c), ensure_ascii=False) + "\n")


def process_one_parsed_json(parsed_json_path: Path, out_dir: Path) -> Path:
    pages = load_pages(parsed_json_path)
    # source_pdf는 pages[0].metadata["source_pdf"]를 우선 사용
    source_pdf = None
    for p in pages:
        sp = p.metadata.get("source_pdf")
        if sp:
            source_pdf = sp
            break
    source_pdf = source_pdf or (parsed_json_path.stem.replace("_parsed", "") + ".pdf")

    chunks = split_pages_into_chunks(pages, source_pdf=source_pdf)
    out_path = out_dir / (parsed_json_path.stem.replace("_parsed", "") + "_chunks.jsonl")
    save_chunks_jsonl(chunks, out_path)
    return out_path


def batch_process_folder(parsed_dir: str, out_dir: str):
    parsed_dir = Path(parsed_dir)
    out_dir = Path(out_dir)

    targets = sorted(parsed_dir.glob("*_parsed.json"))
    print(f"Found {len(targets)} parsed json files.")

    for t in targets:
        try:
            out_path = process_one_parsed_json(t, out_dir)
            print(f"✅ {t.name} -> {out_path.name}")
        except Exception as e:
            print(f"❌ {t.name} failed: {e}")


if __name__ == "__main__":
    # 예시 경로(너 환경에 맞게 수정)
    batch_process_folder(
        parsed_dir="C:/Users/main/Downloads/project2_data/upstage_parsed_raw",
        out_dir="C:/Users/main/Downloads/project2_data/rag_chunks"
    )
