"""
api_client.py
- backend 게이트웨이(/ask, /upload 등) 호출 로직을 한 곳에 모아둔다.
- UI 모듈(chat_page.py, admin_page.py 등)은 이 모듈의 함수만 호출하고 requests를 직접 쓰지 않는다.
- 나중에 스트리밍/대화이력/피드백 저장 등이 backend에 추가돼도 UI 쪽은 거의 안 건드리고
  이 파일만 확장하면 되도록 창구를 하나로 모아둠.
"""

import json
import os

import requests

BACKEND_URL = os.environ.get("BACKEND_URL", "http://backend:8000")
REQUEST_TIMEOUT = float(os.environ.get("BACKEND_REQUEST_TIMEOUT", "120"))


class BackendError(Exception):
    """backend/model 호출 실패를 사용자에게 보여줄 메시지와 함께 감싸는 예외."""


def ask_stream(question: str, history: list[dict] | None = None):
    """질문을 backend /ask(SSE)로 보내고, 토큰을 하나씩 yield하는 제너레이터.
    st.write_stream()에 그대로 넘기면 토큰이 도착하는 대로 화면에 찍힌다.
    backend가 보내는 이벤트 형식: "data: {"token": "..."}\\n\\n" 반복 후 "data: [DONE]\\n\\n".
    에러가 나면 "data: {"error": "..."}\\n\\n" 형태로 오는데, 이건 BackendError로 바꿔서 올린다.
    history는 아직 backend가 안 받아도 무해하게 무시된다.
    """
    payload: dict = {"question": question}
    if history:
        payload["history"] = history

    try:
        resp = requests.post(
            f"{BACKEND_URL}/ask", json=payload, timeout=REQUEST_TIMEOUT, stream=True
        )
        if resp.status_code == 429:
            raise BackendError("🚦 지금 다른 사용자의 답변을 생성하고 있어요. 잠시 후 다시 시도해주세요.")
        resp.raise_for_status()

        for raw_line in resp.iter_lines(decode_unicode=True):
            if not raw_line or not raw_line.startswith("data:"):
                continue
            payload_str = raw_line[len("data:") :].strip()
            if payload_str == "[DONE]":
                return
            try:
                data = json.loads(payload_str)
            except json.JSONDecodeError:
                continue
            if "error" in data:
                raise BackendError(f"❌ {data['error']}")
            token = data.get("token")
            if token:
                yield token
    except requests.Timeout as e:
        raise BackendError("⏱️ 죄송합니다, 응답 시간이 초과되었습니다. 잠시 후 다시 시도해주세요.") from e
    except requests.ConnectionError as e:
        raise BackendError("🔌 죄송합니다, 서버에 연결할 수 없습니다. 잠시 후 다시 시도해주세요.") from e
    except requests.RequestException as e:
        raise BackendError(f"❌ 죄송합니다, 답변을 가져오지 못했습니다. ({e})") from e


def upload_pdf(filename: str, content: bytes) -> dict:
    """PDF를 backend /upload로 올려서 벡터DB에 반영한다."""
    try:
        resp = requests.post(
            f"{BACKEND_URL}/upload",
            files={"file": (filename, content, "application/pdf")},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.Timeout as e:
        raise BackendError(
            "⏱️ 업로드 요청이 시간 초과되었습니다. 파일 크기를 확인하거나 잠시 후 다시 시도해주세요."
        ) from e
    except requests.ConnectionError as e:
        raise BackendError("🔌 서버에 연결할 수 없습니다. 잠시 후 다시 시도해주세요.") from e
    except requests.RequestException as e:
        raise BackendError(f"❌ 업로드 실패: {e}") from e


def send_feedback(question: str, answer: str, rating: str) -> None:
    """답변 👍/👎 피드백을 backend로 보낸다.
    backend에 /feedback 엔드포인트가 아직 없어서 실패해도 사용자에게 에러를 보여주지 않고
    조용히 무시한다 (나중에 backend가 엔드포인트를 추가하면 이 함수는 그대로 두고 자동으로
    저장되기 시작함).
    """
    try:
        requests.post(
            f"{BACKEND_URL}/feedback",
            json={"question": question, "answer": answer, "rating": rating},
            timeout=5,
        )
    except requests.RequestException:
        pass
