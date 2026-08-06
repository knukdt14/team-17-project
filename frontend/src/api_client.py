"""
api_client.py
- model 서비스(/ask, /ingest 등) 호출 로직을 한 곳에 모아둔다.
- UI 모듈(chat_page.py, admin_page.py 등)은 이 모듈의 함수만 호출하고 httpx를 직접 쓰지 않는다.
- NiceGUI는 브라우저 연결 하나하나가 그대로 asyncio 코루틴이라, httpx.AsyncClient로 SSE를
  스트리밍하면서 토큰이 도착할 때마다 on_token 콜백을 부르는 방식으로 짠다.
"""

import json
import os
import urllib.parse

import httpx

MODEL_SERVICE_URL = os.environ.get("MODEL_SERVICE_URL", "http://model:8100")
REQUEST_TIMEOUT = float(os.environ.get("MODEL_REQUEST_TIMEOUT", "120"))


class ModelServiceError(Exception):
    """model 호출 실패를 사용자에게 보여줄 메시지와 함께 감싸는 예외."""


def _error_detail(e: httpx.HTTPStatusError, fallback: str) -> str:
    """model이 4xx/5xx와 함께 내려준 {"detail": "..."} 메시지가 있으면 그걸 그대로 보여주고,
    없으면 fallback을 쓴다 (예: 업로드 5개 제한, 파일 없음 등 구체적인 사유를 그대로 노출)."""
    try:
        detail = e.response.json().get("detail")
        if detail:
            return str(detail)
    except Exception:
        pass
    return fallback


async def ask_stream(
    question: str,
    on_token,
    history: list[dict] | None = None,
    tier: str = "free",
    scope: str = "all",
) -> list[dict]:
    """질문을 model의 /ask(SSE)로 보내고, 토큰이 도착할 때마다 on_token(token)을 호출한다.
    history는 아직 model이 안 받아도 무해하게 무시되므로(Pydantic 기본 동작이 정의 안 된 필드를
    그냥 버림) 미리 실어 보내도 안전하다. 스트림이 끝나면 근거 문서(sources) 리스트를 반환한다.

    tier: "free"(Solar) 또는 "paid"(Groq Llama) - 무료/유료 버전 데모용 토글값을 그대로 넘긴다.
    scope: "all"(기본 규정집+업로드 전체) 또는 "uploaded"(관리자 테스트용 - 업로드분만 검색).
    """
    payload: dict = {"question": question, "tier": tier, "scope": scope}
    if history:
        payload["history"] = history

    sources: list = []
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            async with client.stream("POST", f"{MODEL_SERVICE_URL}/ask", json=payload) as resp:
                if resp.status_code == 429:
                    # 동시 요청이 몰려 model이 바쁠 때를 대비한 안내 (model이 아직 429를
                    # 내려주지 않아도 이 분기는 미리 준비해둔 것)
                    raise ModelServiceError("지금 다른 사용자의 답변을 생성하고 있어요. 잠시 후 다시 시도해주세요.")
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    event_raw = line[len("data: ") :]
                    if event_raw == "[DONE]":
                        break
                    event = json.loads(event_raw)
                    if "error" in event:
                        raise ModelServiceError(f"죄송합니다, 답변을 가져오지 못했습니다. ({event['error']})")
                    if "sources" in event:
                        sources.extend(event["sources"])
                        continue
                    token = event.get("token", "")
                    if token:
                        on_token(token)
    except httpx.TimeoutException as e:
        raise ModelServiceError("죄송합니다, 응답 시간이 초과되었습니다. 잠시 후 다시 시도해주세요.") from e
    except httpx.ConnectError as e:
        raise ModelServiceError("죄송합니다, 서버에 연결할 수 없습니다. 잠시 후 다시 시도해주세요.") from e
    except ModelServiceError:
        raise
    except httpx.HTTPError as e:
        raise ModelServiceError(f"죄송합니다, 답변을 가져오지 못했습니다. ({e})") from e

    return sources


async def upload_pdf(filename: str, content: bytes) -> dict:
    """PDF를 model의 /ingest로 올려서 벡터DB에 반영한다."""
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            resp = await client.post(
                f"{MODEL_SERVICE_URL}/ingest",
                files={"file": (filename, content, "application/pdf")},
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.TimeoutException as e:
        raise ModelServiceError(
            "업로드 요청이 시간 초과되었습니다. 파일 크기를 확인하거나 잠시 후 다시 시도해주세요."
        ) from e
    except httpx.ConnectError as e:
        raise ModelServiceError("서버에 연결할 수 없습니다. 잠시 후 다시 시도해주세요.") from e
    except httpx.HTTPStatusError as e:
        raise ModelServiceError(_error_detail(e, f"업로드 실패: {e}")) from e
    except httpx.HTTPError as e:
        raise ModelServiceError(f"업로드 실패: {e}") from e


async def list_files() -> list[dict]:
    """현재 검색에 반영된 PDF(기본 제공 + 업로드) 목록을 model의 /files에서 가져온다."""
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            resp = await client.get(f"{MODEL_SERVICE_URL}/files")
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as e:
        raise ModelServiceError(f"파일 목록을 가져오지 못했습니다: {e}") from e


async def delete_file(filename: str) -> dict:
    """PDF 한 개를 벡터DB/BM25 코퍼스/디스크에서 모두 제거한다.

    filename에 유효하지 않은 유니코드(로케일 문제로 깨진 파일명 등, surrogateescape로
    보존된 문자)가 섞여 있으면 quote()가 기본(errors="strict")으로는 UnicodeEncodeError를
    던지고, 이 함수가 그 예외를 잡지 못해 호출부에서 조용히(알림 없이) 실패한 것처럼
    보이는 문제가 실측으로 확인됨 - errors="surrogateescape"로 원래 바이트를 그대로
    퍼센트 인코딩해서 보낸다."""
    try:
        quoted = urllib.parse.quote(filename, safe="", errors="surrogateescape")
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            resp = await client.delete(f"{MODEL_SERVICE_URL}/files/{quoted}")
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as e:
        raise ModelServiceError(_error_detail(e, f"삭제 실패: {e}")) from e
    except httpx.HTTPError as e:
        raise ModelServiceError(f"삭제 실패: {e}") from e
    except UnicodeError as e:
        raise ModelServiceError(f"삭제 실패: 파일명 인코딩 오류 ({e})") from e
