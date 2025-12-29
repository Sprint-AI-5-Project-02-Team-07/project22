from glob import glob
import win32com.client as win32
from pathlib import Path

def hwpToPdf(file, path):
    if file == '' or path == '':
        print("[에러] 경로가 지정되지 않았습니다.")

        return
    else:
        print("-------------------------필독!-------------------------\n")
        print("\"한글을 이용하여 위 파일에 접근하려는 시도가 있습니다.\"")
        print("와 같은 팝업창이 뜰 경우 [모두 허용]을 눌러주세요.\n")
        print("-------------------------------------------------------")
        file = glob(file + '\*.hwp')

        hwp=win32.gencache.EnsureDispatch("HWPFrame.HwpObject")

        print("프로그램 강제 종료를 원할 경우 cmd 창을 닫아주세요.\n")
        print("-------------------------------------------------------")

        for i in file:
            hwp.Open(i)
            i = i.split('\\')
            i.reverse()
            hwp.SaveAs(path + '/' + i[0].replace('.hwp', '.pdf'), "PDF")
            print("변환 완료 :", path + '/' + i[0])

        hwp.Quit()

        print("-------------------------변환 완료!-------------------------\n")

        return
    
if __name__=="__main__":
    hwpToPdf("C:/Users/main/Downloads/project2_data/files", "C:/Users/main/Downloads/project2_data/hwp_to_pdf")