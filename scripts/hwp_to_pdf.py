import os
import win32com.client

def convert_hwp_to_pdf(source_folder, target_folder):
    try:
        # 1. Dispatch가 아닌 gencache.EnsureDispatch를 사용하여 정적 바인딩 강제 시도
        # 만약 이전에 오류가 났다면 win32com.client.Dispatch("HWPFrame.HwpObject")로 변경
        hwp = win32com.client.Dispatch("HWPFrame.HwpObject")
        hwp.RegisterModule("FilePathCheckDLL", "FilePathCheckerModule")
    except Exception as e:
        print(f"한글 프로그램을 실행할 수 없습니다: {e}")
        return

    if not os.path.exists(target_folder):
        os.makedirs(target_folder)

    files = [f for f in os.listdir(source_folder) if f.lower().endswith(".hwp")]
    print(f"총 {len(files)}개의 HWP 파일을 변환합니다.")

    for filename in files:
        # 경로 끝에 공백이 있거나 특수문자가 있을 경우를 대비해 처리
        hwp_path = os.path.normpath(os.path.join(source_folder, filename))
        pdf_filename = filename.rsplit('.', 1)[0] + ".pdf"
        pdf_path = os.path.normpath(os.path.join(target_folder, pdf_filename))

        if os.path.exists(pdf_path):
            print(f"[Skip] 이미 존재함: {pdf_filename}")
            continue

        try:
            # 문서 열기
            hwp.Open(hwp_path, "HWP", "forceopen:true")
            
            # --- 한글 2024 필살기: SaveAs 메서드의 매개변수를 최소화 ---
            # 포맷 번호 57은 PDF를 의미합니다. (문자열 "PDF" 대신 사용 가능)
            # arg 1: 저장경로, arg 2: 포맷(PDF), arg 3: 옵션
            hwp.SaveAs(pdf_path, "PDF", "") 
            
            print(f"[성공] 변환 완료: {pdf_filename}")
        except Exception as e:
            print(f"[실패] {filename}: {e}")
        finally:
            hwp.Clear(1)

    hwp.Quit()
    print("모든 작업이 완료되었습니다.")
    hwp.Quit()
    print("모든 작업이 완료되었습니다.")

if __name__ == "__main__":
    # 경로를 상황에 맞게 수정하세요
    SOURCE = r"S:\code\codeit_sprint\project-2\data\raw"
    TARGET = r"S:\code\codeit_sprint\project-2\data\files"
    convert_hwp_to_pdf(SOURCE, TARGET)