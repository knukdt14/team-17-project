"""
cohorts.py
- 기수(13/14/15/17기)별 정적 정보(교육기간/장소/모집기간/혜택/문의)를 담아둔다.
- 이 정보는 규정과 달리 RAG로 검색할 필요가 없는 고정 데이터라 model을 거치지 않고
  프론트에서 직접 들고 있는다. data/raw의 모집공고 PDF 내용을 옮겨 적은 것이며,
  공고 내용이 바뀌면 이 파일만 수정하면 된다.
"""

import os

COHORTS = {
    "13기": {
        "logo": "logo_13.png",
        "subtitle": "포항시X경북대학교",
        "title": "[포항시X경북대학교] AI·빅데이터 전문가 양성과정 13기",
        "period": {
            "사전교육": "26.2.2.(월) ~ 26.2.13.(금) · 2주(30시간)",
            "정규교육": "26.2.23.(월) ~ 26.8.19.(수) · 평일 09:00~18:00 · 6개월(976시간)",
        },
        "location": {
            "본교육": "포항시 북구청 문화예술팩토리 5층 교육장",
        },
        "apply_period": "25.12.29.(월) ~ 26.2.15.(일) · 온라인 접수 → 서류심사(선착순 면접)",
        "benefits": [
            "교육비 전액 국비, 훈련장려금 지급, 경북대학교 수료증 발급",
            "기업 대표 및 재직자 특강 진행",
            "수료생 대상 취업지원 서비스 제공(이력서, 포트폴리오 첨삭)",
            "성적&출결 우수자에게 경북대학교 총장상 수여",
            "수료 후 41개 참여기업 취업 지원",
        ],
        "contact": {"전화": "010-8926-8485", "이메일": "khj1219@knu.ac.kr"},
        "homepage": "https://datainstitute.knu.ac.kr/contents/edu/selectEduView.do?edu_id=164&end=Y&menuId=343",
    },
    "14기": {
        "logo": "logo_14.png",
        "subtitle": "아진산업 채용연계",
        "title": "아진산업 채용예정자 부트캠프 (AI·빅데이터 전문가 양성과정 14기)",
        "period": {
            "사전교육": "26.3.23.(월) ~ 26.4.3.(금) · 평일 18:30~21:30 · 2주(30시간)",
            "정규교육": "26.4.9.(목) ~ 26.9.30.(수) · 평일 09:00~18:00 · 6개월(976시간)",
        },
        "location": {
            "사전교육": "경북대학교 복현회관 교육장 1, 2",
            "본교육": "경일대학교 산학교육관 6층 교육장",
        },
        "apply_period": "26.2.12.(목) ~ 26.3.13.(금) · 추가모집 26.3.14.(토) ~ 26.4.8.(수)",
        "benefits": [
            "현대자동차 1차 밴드인 아진산업(주)와 취업연계 (연봉 약 6,200만원)",
            "아진산업과 훈련생 선발 및 교육 공동 진행",
            "교육비 전액 국비, 훈련장려금 지급, 경북대학교 수료증 발급",
            "아진산업 멘토와 함께하는 기술세미나, 현장 실습 및 프로젝트 멘토링",
            "성적&출결 우수자에게 경북대학교 총장상 수여",
        ],
        "contact": {"전화": "010-8926-8485", "이메일": "khj1219@knu.ac.kr"},
        "homepage": "https://datainstitute.knu.ac.kr/contents/edu/selectEduView.do?edu_id=177&end=Y&menuId=343",
    },
    "15기": {
        "logo": "logo_15.jpg",
        "subtitle": "티에이치엔 채용연계",
        "title": "티에이치엔 채용예정자 부트캠프 (AI·빅데이터 전문가 양성과정 15기)",
        "period": {
            "사전교육": "26.4.27.(월) ~ 26.5.8.(금) · 평일 18:30~21:30 · 2주(30시간)",
            "정규교육": "26.5.11.(월) ~ 26.11.2.(월) · 평일 09:00~18:00 · 6개월(976시간)",
        },
        "location": {
            "사전교육": "경북대학교 복현회관 교육장 1, 2",
            "본교육": "경북대학교 복현회관 교육장 3",
        },
        "apply_period": "26.3.13.(금) ~ 26.4.9.(목) · 추가모집 26.4.10.(금) ~ 26.4.30.(목)",
        "benefits": [
            "우수 수료생 THN 채용 연계 기회 제공",
            "교육비 전액 국비 지원 + 훈련장려금 지급",
            "THN 실무진 멘토링 및 현직자 직무 특강",
            "자동차 제조 데이터 기반 AI·BigData 실무 프로젝트",
            "경북대학교 수료증 발급",
        ],
        "contact": {"전화": "010-8926-8485", "이메일": "khj1219@knu.ac.kr"},
        "homepage": "https://datainstitute.knu.ac.kr/contents/edu/selectEduView.do?edu_id=180&end=Y&menuId=343",
    },
    "17기": {
        "logo": "logo_17.png",
        "subtitle": "피엔티 채용연계",
        "title": "피엔티 채용예정자 부트캠프 (AI·빅데이터 전문가 양성과정 17기)",
        "period": {
            "사전교육": "26.6.22.(월) ~ 26.6.26.(금) · 평일 18:30~21:30 · 1주(15시간)",
            "정규교육": "26.6.30.(화) ~ 26.12.30.(수) · 평일 09:00~18:00 · 6개월(1,000시간)",
        },
        "location": {
            "사전교육": "경북대학교 복현회관 교육장 1, 2",
            "본교육": "대구 스마트시티센터 2층",
        },
        "apply_period": "26.5.11.(월) ~ 26.6.10.(수) · 추가모집 26.6.11.(목) ~ 26.6.17.(수)",
        "benefits": [
            "우수 수료생 피엔티(PNT) 채용 연계 기회 제공",
            "교육비 전액 국비 지원 + 훈련장려금 지급",
            "피엔티(PNT) 실무진 멘토링 및 현직자 직무 특강",
            "배터리 설비·2차 전지 관련 데이터 AI·BigData 실무 프로젝트",
            "우수 수료생 경북대학교 총장상 발급, 경북대학교 수료증 발급",
        ],
        "contact": {"전화": "053-950-6742", "이메일": "khj1219@knu.ac.kr"},
        "homepage": "https://datainstitute.knu.ac.kr/contents/edu/selectEduView.do?edu_id=188&end=Y&menuId=343",
    },
}

