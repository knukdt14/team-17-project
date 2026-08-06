"""
directions.py
- 카카오모빌리티 Directions API(자동차)와 카카오맵 API(대중교통)를 frontend 서버(NiceGUI가
  내부적으로 들고 있는 FastAPI 앱)에서 대신 호출하는 프록시 엔드포인트.
- REST 키를 브라우저 JS에 그대로 노출하면 키가 페이지 소스에 그대로 보여서 누구나 긁어갈 수
  있으므로, 서버에서만 키를 쓰고 브라우저에는 좌표/경로 결과만 돌려준다.
- model이나 별도 backend를 안 건드리고 frontend 안에서 끝나도록, nicegui.app(FastAPI 인스턴스)에
  라우트를 직접 붙인다. main.py에서 이 모듈을 import해야 라우트가 등록된다.
- 두 API는 발급 주체(제품)가 다르다: 자동차 길찾기(/v1/directions)는 "카카오모빌리티", 대중교통
  길찾기(/v2/routing/publictraffic)는 "카카오맵" 제품이다. 인증 방식(REST API 키를
  `Authorization: KakaoAK ...` 헤더로)은 동일해서 같은 KAKAO_REST_KEY를 그대로 쓰지만,
  카카오디벨로퍼스 콘솔의 [앱] > [제품 설정] > [카카오맵]에서 "사용 설정"을 따로 켜야 대중교통
  쪽이 동작한다(2026-07-21 카카오 공지). 이건 코드로 할 수 없는, 콘솔에서 한 번 눌러줘야 하는
  설정이라 팀원이 직접 해줘야 한다.
"""

import os

import httpx
from fastapi import HTTPException
from fastapi.responses import JSONResponse
from nicegui import app

KAKAO_REST_KEY = os.environ.get("KAKAO_REST_KEY", "")
DIRECTIONS_URL = "https://apis-navi.kakaomobility.com/v1/directions"
TRANSIT_URL = "https://dapi.kakao.com/v2/routing/publictraffic"


@app.get("/api/directions")
async def get_directions(origin: str, destination: str, priority: str = "RECOMMEND"):
    """origin/destination은 "lng,lat" 형식 문자열(카카오 좌표 규칙: x=경도, y=위도).
    priority는 기본값 RECOMMEND(추천 경로) - 프론트에서 TIME(최소시간)/DISTANCE(최단거리)로
    다시 호출하면 다른 기준의 대안 경로를 추가로 받아올 수 있다(기존 호출부는 priority를
    안 넘기니 동작이 그대로 유지된다).
    성공하면 {"path": [[lng, lat], ...], "distance_m": int, "duration_s": int}를 돌려준다.
    실패해도 지도 화면(map_page.py)은 마커+딥링크 버튼으로 정상 동작하므로, 여기 에러는
    프론트 JS가 조용히 무시하도록 설계돼 있다.
    """
    if not KAKAO_REST_KEY:
        raise HTTPException(status_code=503, detail="KAKAO_REST_KEY가 설정되지 않았습니다.")

    headers = {"Authorization": f"KakaoAK {KAKAO_REST_KEY}"}
    params = {"origin": origin, "destination": destination, "priority": priority}

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


@app.get("/api/transit")
async def get_transit(origin: str, destination: str):
    """origin/destination은 "lng,lat" 형식 문자열(/api/directions와 동일한 규칙).
    자동차 경로(/api/directions)와는 완전히 별개의 카카오 제품(카카오맵 API)을 쓰는 독립된
    엔드포인트라, 이게 실패해도 자동차 경로 기능에는 전혀 영향이 없다.
    성공하면 {"routes": [{"type": "BUS"|"SUBWAY"|"BUS_AND_SUBWAY", "distance_m": int,
    "duration_s": int, "transfers": int, "fare": int|None,
    "steps": [{"mode": "WALK"|"BUS"|"SUBWAY", "guidance": str, "distance_m": int,
    "duration_s": int, "vehicle_name": str|None, "path": [[lng, lat], ...]}, ...]}, ...]}를
    돌려준다 (최대 카카오가 주는 만큼, 보통 몇 개의 후보 경로).
    """
    if not KAKAO_REST_KEY:
        raise HTTPException(status_code=503, detail="KAKAO_REST_KEY가 설정되지 않았습니다.")

    try:
        start_x, start_y = origin.split(",")
        end_x, end_y = destination.split(",")
    except ValueError as e:
        raise HTTPException(status_code=400, detail="origin/destination은 'lng,lat' 형식이어야 합니다.") from e

    headers = {"Authorization": f"KakaoAK {KAKAO_REST_KEY}"}
    params = {"start_x": start_x, "start_y": start_y, "end_x": end_x, "end_y": end_y}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(TRANSIT_URL, headers=headers, params=params)
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPStatusError as e:
        # 카카오맵 제품이 카카오디벨로퍼스 콘솔에서 아직 "사용 설정"이 안 돼있으면 보통 401/403이
        # 난다 - 원인을 바로 알 수 있게 상태 코드를 그대로 실어 보낸다.
        detail = f"카카오맵 대중교통 API 오류 ({e.response.status_code})"
        if e.response.status_code in (401, 403):
            detail += " - 카카오디벨로퍼스 콘솔 [앱] > [제품 설정] > [카카오맵]에서 사용 설정이 켜져있는지 확인해주세요."
        raise HTTPException(status_code=502, detail=detail) from e
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"카카오맵 대중교통 API 호출 실패: {e}") from e

    if data.get("status") != "OK":
        raise HTTPException(
            status_code=404,
            detail={
                "reason": "no_transit_route",
                "status": data.get("status"),
                "result_msg": "대중교통 경로를 찾을 수 없습니다.",
            },
        )

    routes = []
    for route in data.get("routes", []):
        props = route.get("properties", {})
        fare = props.get("fare") or {}
        steps = []
        for step in route.get("steps", []):
            step_props = step.get("properties", {})
            vehicles = step_props.get("vehicles") or []
            # "vehicles"는 리스트지만 실제로는 이 구간에 하나만 들어있는 게 보통이라 첫 번째만 쓴다.
            vehicle_type = vehicles[0].get("type") if vehicles else None
            vehicle_name = vehicles[0].get("name") if vehicles else None
            steps.append(
                {
                    "mode": vehicle_type or "WALK",
                    "guidance": step_props.get("guidance"),
                    "distance_m": step_props.get("distance"),
                    "duration_s": step_props.get("time"),
                    "vehicle_name": vehicle_name,
                    "path": (step.get("path") or {}).get("points", []),
                }
            )
        routes.append(
            {
                "type": props.get("type"),
                "distance_m": props.get("totalDistance"),
                "duration_s": props.get("totalTime"),
                "transfers": props.get("transfers"),
                "fare": fare.get("value"),
                "steps": steps,
            }
        )

    return JSONResponse({"routes": routes})
