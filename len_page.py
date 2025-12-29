import fitz  # PyMuPDF
from pathlib import Path
import statistics

def is_two_up_pdf(pdf_path, sample_pages=3, x_split_ratio=0.45):
    """
    PDF가 2-up인지 판별
    - 앞쪽 몇 페이지만 샘플링
    """
    doc = fitz.open(pdf_path)
    pages_to_check = min(sample_pages, len(doc))

    two_up_votes = 0

    for i in range(pages_to_check):
        page = doc[i]
        blocks = page.get_text("blocks")

        x_positions = []
        page_width = page.rect.width

        for b in blocks:
            x0 = b[0]
            x_center = x0 / page_width
            x_positions.append(x_center)

        if not x_positions:
            continue

        # 좌/우로 나뉘는지 확인
        left = [x for x in x_positions if x < x_split_ratio]
        right = [x for x in x_positions if x > (1 - x_split_ratio)]

        if left and right:
            two_up_votes += 1

    doc.close()

    # 과반 이상이 2-up이면 2-up으로 판정
    return two_up_votes >= (pages_to_check // 2 + 1)


def analyze_pdf_folder(pdf_dir):
    pdf_dir = Path(pdf_dir)
    one_up = []
    two_up = []

    for pdf in pdf_dir.glob("*.pdf"):
        try:
            if is_two_up_pdf(pdf):
                two_up.append(pdf.name)
            else:
                one_up.append(pdf.name)
        except Exception as e:
            print(f"[ERROR] {pdf.name}: {e}")

    print("\n=== PDF 레이아웃 분석 결과 ===")
    print(f"1-page (1-up) PDF 개수 : {len(one_up)}")
    print(f"2-page (2-up) PDF 개수 : {len(two_up)}")
    for i in two_up:
        print(i)
    return one_up, two_up


if __name__ == "__main__":
    one_up, two_up = analyze_pdf_folder(
        "C:/Users/main/Downloads/project2_data/pdf_1up_only"
    )