COHORT_LIST = list(COHORTS.keys())


def get_cohort(name: str) -> dict:
    return COHORTS.get(name, {})


def get_main_location(name: str) -> str:
    """지도에 표시할 대표 장소(본교육 우선, 없으면 사전교육)를 돌려준다."""
    loc = get_cohort(name).get("location", {})
    return loc.get("본교육") or loc.get("사전교육") or ""


_POSTER_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")


def get_posters(name: str) -> list[dict]:
    """frontend/assets/<기수>/ 폴더 안 이미지 파일을 그대로 스캔해서 {url, portrait, width, height}
    형태로 돌려준다. 코드/COHORTS 딕셔너리를 안 건드리고 폴더에 파일만 넣으면(빼면) 그대로 반영된다.
    width/height(원본 픽셀)는 확대/축소 버튼의 기준 크기를 잡는 데 쓴다."""
    assets_dir = os.path.join(os.path.dirname(__file__), "..", "assets", name)
    if not os.path.isdir(assets_dir):
        return []

    posters = []
    for fn in sorted(os.listdir(assets_dir)):
        if not fn.lower().endswith(_POSTER_EXTENSIONS):
            continue
        path = os.path.join(assets_dir, fn)
        portrait, width, height = True, 520, 720
        try:
            from PIL import Image

            with Image.open(path) as im:
                width, height = im.size
                portrait = height >= width
        except Exception:
            pass
        posters.append(
            {"url": f"/assets/{name}/{fn}", "portrait": portrait, "width": width, "height": height}
        )
    return posters
