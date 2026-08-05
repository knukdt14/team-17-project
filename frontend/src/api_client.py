"""
api_client.py
- model 서비스(/ask, /ingest 등) 호출 로직을 한 곳에 모아둔다.
- UI 모듈(chat_page.py, admin_page.py 등)은 이 모듈의 함수만 호출하고 httpx를 직접 쓰지 않는다.
- NiceGUI는 브라우저 연결 하나하나가 그대로 asyncio 코루틴이라, httpx.AsyncClient로 SSE를
  스트리밍하면서 토큰이 도착할 때마다 on_token 콜백을 부르는 방식으로 짠다.
"""

import json
import os

import httpx

MODEL_SERVICE_URL = os.environ.get("MODEL_SERVICE_URL", "http://model:8100")
REQUEST_TIMEOUT = float(os.environ.get("MODEL_REQUEST_TIMEOUT", "120"))


class ModelServiceError(Exception):
    """model 호출 실패를 사용자에게 보여줄 메시지와 함께 감싸는 예외."""


async def ask_stream(question: str, on_token, history: list[dict] | None = None) -> list[dict]:
    """질문을 model의 /ask(SSE)로 보내고, 토큰이 도착할 때마다 on_token(token)을 호출한다.
    history는 아직 model이 안 받아도 무해하게 무시되므로(Pydantic 기본 동작이 정의 안 된 필드를
    그냥 버림) 미리 실어 보내도 안전하다. 스트림이 끝나면 근거 문서(sources) 리스트를 반환한다.
    """
    payload: dict = {"question": question}
    if history:
        payload["history"] = history

    sources: list = []
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            async with client.stream("POST", f"{MODEL_SERVICE_URL}/ask", json=payload) as resp:
                if resp.status_code == 429:
                    # 동시 요청이 몰려 model이 바쁠 때를 대비한 안내 (model이 아직 429를
                    # 내려주지 않아도 이 분기는 미리 준비해둔 것)
                    raise ModelServiceError("🚦 지금 다른 사용자의 답변을 생성하고 있어요. 잠시 후 다시 시도해주세요.")
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    event_raw = line[len("data: ") :]
                    if event_raw == "[DONE]":
                        break
                    event = json.loads(event_raw)
                    if "error" in event:
                        raise ModelServiceError(f"❌ 죄송합니다, 답변을 가져오지 못했습니다. ({event['error']})")
                    if "sources" in event:
                        sources.extend(event["sources"])
                        continue
                    token = event.get("token", "")
                    if token:
                        on_token(token)
    except httpx.TimeoutException as e:
        raise ModelServiceError("⏱️ 죄송합니다, 응답 시간이 초과되었습니다. 잠시 후 다시 시도해주세요.") from e
    except httpx.ConnectError as e:
        raise ModelServiceError("🔌 죄송합니다, 서버에 연결할 수 없습니다. 잠시 후 다시 시도해주세요.") from e
    except ModelServiceError:
        raise
    except httpx.HTTPError as e:
        raise ModelServiceError(f"❌ 죄송합니다, 답변을 가져오지 못했습니다. ({e})") from e

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
            "⏱️ 업로드 요청이 시간 초과되었습니다. 파일 크기를 확인하거나 잠시 후 다시 시도해주세요."
        ) from e
    except httpx.ConnectError as e:
        raise ModelServiceError("🔌 서버에 연결할 수 없습니다. 잠시 후 다시 시도해주세요.") from e
    except httpx.HTTPError as e:
        raise ModelServiceError(f"❌ 업로드 실패: {e}") from e
