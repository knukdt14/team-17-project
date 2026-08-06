"""
directions.py
- 카카오모빌리티 Directions API를 frontend 서버(NiceGUI가 내부적으로 들고 있는 FastAPI 앱)에서
  대신 호출하는 프록시 엔드포인트.
- REST 키를 브라우저 JS에 그대로 노출하면 키가 페이지 소스에 그대로 보여서 누구나 긁어갈 수
  있으므로, 서버에서만 키를 쓰고 브라우저에는 좌표/경로 결과만 돌려준다.
- model이나 별도 backend를 안 건드리고 frontend 안에서 끝나도록, nicegui.app(FastAPI 인스턴스)에
  라우트를 직접 붙인다. main.py에서 이 모듈을 import해야 라우트가 등록된다.
"""

import os

import httpx
from fastapi import HTTPException
from fastapi.responses import JSONResponse
from nicegui import app

KAKAO_REST_KEY = os.environ.get("KAKAO_REST_KEY", "")
DIRECTIONS_URL = "https://apis-navi.kakaomobility.com/v1/directions"


@app.get("/api/directions")
async def get_directions(origin: str, destination: str):
    """origin/destination은 "lng,lat" 형식 문자열(카카오 좌표 규칙: x=경도, y=위도).
    성공하면 {"path": [[lng, lat], ...], "distance_m": int, "duration_s": int}를 돌려준다.
    실패해도 지도 화면(map_page.py)은 마커+딥링크 버튼으로 정상 동작하므로, 여기 에러는
    프론트 JS가 조용히 무시하도록 설계돼 있다.
    """
    if not KAKAO_REST_KEY:
        raise HTTPException(status_code=503, detail="KAKAO_REST_KEY가 설정되지 않았습니다.")

    headers = {"Authorization": f"KakaoAK {KAKAO_REST_KEY}"}
    params = {"origin": origin, "destination": destination, "priority": "RECOMMEND"}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(DIRECTIONS_URL, headers=headers, params=params)
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=502, detail=f"카카오모빌리티 API 오류 ({e.response.status_code})"
        ) from e
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"카카오모빌리티 API 호출 실패: {e}") from e

    routes = data.get("routes") or []
    if not routes or routes[0].get("result_code") != 0:
        # result_code/result_msg를 그대로 실어서 돌려준다 - 프론트(map_page.py)가 이걸 보고
        # "경로 자체를 못 찾음"과 "서버/네트워크 문제"를 구분해 좀 더 도움이 되는 안내를 보여준다.
        # (예: 102/103 = 출발지/도착지 주변에 차량 진입 가능한 도로가 없음 - 흔히 대형 시설의
        # POI 좌표가 건물 한가운데로 잡혀서 도로에 스냅이 안 될 때 발생)
        route = routes[0] if routes else {}
        raise HTTPException(
            status_code=404,
            detail={
                "reason": "no_route",
                "result_code": route.get("result_code"),
                "result_msg": route.get("result_msg") or "경로를 찾을 수 없습니다.",
            },
        )

    route = routes[0]
    path: list[list[float]] = []
    for section in route.get("sections", []):
        for road in section.get("roads", []):
            vertexes = road.get("vertexes", [])
            # vertexes는 [x1,y1,x2,y2,...]로 평탄화된 좌표열
            for i in range(0, len(vertexes) - 1, 2):
                path.append([vertexes[i], vertexes[i + 1]])

    summary = route.get("summary", {})
    return JSONResponse(
        {
            "path": path,
            "distance_m": summary.get("distance"),
            "duration_s": summary.get("duration"),
        }
    )
