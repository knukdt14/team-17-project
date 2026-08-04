"""
loader.py
- PDF/HWP/Word 문서를 읽어 텍스트로 변환
- 텍스트 레이어가 없는 페이지(사진으로 된 표 등)는 OCR로 보완
- (알려진 한계) 일부 페이지는 표가 이미지로 삽입되어 있는데, 격자/좁은
  컬럼 구조 때문에 Tesseract OCR로도 정확히 읽히지 않음. 이런 페이지는
  일반 OCR 대신 KNOWN_TABLE_OVERRIDES에 수동으로 확인한 텍스트를 등록해
  보정한다 (이 6개 고정 문서에 한정된 임시방편. 문서가 바뀌면 재검증 필요.
  OCR 정확도가 개선되면 제거할 것 - 관련 이슈 참고).
"""

import os
import glob
from dataclasses import dataclass
from typing import List
import io

import fitz  # PyMuPDF
import pytesseract
from PIL import Image

# 텍스트 추출이 너무 적으면 OCR로 폴백하는 기준 (글자 수)
OCR_FALLBACK_THRESHOLD = 100
OCR_LANG = "kor+eng"
OCR_DPI = 300

# 표가 이미지로 삽입되어 OCR로도 정확히 못 읽는 페이지에 대한 수동 보정.
# 키: (파일명, 0-indexed 페이지 번호) -> 사람이 직접 확인해서 넣은 텍스트.
# 일반적인 해결책이 아니라 이 프로젝트의 고정 데이터셋(6개 PDF)에 한정된
# 임시방편이며, 문서가 교체/개정되면 다시 확인해야 함.
KNOWN_TABLE_OVERRIDES = {
    ("국민내일배움카드 운영규정.pdf", 8): """
[표: 제15조(계좌잔액의 차감) 제1항 각 호 - 차감 기준]
구분 | 차감액
1. 집체훈련과정, 비대면실시간훈련과정, 혼합훈련과정에서 질병·사고, 훈련기관의 휴·폐업 등 특별한 사정, 천재지변 등 불가피한 사유 없이 중도에 훈련 수강을 그만둔 경우 및 제35조제1항제1호 또는 제3호에 따라 제적된 경우 | 1회 20만원, 2회 50만원, 3회 이상 100만원
2. 원격훈련과정(다만, 비대면 실시간 훈련과정은 제외한다)에서 질병·사고, 훈련기관의 휴·폐업 등 특별한 사정, 천재지변 등 불가피한 사유 없이 중도에 훈련 수강을 그만둔 경우 및 제35조제1항제2호에 따라 제적된 경우 | 1회 4만원, 2회 10만원, 3회 이상 20만원
3. 거짓이나 그 밖의 부정한 방법으로 출결체크하여 제35조제1항제4호에 따라 제적된 경우 | 전액
4. 제4조제1항의 지원대상에 해당하지 않거나 제4조제2항의 지원제외 대상에 해당함에도 불구하고 거짓이나 그 밖의 부정한 방법으로 계좌를 발급받거나, 지원받은 경우 | 전액
""".strip(),
}


@dataclass
class PageDoc:
    source: str      # 원본 파일명
    page_num: int    # 0-indexed 페이지 번호
    text: str        # 추출된 텍스트
    method: str      # "text" / "ocr" / "text+manual_table"


def _ocr_page(page: fitz.Page) -> str:
    """페이지를 이미지로 렌더링 후 OCR로 텍스트 추출"""
    pix = page.get_pixmap(dpi=OCR_DPI)
    img_bytes = pix.tobytes("png")
    image = Image.open(io.BytesIO(img_bytes))
    text = pytesseract.image_to_string(image, lang=OCR_LANG)
    return text.strip()


def load_pdf(path: str) -> List[PageDoc]:
    """PDF 한 개를 페이지 단위로 읽어서 반환.
    텍스트 레이어가 충분하면 그대로 사용하고,
    부족하면(사진으로 된 표 등) OCR로 재시도.
    알려진 표 누락 페이지는 수동 보정 텍스트를 덧붙인다.
    """
    filename = os.path.basename(path)
    docs = []
    doc = fitz.open(path)

    for i, page in enumerate(doc):
        text = page.get_text().strip()
        method = "text"

        if len(text) < OCR_FALLBACK_THRESHOLD:
            ocr_text = _ocr_page(page)
            if len(ocr_text) > len(text):
                text = ocr_text
                method = "ocr"

        override = KNOWN_TABLE_OVERRIDES.get((filename, i))
        if override:
            text = (text + "\n" + override).strip()
            method = method + "+manual_table" if method != "text" else "text+manual_table"

        docs.append(PageDoc(source=filename, page_num=i, text=text, method=method))

    doc.close()
    return docs


def load_pdf_directory(dir_path: str) -> List[PageDoc]:
    """디렉토리 내 모든 PDF를 읽어서 하나의 리스트로 반환"""
    all_docs = []
    for path in sorted(glob.glob(os.path.join(dir_path, "*.pdf"))):
        all_docs.extend(load_pdf(path))
    return all_docs


# HWP/DOCX는 추후 구현 (현재 데이터셋엔 PDF만 존재)
def load_docx(path: str) -> List[PageDoc]:
    raise NotImplementedError("docx 로더는 아직 미구현")


def load_hwp(path: str) -> List[PageDoc]:
    raise NotImplementedError("hwp 로더는 아직 미구현")


if __name__ == "__main__":
    # 간단 테스트: 국민내일배움카드 운영규정.pdf 로 확인
    test_path = "data/raw/국민내일배움카드 운영규정.pdf"
    pages = load_pdf(test_path)
    print(f"총 {len(pages)}페이지 로드")

    special_pages = [p for p in pages if p.method != "text"]
    print(f"OCR/보정이 적용된 페이지: {len(special_pages)}개 -> {[(p.page_num, p.method) for p in special_pages]}")

    target = next((p for p in pages if p.page_num == 8), None)
    if target:
        print("\n---- 9페이지(0-indexed 8) 미리보기 ----")
        print(target.text[:1500])
        print("\n'20만원' 포함 여부:", "20만원" in target.text)