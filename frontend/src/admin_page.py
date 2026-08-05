"""
admin_page.py
- 관리자 전용 화면: 규정 PDF 업로드/반영.
- theme.py의 좌측 드로어는 is_admin()일 때만 이 페이지 링크를 보여주지만, URL을 직접
  입력해서 들어올 수도 있으니 이 페이지 자체에서도 로그인 여부를 한 번 더 확인한다.
"""

from nicegui import ui

from api_client import ModelServiceError, upload_pdf
from auth import is_admin
from theme import frame, page_header


@ui.page("/admin")
def admin_page():
    frame(current_path="/admin")
    page_header("🛠️", "관리자 - 규정 PDF 관리", "규정이 바뀌었을 때 새 PDF를 업로드해서 벡터DB에 반영합니다.")

    if not is_admin():
        ui.label("관리자로 로그인해야 이용할 수 있습니다.").classes("text-amber-600")
        return

    status_label = ui.label("").classes("mt-3 text-sm")

    async def _handle_upload(e):
        content = await e.file.read()
        status_label.text = "업로드 및 반영 중..."
        status_label.classes(remove="text-red-500 text-green-600", add="text-gray-500")
        try:
            data = await upload_pdf(e.file.name, content)
            status_label.text = f"✅ {data['filename']} 반영 완료 (청크 {data['chunks_added']}개 추가)"
            status_label.classes(remove="text-gray-500 text-red-500", add="text-green-600")
        except ModelServiceError as err:
            status_label.text = str(err)
            status_label.classes(remove="text-gray-500 text-green-600", add="text-red-500")

    ui.upload(on_upload=_handle_upload, auto_upload=True, label="PDF 파일 업로드").props("accept=.pdf").classes(
        "w-full max-w-md"
    )

    ui.separator().classes("my-5")
    ui.label("업로드된 문서 목록").classes("text-indigo-600 font-extrabold text-base mb-2")
    ui.label(
        "📋 문서 목록 조회/삭제 기능은 아직 model에 관련 API(/documents 등)가 없어서 준비 중입니다. "
        "추가되면 여기에 목록·삭제 UI를 연결하겠습니다."
    ).classes("text-gray-500 text-sm")
