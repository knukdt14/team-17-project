"""
map_page.py
- 선택한 기수의 교육 장소를 카카오맵으로 보여준다.
- 좌표를 직접 관리하지 않고, 카카오맵 JS SDK로 장소(POI)를 검색해 마커를 찍는다
  (서버/모델 쪽 코드 변경 불필요).
- Kakao Geocoder(주소 검색)는 도로명/지번 주소만 인식해서 "5층 교육장"처럼 건물명 뒤에
  층/호실이 붙은 우리 데이터는 검색이 거의 실패한다. 검색은 3단계 폴백으로 진행한다:
  1) 장소(POI) 검색 Places.keywordSearch(건물명) - 등록된 유명 장소면 여기서 바로 잡힘
  2) 실패하면 _KNOWN_ADDRESSES에 등록해둔 실제 도로명주소로 Geocoder.addressSearch
     (대학 내부 교육관처럼 POI로 등록 안 된 건물을 위한 보강 - 좌표를 사람이 직접
     추정하지 않고, 검증된 정식 주소를 카카오 자체 지오코더에 맡긴다)
  3) 그래도 실패하면 원본 전체 문자열(예: "경일대학교 산학교육관 6층 교육장")로 마지막 시도
- "카카오맵으로 길찾기" 버튼은 카카오맵 앱/웹으로 여는 딥링크일 뿐이라 Directions API를
  호출하지 않는다. 도착지만 넘기면 출발지(현재 위치)는 카카오맵 앱이 알아서 잡는다.
  이 버튼은 반드시 새 탭에서 열려야 하는데, raw <a onclick=...> HTML은 NiceGUI가
  ui.html() 콘텐츠에 적용하는 살균(sanitize) 처리에 걸려 onclick이 씹히는 문제가 있었다.
  그래서 이 버튼만은 NiceGUI가 공식 지원하는 ui.link(new_tab=True) 컴포넌트로 만든다
  (진짜 <a target="_blank">를 프레임워크가 직접 보장해줌).
- 출발지는 브라우저 위치를 자동으로 가져오지 않는다 (환경에 따라 부정확할 수 있고,
  사용자 동의 없이 위치를 바로 요청하는 것도 좋은 UX가 아님). 대신 출발지를 직접
  입력하는 텍스트 필드 + "경로 찾기" 버튼을 기본으로 제공하고, 원하면 "내 위치 자동으로
  사용" 버튼으로 Geolocation을 켤 수 있게 옵션으로만 둔다.
- KAKAO_JS_KEY가 없으면 지도 없이 딥링크 버튼만 보여준다.
- main.py의 ui.sub_pages가 이 함수를 "/map" 콘텐츠로 호출하므로 @ui.page 데코레이터와
  frame() 호출은 여기서 하지 않는다(헤더는 root_page에서 한 번만 그린다).
- ui.sub_pages는 탭 이동을 브라우저 새로고침 없이 client-side로 처리하는데,
  ui.add_body_html()로 넣은 <script>는 이런 재진입 상황에서 다시 실행되지 않을 수 있다
  (다른 탭 갔다가 "오시는길"로 돌아오면 지도가 아예 안 뜨는 문제로 나타남). 그래서 지도
  초기화/경로 로직은 ui.run_javascript()로 호출한다 - 이건 map_page()가 실행될 때마다
  "지금 붙어있는 클라이언트에게 이 JS를 실행해라"고 그때그때 보내는 방식이라 재진입에도
  항상 실행된다.
- 카카오맵 SDK <script>는 여기서 붙이지 않는다. 처음엔 이 함수 안에서 JS로 동적으로
  <script> 태그를 만들어 붙였는데(autoload=false + kakao.maps.load() 방식), sub_pages
  재진입 시 간헐적으로 초기화가 멈추는(새로고침해야만 되는) 문제가 있었다. 그래서
  main.py의 root_page()가 진짜 페이지 로드 시점에 <head>에 한 번만 선언적으로 붙이는
  방식으로 되돌렸다(예전에 항상 안정적으로 동작하던 방식과 동일). 여기서는 그게 준비될
  때까지 window.kakao.maps.LatLng 존재 여부만 기다린다(waitUntilReady).

- [모드별 배타적 표시] 실제 카카오맵 앱처럼 자동차/대중교통/도보 세 모드 중 항상 하나만
  지도에 그려진다(currentMode). 세 모드의 kakao.maps.Polyline 객체를 서로 다른 변수/배열
  (carLines/transitLinesByRoute/walkLine)에 따로 보관해두고, 모드를 바꿀 때는 새로 지도를
  그리는 게 아니라 이미 만들어둔 Polyline의 setMap(map)/setMap(null)만 토글한다 - 한 번
  불러온 경로는 다시 API를 호출하지 않고 캐시된 걸 재사용한다(불필요한 재요청/깜빡임 방지).
  대중교통은 카카오가 환승 조합이 다른 대안 경로를 여러 개 내려줄 수 있어서, 자동차의
  추천/최소시간/최단거리 선택형 칩과 같은 방식으로 routes[] 전체를 미리 그려두고
  (transitLinesByRoute[i]) 패널에서 고른 인덱스(transitSelectedIndex)의 것만 보여준다.
- [자동차 경로 대안 선택] priority=RECOMMEND/TIME/DISTANCE 세 기준을 "추천 경로/최소시간/
  최단거리"로 라벨링해 선택형 칩으로 제공한다. 이전엔 세 기준을 항상 동시에(옅은 점선으로)
  겹쳐 그렸는데, 이번 요청으로 "한 번에 하나만" 보이게 바꿨다 - RECOMMEND는 사용자가 검색한
  직후 바로 그리고, TIME/DISTANCE는 화면엔 안 그린 채 백그라운드로 미리 불러와서(지도에는
  안 보이지만 거리/시간 정보는 패널에 채워짐) 사용자가 칩을 누르는 순간 바로 전환되게 한다.
  "무료(톨게이트 회피)" 옵션은 만들지 않았다 - 카카오모빌리티 자동차 길찾기 공식 문서가 JS로
  렌더링되는 SPA라 자동으로 확인할 수 없었고, 다른 경로(devtalk 검색)로도 avoid/toll 관련
  파라미터의 정확한 이름을 확인하지 못했다. 검증 안 된 파라미터를 임의로 붙이면 카카오 API가
  조용히 무시하거나 에러를 낼 수 있어서, 이미 실제로 동작이 확인된 세 기준만 제공한다.
- [도보 모드] 카카오맵 API(2026-07-21 신설) 도보 경로 조회를 새 백엔드 엔드포인트
  (/api/walking, directions.py)로 프록시해서 쓴다. 자동차/대중교통과는 별도 기능이라 이게
  실패해도 다른 모드에는 전혀 영향이 없다.
- [우측 경로 패널] 지도를 flex 컨테이너(#kdt-map-layout)로 감싸서 왼쪽엔 지도
  (#kdt-map-wrap, flex:1), 오른쪽엔 경로 옵션 패널(#kdt-side-panel, 고정 폭)을 둔다.
  패널은 출발지 검색 전에는 display:none이라 지도가 이전처럼 꽉 차게 보이고, 경로를 찾은
  순간부터만 나타난다. #kdt-map에 이미 붙어있는 ResizeObserver가 패널이 나타나며 지도 폭이
  줄어드는 것도 자동으로 감지해서 map.relayout()을 호출해주기 때문에, 패널 표시/숨김 로직에
  별도의 relayout 호출을 추가하지 않아도 된다.
"""

import json
import os
import re
from urllib.parse import quote

from nicegui import app, ui

from cohorts import get_main_location
from theme import ACCENT, INK, MUTED, page_header

KAKAO_JS_KEY = os.environ.get("KAKAO_JS_KEY", "")

_SUFFIX_RE = re.compile(r"\s*(?:\d+층\s*)?교육장(?:\s*\d+(?:,\s*\d+)*)?\s*$|\s*\d+층\s*$")


def _place_keyword(location: str) -> str:
    simplified = _SUFFIX_RE.sub("", location).strip()
    return simplified or location


# keywordSearch(POI 검색)이 등록 안 된 건물명(예: 대학 내부 특정 교육관)에서 실패할 때를
# 대비한 폴백. 건물명을 실제 도로명주소로 매핑해두면 Kakao Geocoder가 거의 항상 정확히
# 찾아준다 (사람이 좌표를 직접 추정/하드코딩하지 않아도 됨). _place_keyword()로 뽑은
# 건물명이 key라서, cohorts.py에 새 장소가 추가돼도 여기 없으면 기존 로직(keywordSearch
# -> 원본 문자열 addressSearch)으로 자연스럽게 폴백된다.
_KNOWN_ADDRESSES = {
    "포항시 북구청 문화예술팩토리": "경북 포항시 북구 삼호로 36",
    "경북대학교 복현회관": "대구광역시 북구 대학로 80",
    "경일대학교 산학교육관": "경상북도 경산시 하양읍 부호리 359",
    "대구 스마트시티센터": "대구광역시 수성구 유니버시아드로 119",
}


def map_page():
    cohort = app.storage.user.get("selected_cohort")
    location = get_main_location(cohort)

    if not location:
        page_header("place", "오시는길")
        ui.label("먼저 기수를 선택해주세요.").classes("text-gray-500")
        return

    search_link = f"https://map.kakao.com/link/search/{quote(location)}"

    def _location_badge():
        # 예전엔 이 카드가 헤더 아래 별도 줄(w-full)로 있어서 지도를 보려면 스크롤을 한 번
        # 더 내려야 했다. page_header의 right 슬롯에 넣어 제목과 같은 줄에 나란히 배치하면
        # 세로 스크롤이 줄어든다. flex-grow로 제목 옆 남은 공간을 채우도록 키워서(化면이
        # 넓을 때 박스가 훨씬 커 보이게) 글자 크기도 그에 맞춰 키웠다.
        with ui.card().classes("px-8 py-6 kdt-fade-up flex-grow"):
            ui.label(cohort).classes("text-lg font-bold").style(f"color:{ACCENT};")
            ui.label(location).classes("text-4xl font-extrabold mt-1 whitespace-nowrap").style(f"color:{INK};")

    # compact_right=True: justify-between을 쓰면 화면이 넓을 때 제목과 장소 카드 사이
    # 공백이 너무 커 보인다는 피드백을 받아, 제목 옆에 적당한 간격만 두고 붙인다.
    page_header("place", "오시는길", "", kicker="LOCATION", right=_location_badge, compact_right=True)

    if not KAKAO_JS_KEY:
        ui.label("지도 미리보기는 KAKAO_JS_KEY가 설정되면 표시됩니다. 지금은 길찾기 링크만 이용해주세요.").classes(
            "text-sm mb-3"
        ).style(f"color:{MUTED};")
        ui.link("카카오맵으로 길찾기", search_link, new_tab=True).classes(
            "block w-full text-center bg-yellow-300 text-gray-900 font-bold rounded-xl py-3 no-underline"
        )
        return

    keyword = _place_keyword(location)
    known_address = _KNOWN_ADDRESSES.get(keyword)

    # 출발지 수동 입력 - 자동으로 위치를 잡지 않고, 사용자가 직접 입력한 걸 우선한다.
    with ui.card().classes("w-full p-4 mb-4 kdt-fade-up"):
        ui.label("출발지에서 경로 보기").classes("text-sm font-bold mb-2").style(f"color:{INK};")
        with ui.row().classes("w-full items-center gap-2 flex-nowrap"):
            origin_input = ui.input(
                placeholder="출발지 주소나 건물명 (예: 대구역, OO아파트, 시청 등)"
            ).classes("flex-grow").props("dense outlined")

            def _find_route_from_text():
                text = (origin_input.value or "").strip()
                if not text:
                    ui.notify("출발지를 입력해주세요.", type="warning")
                    return
                ui.run_javascript(f"window.kdtRouteFromText && window.kdtRouteFromText({json.dumps(text)});")

            ui.button("경로 찾기", icon="directions", on_click=_find_route_from_text).props(
                "no-caps unelevated color=primary"
            )
        # 검색하면 여러 후보(예: "동대구역"의 역 본체/1호선/대경선/주차장 등)가 나올 수 있는데,
        # 이 리스트에 후보들을 카드로 보여주면 사용자가 원하는 걸 직접 골라서 바로 경로를 볼 수
        # 있다 - 자동 시도 동작 자체는 그대로 두고, 추가 선택지로만 얹는다
        # (JS의 renderCandidates()가 채운다).
        ui.html('<div id="kdt-candidates" style="display:none;"></div>').classes("w-full")
        with ui.row().classes("items-center gap-4 mt-1 flex-wrap"):
            ui.button(
                "내 위치 자동으로 사용",
                icon="my_location",
                on_click=lambda: ui.run_javascript(
                    "window.kdtRouteFromGeolocation && window.kdtRouteFromGeolocation();"
                ),
            ).props("flat no-caps dense").classes("text-xs px-0").style(f"color:{MUTED};")
            ui.button(
                "대중교통으로 보기",
                icon="directions_transit",
                on_click=lambda: ui.run_javascript("window.kdtShowTransit && window.kdtShowTransit();"),
            ).props("flat no-caps dense").classes("text-xs px-0").style(f"color:{MUTED};")

    with ui.card().classes("w-full p-3 kdt-reveal"):
        # 카드(w-full)는 flex 컨테이너라서, ui.html()이 만드는 wrapper div도 명시적으로
        # w-full을 안 주면 flex item 기본 동작(shrink-to-fit)으로 폭이 0에 수렴한다.
        # 그러면 안의 #kdt-map(style width:100%)도 "0의 100%"라 결국 0폭이 되고, 카카오맵이
        # 그 순간의 컨테이너 크기를 기준으로 지도를 만들어서 화면 왼쪽 일부에만 좁게 그려진다.
        # #kdt-map-layout(flex row) 안에 지도(flex:1, 대부분의 폭)와 경로 패널(고정 폭,
        # 경로가 있을 때만 보임)을 나란히 둔다.
        ui.html(
            f"""
            <div id="kdt-map-layout" style="display:flex;gap:12px;align-items:flex-start;width:100%;">
              <div id="kdt-map-wrap" style="flex:1 1 0%;min-width:0;">
                <div id="kdt-map" style="width:100%;height:520px;border-radius:12px;"></div>
                <div id="kdt-route-info" style="display:none;margin-top:12px;padding:10px 14px;
                     border-radius:10px;font-size:0.85rem;font-weight:700;"></div>
              </div>
              <div id="kdt-side-panel" style="display:none;flex:0 0 auto;width:22%;min-width:200px;
                   max-width:280px;border:1px solid #eee;border-radius:12px;padding:12px;
                   background:#fafafa;box-sizing:border-box;"></div>
            </div>
            """
        ).classes("w-full")
        with ui.row().classes("items-center gap-3 mt-3 flex-nowrap"):
            ui.link("카카오맵 앱으로 길찾기", search_link, new_tab=True).props("id=kdt-route-link").classes(
                "px-4 py-2.5 rounded-xl font-bold no-underline text-sm whitespace-nowrap"
            ).style("background:#FEE500;color:#191919;")
            ui.label(
                "이 페이지에서 자동으로 경로가 안 그려지면 이 버튼으로 카카오맵 앱/웹에서 바로 안내받을 수 있어요."
            ).classes("text-xs").style(f"color:{MUTED};")

    # main.py가 ui.sub_pages로 화면을 client-side 라우팅하면서 map_page()가 매번 다시
    # 호출되는데, ui.add_body_html()로 넣은 <script>는 (특히 sub_pages 전환처럼 브라우저가
    # 실제로 새로고침되지 않는 상황에서) 두 번째 방문부터는 다시 실행이 안 되는 경우가 있다
    # (NiceGUI GitHub 이슈로도 보고된 문제). 그래서 ui.run_javascript()로 바꿨다 - 이건
    # "지금 붙어있는 클라이언트한테 이 JS를 실행해라"라고 그때그때 보내는 방식이라, 처음
    # 진입이든 tab 이동으로 재진입이든 map_page()가 호출될 때마다 항상 실행된다.
    # 카카오맵 SDK <script> 자체는 여기서 붙이지 않는다 - main.py의 root_page()가 진짜
    # 페이지 로드 시점에 <head>에 한 번만 선언적으로 붙여준다(예전에 항상 잘 되던 방식).
    # 여기서는 그게 준비될 때까지 window.kakao.maps.LatLng 존재 여부만 기다린다.
    ui.run_javascript(
        f"""
        (function() {{
            var keyword = {json.dumps(keyword)};
            var fullAddress = {json.dumps(location)};
            var knownAddress = {json.dumps(known_address)};
            var routeColor = {json.dumps(ACCENT)};
            var walkColor = "#16A34A";
            // 경로 선택 칩/요약 문구의 글자색 - 배경/테두리는 선택 상태를 보여주기 위해
            // routeColor(포인트 컬러)를 계속 쓰지만, 글자 자체는 가독성 때문에 검은 계열로
            // 바꿔달라는 피드백을 받아 텍스트 전용 색을 따로 둔다.
            var textColor = {json.dumps(INK)};

            // initMap()이 끝나야 채워지는 것들 - 그 전에 버튼이 눌리면 "아직 준비 중" 안내로 막는다.
            var map = null;
            var geocoder = null;
            var places = null;
            var destLatG = null;
            var destLngG = null;
            var myLocationOverlay = null;

            // "출발지에서 경로 보기"에 마지막으로 쓴 출발지 좌표 - 모드를 바꿔도(자동차 -> 대중교통
            // 등) 같은 출발지를 그대로 쓴다.
            var lastOriginLat = null;
            var lastOriginLng = null;

            // 모드별 상태 - 세 모드 중 항상 하나만(currentMode) 지도에 그려진다. 이미 불러온 데이터는
            // Polyline 객체/거리·시간 정보로 캐시해두고, 모드를 바꿀 때 재요청하지 않고 재사용한다.
            var currentMode = null; // null | 'car' | 'transit' | 'walk'

            var carLines = {{ RECOMMEND: null, TIME: null, DISTANCE: null }};
            var carPaths = {{ RECOMMEND: null, TIME: null, DISTANCE: null }};
            var carData  = {{ RECOMMEND: null, TIME: null, DISTANCE: null }};
            var carPending = {{ RECOMMEND: false, TIME: false, DISTANCE: false }};
            var carFailed  = {{ RECOMMEND: false, TIME: false, DISTANCE: false }};
            // 실패했을 때 보여줄 안내 문구 - priority별로 다르게(특히 RECOMMEND는 더 구체적인
            // 안내를 준다) 기억해뒀다가 패널에서 그대로 보여준다.
            var carErrorMsg = {{ RECOMMEND: '', TIME: '', DISTANCE: '' }};
            var carSelected = 'RECOMMEND';
            var carPriorityLabel = {{ RECOMMEND: '추천 경로', TIME: '최소시간', DISTANCE: '최단거리' }};

            // 카카오맵 API가 대중교통 경로를 여러 개(환승 조합이 다른 대안들) 내려줄 수 있어서,
            // 자동차 모드처럼 "여러 옵션 중에 선택" 방식으로 바꿨다. routes[]를 통째로 저장해두고,
            // 옵션별로 Polyline 배열을 따로 만들어서(transitLinesByRoute[i]) 선택된 옵션의
            // 배열만 지도에 보이게 한다.
            var transitRoutes = [];
            var transitLinesByRoute = [];
            var transitSelectedIndex = 0;
            var transitPending = false;
            var transitFailed = false;
            var transitFailMsg = '';

            var walkLine = null;
            var walkData = null;
            var walkPending = false;
            var walkFailed = false;
            var walkFailMsg = '';

            function showError(container, msg) {{
              container.innerHTML = "<p style='padding:16px;color:#c0392b;font-size:0.85rem;'>" + msg + "</p>";
            }}

            function escapeHtml(s) {{
              return String(s == null ? '' : s).replace(/[&<>"']/g, function(ch) {{
                return {{ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }}[ch];
              }});
            }}

            function setRouteInfo(text, visible, isError) {{
              var info = document.getElementById('kdt-route-info');
              if (!info) return;
              info.textContent = text || "";
              info.style.display = visible ? "block" : "none";
              info.style.color = isError ? "#c0392b" : routeColor;
              info.style.background = isError ? "#c0392b14" : (routeColor + "14");
            }}

            // 구글맵 스타일의 "내 위치" 파란 점 - 목적지 핀과 모양이 완전히 달라서
            // 지도 위에서 어느 게 내 위치고 어느 게 목적지인지 헷갈리지 않는다.
            // 다시 검색할 때마다 이전 점은 지우고 새로 찍는다. 모드를 바꿔도 출발지는 그대로라
            // 이 점은 지우지 않는다(모드별 clear 로직과 무관).
            function placeMyLocationDot(lat, lng) {{
              if (myLocationOverlay) {{
                myLocationOverlay.setMap(null);
              }}
              myLocationOverlay = new kakao.maps.CustomOverlay({{
                map: map,
                position: new kakao.maps.LatLng(lat, lng),
                content:
                  '<div style="width:16px;height:16px;border-radius:50%;' +
                  'background:#4285F4;border:3px solid #fff;' +
                  'box-shadow:0 0 0 2px #4285F4, 0 2px 6px rgba(0,0,0,0.35);"></div>',
                yAnchor: 0.5,
                xAnchor: 0.5,
                zIndex: 10
              }});
            }}

            function originDestPoints() {{
              var pts = [];
              if (lastOriginLat !== null) pts.push(new kakao.maps.LatLng(lastOriginLat, lastOriginLng));
              if (destLatG !== null) pts.push(new kakao.maps.LatLng(destLatG, destLngG));
              return pts;
            }}

            // NiceGUI처럼 지도 컨테이너 크기가 나중에 바뀌는(반응형 레이아웃, 패널 표시/숨김)
            // 환경에서는 카카오맵이 내부에 캐싱해둔 픽셀 크기가 실제 DOM 크기와 어긋나서
            // setBounds/좌표 계산이 엉뚱한 곳으로 튈 수 있다. relayout()으로 크기를 다시 맞춘
            // 다음 자동맞춤(setBounds)을 호출하면 해결된다.
            function fitBoundsToPath(path, extraPoints) {{
              if (!map || !path || path.length === 0) return;
              var bounds = new kakao.maps.LatLngBounds();
              path.forEach(function(p) {{ bounds.extend(p); }});
              (extraPoints || []).forEach(function(p) {{ bounds.extend(p); }});
              map.relayout();
              map.setBounds(bounds, 60, 60, 60, 60);
            }}

            function hideAllModeLines() {{
              ['RECOMMEND', 'TIME', 'DISTANCE'].forEach(function(p) {{
                if (carLines[p]) carLines[p].setMap(null);
              }});
              transitLinesByRoute.forEach(function(arr) {{ arr.forEach(function(line) {{ line.setMap(null); }}); }});
              if (walkLine) walkLine.setMap(null);
            }}

            // 검색 카드 목록에서 하나를 클릭하면(map_page.py의 유일한 선택 경로 - 자동 선택은
            // 없다) 목록이 그대로 남아있으면 화면이 복잡해 보인다는 피드백을 받아 바로 접는다.
            function hideCandidates() {{
              var box = document.getElementById('kdt-candidates');
              if (box) {{
                box.style.display = 'none';
                box.innerHTML = '';
              }}
            }}

            // ---------- 검색 후보 카드 (요청 #1) ----------
            function formatDistanceMeters(distanceStr) {{
              var meters = parseInt(distanceStr, 10);
              if (!meters || isNaN(meters)) return '';
              if (meters < 1000) return meters + 'm';
              return (meters / 1000).toFixed(1) + 'km';
            }}

            function categoryBadge(categoryName) {{
              if (!categoryName) return '';
              var parts = categoryName.split('>').map(function(s) {{ return s.trim(); }}).filter(Boolean);
              return parts.length ? parts[parts.length - 1] : '';
            }}

            // keywordSearch 결과를 카드 목록으로 보여준다 - 자동으로 아무 후보나 골라 바로
            // 경로를 그리지 않고, 사용자가 직접 카드를 클릭해야만 경로 계산이 시작된다.
            // 실제 카카오맵 앱 검색 결과처럼 이름/카테고리 배지/거리/주소를 함께 보여준다.
            // NiceGUI의 ui.html() 살균 처리를 거치지 않고(=onclick 안 씹힘) 여기서 직접
            // DOM을 만들고 addEventListener를 붙이는 순수 JS라 문제 없다.
            function renderCandidates(candidates) {{
              var box = document.getElementById('kdt-candidates');
              if (!box) return;
              if (!candidates || candidates.length === 0) {{
                box.style.display = 'none';
                box.innerHTML = '';
                return;
              }}
              var html = '<div style="font-size:0.75rem;font-weight:700;margin:6px 0 6px;color:' + routeColor + ';">검색 결과 - 원하는 위치를 골라주세요</div>';
              html += '<div style="display:flex;flex-direction:column;gap:6px;">';
              candidates.slice(0, 6).forEach(function(c, idx) {{
                var addr = c.road_address_name || c.address_name || '';
                var badge = categoryBadge(c.category_name);
                var distText = formatDistanceMeters(c.distance);
                html += '<button type="button" data-idx="' + idx + '" style="' +
                  'display:flex;flex-direction:column;align-items:flex-start;gap:3px;text-align:left;' +
                  'border:1px solid ' + routeColor + '33;background:#fff;border-radius:12px;' +
                  'padding:9px 12px;cursor:pointer;width:100%;">' +
                  '<div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;width:100%;">' +
                  '<span style="font-size:0.85rem;font-weight:800;color:#191919;">' + escapeHtml(c.place_name || '이름 없음') + '</span>' +
                  (badge ? '<span style="font-size:0.65rem;font-weight:700;color:' + routeColor + ';background:' + routeColor + '14;border-radius:999px;padding:2px 8px;">' + escapeHtml(badge) + '</span>' : '') +
                  (distText ? '<span style="font-size:0.7rem;font-weight:700;color:#6B7280;margin-left:auto;">' + distText + '</span>' : '') +
                  '</div>' +
                  (addr ? '<div style="font-size:0.72rem;color:#6B7280;">' + escapeHtml(addr) + '</div>' : '') +
                  '</button>';
              }});
              html += '</div>';
              box.innerHTML = html;
              box.style.display = 'block';
              box.querySelectorAll('button[data-idx]').forEach(function(btn) {{
                btn.addEventListener('click', function() {{
                  var c = candidates[parseInt(btn.getAttribute('data-idx'), 10)];
                  // 직접 골랐다는 건 의사가 분명한 행동이니 클릭 즉시 목록을 접는다. 이
                  // 후보로 도로 경로를 못 찾으면(no_route) 목록을 다시 보여줘서 다른 후보를
                  // 고를 수 있게 한다 - 완전히 처음부터 다시 검색하지 않아도 되게.
                  hideCandidates();
                  loadRoutesForOrigin(parseFloat(c.y), parseFloat(c.x), function() {{
                    renderCandidates(candidates);
                  }});
                }});
              }});
            }}

            // ---------- 우측 경로 옵션 패널 + 모드 버튼 + 자동차 대안 선택 ----------
            // 자동차/대중교통/도보 버튼은 각 모드가 지도에 그려질 때 쓰는 색(routeColor/파랑/초록)을
            // 그대로 써서, 버튼 색만 봐도 지금 어떤 색 경로가 그려질지 바로 연상되게 한다.
            var modeColors = {{ car: routeColor, transit: '#2563EB', walk: walkColor }};

            function modeButtonHtml(mode, label) {{
              var active = currentMode === mode;
              var c = modeColors[mode];
              return '<button type="button" data-mode="' + mode + '" style="' +
                'flex:1;padding:11px 6px;border-radius:10px;font-size:0.92rem;font-weight:800;cursor:pointer;' +
                'border:1.5px solid ' + (active ? c : c + '40') + ';' +
                'background:' + (active ? c : '#fff') + ';' +
                'color:' + (active ? '#fff' : c) + ';">' + label + '</button>';
            }}

            function priorityChipHtml(priority) {{
              var selected = carSelected === priority;
              var text = carPriorityLabel[priority];
              var d = carData[priority];
              if (d && d.distance_m != null) {{
                var km = (d.distance_m / 1000).toFixed(1);
                var min = Math.round((d.duration_s || 0) / 60);
                text += ' · ' + km + 'km · ' + min + '분';
              }} else if (carPending[priority]) {{
                text += ' · 불러오는 중...';
              }} else if (carFailed[priority]) {{
                text += ' · 경로 없음';
              }}
              return '<button type="button" data-priority="' + priority + '" style="' +
                'display:block;width:100%;text-align:left;margin-bottom:6px;padding:8px 10px;' +
                'border-radius:10px;font-size:0.75rem;font-weight:700;cursor:pointer;' +
                'border:1px solid ' + (selected ? routeColor : routeColor + '33') + ';' +
                'background:' + (selected ? routeColor + '14' : '#fff') + ';color:' + textColor + ';">' +
                escapeHtml(text) + '</button>';
            }}

            function renderSidePanel() {{
              var panel = document.getElementById('kdt-side-panel');
              if (!panel) return;
              if (!currentMode) {{
                panel.style.display = 'none';
                panel.innerHTML = '';
                return;
              }}
              panel.style.display = 'block';

              var html = '<div style="display:flex;gap:4px;margin-bottom:10px;">';
              html += modeButtonHtml('car', '자동차');
              html += modeButtonHtml('transit', '대중교통');
              html += modeButtonHtml('walk', '도보');
              html += '</div>';

              if (currentMode === 'car') {{
                // 예전엔 이 요약 문구(거리·시간)가 지도 아래 별도 박스에 나왔는데, 경로 선택
                // 패널이 그것만으로는 너무 비어 보인다는 피드백을 받아 패널 안으로 옮겼다.
                // 글자 크기도 처음엔 작았는데("도보 약 32.7km" 같은 문구가 잘 안 보인다는
                // 피드백) 요약 문구는 패널에서 가장 눈에 띄어야 하는 정보라 1rem으로 키웠다.
                var selData = carData[carSelected];
                if (selData && selData.distance_m != null) {{
                  var selKm = (selData.distance_m / 1000).toFixed(1);
                  var selMin = Math.round((selData.duration_s || 0) / 60);
                  html += '<div style="font-size:1rem;font-weight:800;color:' + textColor + ';margin-bottom:3px;">입력하신 위치에서 약 ' + selKm + 'km · ' + selMin + '분</div>';
                  html += '<div style="font-size:0.74rem;color:#6B7280;margin-bottom:14px;">교통상황에 따라 달라질 수 있어요</div>';
                }} else if (carFailed[carSelected]) {{
                  html += '<div style="font-size:0.85rem;font-weight:700;color:#c0392b;margin-bottom:14px;">' + escapeHtml(carErrorMsg[carSelected] || '경로를 찾을 수 없습니다.') + '</div>';
                }} else {{
                  html += '<div style="font-size:0.85rem;color:#6B7280;margin-bottom:14px;">경로 계산 중...</div>';
                }}
                html += '<div style="font-size:0.75rem;font-weight:700;color:#6B7280;margin-bottom:6px;">경로 선택</div>';
                html += priorityChipHtml('RECOMMEND');
                html += priorityChipHtml('TIME');
                html += priorityChipHtml('DISTANCE');
              }} else if (currentMode === 'transit') {{
                if (transitPending) {{
                  html += '<div style="font-size:0.85rem;color:#6B7280;">대중교통 경로 찾는 중...</div>';
                }} else if (transitFailed) {{
                  html += '<div style="font-size:0.85rem;color:#c0392b;">' + escapeHtml(transitFailMsg || '대중교통 경로를 찾을 수 없습니다.') + '</div>';
                }} else if (transitRoutes.length > 0) {{
                  // 카카오맵 앱처럼 대중교통도 여러 경로 후보 중 하나를 고를 수 있게 - 각 옵션을
                  // "N분 · 환승 M회" 칩으로 보여주고, 고른 옵션의 상세(요금/구간)만 아래에 펼친다.
                  html += '<div style="font-size:0.75rem;font-weight:700;color:#6B7280;margin-bottom:6px;">경로 선택</div>';
                  transitRoutes.forEach(function(route, idx) {{
                    var selected = idx === transitSelectedIndex;
                    var rMin = Math.round((route.duration_s || 0) / 60);
                    var rLabel = '경로 ' + (idx + 1) + ' · ' + rMin + '분 · 환승 ' + (route.transfers || 0) + '회';
                    html += '<button type="button" data-transit-idx="' + idx + '" style="' +
                      'display:block;width:100%;text-align:left;margin-bottom:6px;padding:8px 10px;' +
                      'border-radius:10px;font-size:0.8rem;font-weight:700;cursor:pointer;' +
                      'border:1px solid ' + (selected ? routeColor : routeColor + '33') + ';' +
                      'background:' + (selected ? routeColor + '14' : '#fff') + ';color:' + textColor + ';">' +
                      escapeHtml(rLabel) + '</button>';
                  }});

                  var route = transitRoutes[transitSelectedIndex];
                  var km = ((route.distance_m || 0) / 1000).toFixed(1);
                  var totalMin = Math.round((route.duration_s || 0) / 60);
                  var fareText = route.fare != null ? ' · 약 ' + route.fare.toLocaleString() + '원' : '';
                  html += '<div style="font-size:1rem;font-weight:800;color:' + textColor + ';margin:10px 0 8px;">' +
                    km + 'km · ' + totalMin + '분 · 환승 ' + (route.transfers || 0) + '회' + fareText + '</div>';
                  (route.steps || []).forEach(function(step) {{
                    var stColor = step.is_transit ? '#2563EB' : '#9CA3AF';
                    var min = Math.round((step.duration_s || 0) / 60);
                    var label = step.is_transit
                      ? (((step.vehicle_type || '') + ' ' + (step.vehicle_name || '')).trim() || '대중교통')
                      : '도보';
                    html += '<div style="display:flex;align-items:center;gap:6px;padding:4px 0;font-size:0.78rem;">' +
                      '<span style="width:8px;height:8px;border-radius:50%;background:' + stColor + ';flex:0 0 auto;"></span>' +
                      '<span style="font-weight:700;">' + escapeHtml(label) + '</span>' +
                      (min > 0 ? '<span style="color:#6B7280;">' + min + '분</span>' : '') +
                      '</div>';
                  }});
                }} else {{
                  html += '<div style="font-size:0.85rem;color:#6B7280;">대중교통 경로를 불러오는 중입니다...</div>';
                }}
              }} else if (currentMode === 'walk') {{
                if (walkPending) {{
                  html += '<div style="font-size:0.85rem;color:#6B7280;">도보 경로 찾는 중...</div>';
                }} else if (walkFailed) {{
                  html += '<div style="font-size:0.85rem;color:#c0392b;">' + escapeHtml(walkFailMsg || '도보 경로를 찾을 수 없습니다.') + '</div>';
                }} else if (walkData) {{
                  var wkm = ((walkData.distance_m || 0) / 1000).toFixed(1);
                  var wmin = Math.round((walkData.duration_s || 0) / 60);
                  html += '<div style="font-size:1rem;font-weight:800;color:' + walkColor + ';">도보 약 ' + wkm + 'km · ' + wmin + '분</div>';
                }} else {{
                  html += '<div style="font-size:0.85rem;color:#6B7280;">도보 경로를 불러오는 중입니다...</div>';
                }}
              }}

              panel.innerHTML = html;
              panel.querySelectorAll('button[data-mode]').forEach(function(btn) {{
                btn.addEventListener('click', function() {{ switchMode(btn.getAttribute('data-mode')); }});
              }});
              panel.querySelectorAll('button[data-priority]').forEach(function(btn) {{
                btn.addEventListener('click', function() {{ selectCarPriority(btn.getAttribute('data-priority')); }});
              }});
              panel.querySelectorAll('button[data-transit-idx]').forEach(function(btn) {{
                btn.addEventListener('click', function() {{ selectTransitRoute(parseInt(btn.getAttribute('data-transit-idx'), 10)); }});
              }});
            }}

            function selectCarPriority(priority) {{
              if (currentMode !== 'car' || carSelected === priority) return;
              if (carLines[carSelected]) carLines[carSelected].setMap(null);
              carSelected = priority;
              if (carLines[priority]) {{
                carLines[priority].setMap(map);
                fitBoundsToPath(carPaths[priority], originDestPoints());
              }}
              renderSidePanel();
            }}

            // 대중교통 경로 후보(transitRoutes) 중 하나를 고르면, 그 후보의 Polyline만 지도에
            // 남기고 나머지 후보들은 숨긴다 - 이미 다 그려서 캐시해뒀기 때문에 재요청 없이
            // 즉시 전환된다.
            function selectTransitRoute(idx) {{
              if (currentMode !== 'transit' || idx === transitSelectedIndex || !transitLinesByRoute[idx]) return;
              (transitLinesByRoute[transitSelectedIndex] || []).forEach(function(line) {{ line.setMap(null); }});
              transitSelectedIndex = idx;
              var pts = [];
              transitLinesByRoute[idx].forEach(function(line) {{
                line.setMap(map);
                pts = pts.concat(line.getPath());
              }});
              if (pts.length > 0) fitBoundsToPath(pts, originDestPoints());
              renderSidePanel();
            }}

            // 메인 경로(추천 기준) 조회에 성공한 뒤, 다른 두 기준(최소시간/최단거리)은
            // 백그라운드로 미리 불러온다. 화면에는 안 그리고(선택되기 전까지 setMap(null)),
            // 패널에 거리/시간 정보만 채워서 사용자가 칩을 누르는 즉시 바로 보여줄 수 있게 한다.
            // 실패해도 메인 경로 표시에는 전혀 영향이 없다.
            function fetchCarPriorityBackground(priority, originLat, originLng) {{
              carPending[priority] = true;
              if (currentMode === 'car') renderSidePanel();
              var originParam = originLng + "," + originLat;
              var destParam = destLngG + "," + destLatG;
              var url = "/api/directions?origin=" + encodeURIComponent(originParam)
                      + "&destination=" + encodeURIComponent(destParam)
                      + "&priority=" + priority;
              fetch(url).then(function(res) {{ return res.ok ? res.json() : null; }}).then(function(data) {{
                carPending[priority] = false;
                if (!data || !data.path || data.path.length === 0) {{
                  carFailed[priority] = true;
                  carErrorMsg[priority] = "이 기준으로는 경로를 찾을 수 없습니다.";
                  if (currentMode === 'car') renderSidePanel();
                  return;
                }}
                var linePath = data.path.map(function(p) {{ return new kakao.maps.LatLng(p[1], p[0]); }});
                carLines[priority] = new kakao.maps.Polyline({{
                  map: (currentMode === 'car' && carSelected === priority) ? map : null,
                  path: linePath,
                  strokeWeight: 5,
                  strokeColor: routeColor,
                  strokeOpacity: 0.85,
                  strokeStyle: "solid"
                }});
                carPaths[priority] = linePath;
                carData[priority] = {{ distance_m: data.distance_m, duration_s: data.duration_s }};
                if (currentMode === 'car') renderSidePanel();
              }}).catch(function() {{
                carPending[priority] = false;
                carFailed[priority] = true;
                carErrorMsg[priority] = "이 기준으로는 경로를 찾을 수 없습니다.";
                if (currentMode === 'car') renderSidePanel();
              }});
            }}

            // 출발지 좌표가 정해지면(후보 카드 클릭, 주소 검색 성공, 위치 자동감지) 여기서 새
            // 경로 조회를 시작한다. 완전히 새로운 출발지 검색이므로 이전 세 모드의 결과를 모두
            // 초기화하고 자동차 모드부터 다시 시작한다. onFail이 주어지면(=후보 카드를 클릭한
            // 경우) "경로 자체를 못 찾음"(no_route) 실패 시 바로 에러 메시지만 띄우지 않고
            // onFail을 불러서 다른 후보를 다시 고를 수 있게 한다.
            function loadRoutesForOrigin(originLat, originLng, onFail) {{
              if (!map || destLatG === null) {{
                setRouteInfo("지도가 아직 준비 중입니다. 잠시 후 다시 시도해주세요.", true, true);
                return;
              }}

              lastOriginLat = originLat;
              lastOriginLng = originLng;

              hideAllModeLines();
              ['RECOMMEND', 'TIME', 'DISTANCE'].forEach(function(p) {{
                carLines[p] = null; carPaths[p] = null; carData[p] = null;
                carPending[p] = false; carFailed[p] = false;
              }});
              transitRoutes = []; transitLinesByRoute = []; transitSelectedIndex = 0;
              transitPending = false; transitFailed = false; transitFailMsg = '';
              walkLine = null; walkData = null; walkPending = false; walkFailed = false; walkFailMsg = '';
              carSelected = 'RECOMMEND';
              currentMode = 'car';

              placeMyLocationDot(originLat, originLng);
              // 로딩/거리/에러 안내는 이제 지도 아래가 아니라 우측 패널 쪽에서 보여준다
              // (currentMode가 이미 'car'이므로 renderSidePanel()이 "경로 계산 중..."을 그려준다).
              setRouteInfo("", false, false);
              renderSidePanel();

              var originParam = originLng + "," + originLat;
              var destParam = destLngG + "," + destLatG;
              var url = "/api/directions?origin=" + encodeURIComponent(originParam)
                      + "&destination=" + encodeURIComponent(destParam)
                      + "&priority=RECOMMEND";

              carPending.RECOMMEND = true;
              fetch(url).then(function(res) {{
                return res.json().then(function(body) {{
                  if (!res.ok) {{
                    var err = new Error("directions request failed");
                    err.body = body;
                    throw err;
                  }}
                  return body;
                }});
              }}).then(function(data) {{
                carPending.RECOMMEND = false;
                if (!data.path || data.path.length === 0) {{
                  if (onFail) {{ onFail(); return; }}
                  carFailed.RECOMMEND = true;
                  carErrorMsg.RECOMMEND = "경로를 찾을 수 없습니다. 길찾기 버튼으로 이용해주세요.";
                  renderSidePanel();
                  return;
                }}

                var linePath = data.path.map(function(p) {{ return new kakao.maps.LatLng(p[1], p[0]); }});
                carLines.RECOMMEND = new kakao.maps.Polyline({{
                  map: map,
                  path: linePath,
                  strokeWeight: 5,
                  strokeColor: routeColor,
                  strokeOpacity: 0.85,
                  strokeStyle: "solid"
                }});
                carPaths.RECOMMEND = linePath;
                carData.RECOMMEND = {{ distance_m: data.distance_m, duration_s: data.duration_s }};

                fitBoundsToPath(linePath, originDestPoints());
                // 후보 카드를 클릭한 경우 이미 클릭 시점에 hideCandidates()가 실행됐으니
                // 여기서는 아무 효과가 없다(멱등) - 혹시 모를 다른 진입 경로를 위한 안전망.
                hideCandidates();
                renderSidePanel();

                fetchCarPriorityBackground('TIME', originLat, originLng);
                fetchCarPriorityBackground('DISTANCE', originLat, originLng);
              }}).catch(function(err) {{
                carPending.RECOMMEND = false;
                var detail = err && err.body && err.body.detail;
                var isNoRoute = detail && typeof detail === "object" && detail.reason === "no_route";
                if (isNoRoute && onFail) {{
                  onFail();
                  return;
                }}
                carFailed.RECOMMEND = true;
                carErrorMsg.RECOMMEND = isNoRoute
                  ? "이 출발지 주변에서 차로 갈 수 있는 경로를 찾지 못했어요. 더 구체적인 위치(예: 정확한 출입구, 인근 도로명)로 다시 입력해보시거나, 길찾기 버튼을 이용해주세요."
                  : "경로를 불러오지 못했습니다. 카카오맵 앱으로 길찾기 버튼을 이용해주세요.";
                renderSidePanel();
              }});
            }}

            // "내 위치 자동으로 사용" 버튼 전용 - 사용자가 명시적으로 눌렀을 때만 위치 권한을 요청한다.
            window.kdtRouteFromGeolocation = function() {{
              if (!navigator.geolocation) {{
                setRouteInfo("이 브라우저는 위치 감지를 지원하지 않습니다. 출발지를 직접 입력해주세요.", true, true);
                return;
              }}
              setRouteInfo("내 위치 확인 중...", true, false);
              navigator.geolocation.getCurrentPosition(function(pos) {{
                loadRoutesForOrigin(pos.coords.latitude, pos.coords.longitude);
              }}, function() {{
                setRouteInfo("위치 권한이 거부됐거나 가져오지 못했습니다. 출발지를 직접 입력해주세요.", true, true);
              }}, {{ timeout: 8000 }});
            }};

            // 출발지 텍스트 입력 - keywordSearch(POI) 먼저, 실패하면 주소 검색으로 폴백.
            // 목적지 좌표가 이미 잡혀있으면(destLatG/destLngG) 그 위치를 기준 좌표로 넘겨서
            // 카카오가 각 후보의 목적지까지의 거리(distance)를 같이 내려주게 한다(검색 카드에 표시).
            window.kdtRouteFromText = function(text) {{
              if (!map || !places || !geocoder) {{
                setRouteInfo("지도가 아직 준비 중입니다. 잠시 후 다시 시도해주세요.", true, true);
                return;
              }}
              setRouteInfo("\\"" + text + "\\" 위치 찾는 중...", true, false);

              var searchOptions = (destLatG !== null && destLngG !== null)
                ? {{ location: new kakao.maps.LatLng(destLatG, destLngG) }}
                : undefined;

              places.keywordSearch(text, function(data, status) {{
                if (status === kakao.maps.services.Status.OK && data.length > 0) {{
                  // 여러 후보가 나올 수 있는 검색어(예: "동대구역"의 역 본체/1호선/대경선/
                  // 주차장 등)라서, 카카오가 1등으로 준 결과를 바로 경로에 쓰지 않고 후보
                  // 카드로 보여준 뒤 사용자가 직접 하나를 클릭해야만 경로를 계산한다 - 자동으로
                  // 아무 후보나 골라서 바로 경로를 그리면 사용자가 원치 않는 위치로 경로가
                  // 잡히는 경우가 많다는 피드백을 받아 자동 선택 로직을 없앴다.
                  setRouteInfo("", false, false);
                  renderCandidates(data);
                  return;
                }}
                renderCandidates([]);
                geocoder.addressSearch(text, function(result, gStatus) {{
                  if (gStatus === kakao.maps.services.Status.OK) {{
                    loadRoutesForOrigin(parseFloat(result[0].y), parseFloat(result[0].x));
                  }} else {{
                    setRouteInfo(
                      "입력하신 위치를 찾지 못했습니다. 더 구체적으로 입력해보세요 (예: 'OO역', 'OO구 OO동').",
                      true, true
                    );
                  }}
                }});
              }}, searchOptions);
            }};

            // ---------- 대중교통 모드 ----------
            // 도보/탑승 두 가지로만 색을 나눈다 - 카카오 공식 문서가 vehicles[].type을
            // "BUS"/"SUBWAY"라고 적어놓은 스키마 표와, 실제로 "마을"(한국어 버스 서브타입)을
            // 보여주는 샘플 응답이 서로 안 맞아서, 그 값으로 버스/지하철 색을 따로 나누면
            // 잘못 분류될 위험이 크다(예: 전부 도보 취급). 대신 백엔드(directions.py)가 내려주는
            // is_transit(그 구간에 vehicles가 있었는지)만 신뢰하고, 실제 버스/지하철 이름은
            // 패널에 라벨 텍스트로 정확히 보여준다.
            var transitStepStyle = {{
              WALK:    {{ color: "#9CA3AF", weight: 4, style: "shortdot" }},
              TRANSIT: {{ color: "#2563EB", weight: 5, style: "solid" }}
            }};

            function loadTransit() {{
              transitPending = true;
              transitFailed = false;
              renderSidePanel();

              var originParam = lastOriginLng + "," + lastOriginLat;
              var destParam = destLngG + "," + destLatG;
              var url = "/api/transit?origin=" + encodeURIComponent(originParam)
                      + "&destination=" + encodeURIComponent(destParam);

              fetch(url).then(function(res) {{
                return res.json().then(function(body) {{
                  if (!res.ok) {{
                    var err = new Error("transit request failed");
                    err.body = body;
                    throw err;
                  }}
                  return body;
                }});
              }}).then(function(data) {{
                transitPending = false;
                // 카카오가 환승 조합이 다른 대안을 꽤 많이(때로는 10개 이상) 내려줄 수 있는데,
                // 그만큼 다 보여주면 고르기 오히려 번거롭다는 피드백을 받아 상위 3개까지만 쓴다.
                var routes = (data.routes || []).slice(0, 3);
                if (routes.length === 0) {{
                  transitFailed = true;
                  transitFailMsg = "대중교통 경로를 찾을 수 없습니다.";
                  renderSidePanel();
                  return;
                }}

                // 카카오맵 API가 환승 조합이 다른 대안 경로를 여러 개 내려줄 수 있어서, 모두
                // 미리 그려두고(화면에는 첫 번째만 보이게) 사용자가 패널에서 고르면 즉시
                // 전환되게 한다 - 재요청 없이 setMap()만 토글.
                transitLinesByRoute = routes.map(function(route, idx) {{
                  return (route.steps || []).reduce(function(arr, step) {{
                    var style = step.is_transit ? transitStepStyle.TRANSIT : transitStepStyle.WALK;
                    var path = (step.path || []).map(function(p) {{ return new kakao.maps.LatLng(p[1], p[0]); }});
                    if (path.length > 1) {{
                      arr.push(new kakao.maps.Polyline({{
                        map: (currentMode === 'transit' && idx === 0) ? map : null,
                        path: path,
                        strokeWeight: style.weight,
                        strokeColor: style.color,
                        strokeOpacity: 0.85,
                        strokeStyle: style.style
                      }}));
                    }}
                    return arr;
                  }}, []);
                }});
                transitRoutes = routes;
                transitSelectedIndex = 0;

                if (currentMode === 'transit') {{
                  var boundsPts = [];
                  transitLinesByRoute[0].forEach(function(line) {{ boundsPts = boundsPts.concat(line.getPath()); }});
                  if (boundsPts.length > 0) fitBoundsToPath(boundsPts, originDestPoints());
                }}
                renderSidePanel();
              }}).catch(function(err) {{
                transitPending = false;
                transitFailed = true;
                var detail = err && err.body && err.body.detail;
                transitFailMsg = (detail && typeof detail === "object") ? (detail.result_msg || "대중교통 경로를 불러오지 못했습니다.")
                  : (typeof detail === "string" ? detail : "대중교통 경로를 불러오지 못했습니다.");
                renderSidePanel();
              }});
            }}

            // ---------- 도보 모드 ----------
            function loadWalk() {{
              walkPending = true;
              walkFailed = false;
              renderSidePanel();

              var originParam = lastOriginLng + "," + lastOriginLat;
              var destParam = destLngG + "," + destLatG;
              var url = "/api/walking?origin=" + encodeURIComponent(originParam)
                      + "&destination=" + encodeURIComponent(destParam);

              fetch(url).then(function(res) {{
                return res.json().then(function(body) {{
                  if (!res.ok) {{
                    var err = new Error("walking request failed");
                    err.body = body;
                    throw err;
                  }}
                  return body;
                }});
              }}).then(function(data) {{
                walkPending = false;
                if (!data.path || data.path.length === 0) {{
                  walkFailed = true;
                  walkFailMsg = "도보 경로를 찾을 수 없습니다.";
                  renderSidePanel();
                  return;
                }}
                var linePath = data.path.map(function(p) {{ return new kakao.maps.LatLng(p[1], p[0]); }});
                if (walkLine) walkLine.setMap(null);
                walkLine = new kakao.maps.Polyline({{
                  map: currentMode === 'walk' ? map : null,
                  path: linePath,
                  strokeWeight: 5,
                  strokeColor: walkColor,
                  strokeOpacity: 0.85,
                  strokeStyle: "shortdot"
                }});
                walkData = {{ distance_m: data.distance_m, duration_s: data.duration_s }};
                if (currentMode === 'walk') {{
                  fitBoundsToPath(linePath, originDestPoints());
                }}
                renderSidePanel();
              }}).catch(function(err) {{
                walkPending = false;
                walkFailed = true;
                var detail = err && err.body && err.body.detail;
                walkFailMsg = (detail && typeof detail === "object") ? (detail.result_msg || "도보 경로를 불러오지 못했습니다.")
                  : (typeof detail === "string" ? detail : "도보 경로를 불러오지 못했습니다.");
                renderSidePanel();
              }});
            }}

            // 세 모드 버튼(자동차/대중교통/도보) 공용 전환 함수. 이미 불러온 모드는 재요청 없이
            // 캐시된 Polyline만 다시 보여주고, 처음 보는 모드면 그때 API를 호출한다.
            function switchMode(mode) {{
              if (lastOriginLat === null || destLatG === null) {{
                setRouteInfo("먼저 출발지를 입력해서 경로를 한 번 찾아주세요.", true, true);
                return;
              }}
              if (mode === currentMode) return;

              hideAllModeLines();
              currentMode = mode;
              // 로딩/거리/에러 안내는 패널이 currentMode/carSelected 상태를 보고 그려주므로
              // 지도 아래 박스는 모드를 바꿀 때마다 비워둔다.
              setRouteInfo("", false, false);

              if (mode === 'car') {{
                if (carLines[carSelected]) {{
                  carLines[carSelected].setMap(map);
                  fitBoundsToPath(carPaths[carSelected], originDestPoints());
                }}
              }} else if (mode === 'transit') {{
                if (transitRoutes.length > 0) {{
                  var pts = [];
                  (transitLinesByRoute[transitSelectedIndex] || []).forEach(function(line) {{
                    line.setMap(map);
                    pts = pts.concat(line.getPath());
                  }});
                  if (pts.length > 0) fitBoundsToPath(pts, originDestPoints());
                }} else if (!transitPending) {{
                  loadTransit();
                }}
              }} else if (mode === 'walk') {{
                if (walkLine) {{
                  walkLine.setMap(map);
                  fitBoundsToPath(walkLine.getPath(), originDestPoints());
                }} else if (!walkPending) {{
                  loadWalk();
                }}
              }}

              renderSidePanel();
            }}

            // 기존 "대중교통으로 보기" 버튼과의 호환을 위한 얇은 래퍼 - switchMode('transit')로
            // 그대로 연결한다(버튼 자체는 그대로 두되, 동작은 새 모드 전환 로직을 탄다).
            window.kdtShowTransit = function() {{
              switchMode('transit');
            }};

            // 두 가지가 다 준비돼야 지도를 만들 수 있다:
            // 1) #kdt-map DOM - NiceGUI가 클라이언트에서 Vue로 그리는 요소라 이 스크립트가
            //    실행되는 시점엔 아직 없거나, 있어도 "실제 화면 크기(레이아웃)"는 아직 0일 수
            //    있다(태그만 막 들어간 직후). 크기가 0인 채로 지도를 만들면 카카오맵이 크기를
            //    0으로 기억해버려서 지도가 확 축소된 화면(한국 전체~일본까지 보이는 수준)으로
            //    나온다.
            // 2) 카카오맵 SDK(window.kakao.maps.LatLng) - root_page()의 <head> 스크립트가
            //    비동기로 로드/초기화되는 중이라, 우리 스크립트가 그보다 먼저 실행됐을 수 있다.
            // 그래서 둘 다 실제로 준비될 때까지 잠깐씩(최대 10초) 재시도한다.
            function waitUntilReady(retriesLeft) {{
              var container = document.getElementById('kdt-map');
              var containerReady = container && container.offsetWidth > 0 && container.offsetHeight > 0;
              var sdkReady = window.kakao && window.kakao.maps && window.kakao.maps.LatLng;
              if (!containerReady || !sdkReady) {{
                if (retriesLeft > 0) {{
                  setTimeout(function() {{ waitUntilReady(retriesLeft - 1); }}, 100);
                  return;
                }}
                // 10초 넘게 기다렸는데도 준비가 안 되면(느린 네트워크, SDK 로드 실패 등) 아무
                // 설명 없이 빈 화면으로 남기지 말고, 최소한 원인과 대안을 알려준다.
                var reason = !sdkReady
                  ? "카카오맵 스크립트를 불러오지 못했습니다 (네트워크 차단 또는 잘못된 키)."
                  : "지도를 불러오는 데 시간이 오래 걸리고 있습니다.";
                setRouteInfo(reason + " 새로고침하거나 길찾기 버튼을 이용해주세요.", true, true);
                return;
              }}
              initMap(container);
            }}

            function initMap(container) {{
              if (typeof kakao === 'undefined' || !kakao.maps) {{
                showError(container, "카카오맵 SDK를 불러오지 못했습니다. Kakao Developers 콘솔에 이 사이트 도메인이 등록되어 있는지 확인해주세요. 길찾기 버튼으로 이용해주세요.");
                return;
              }}

              try {{
                var center = new kakao.maps.LatLng(35.8714, 128.6014);
                map = new kakao.maps.Map(container, {{ center: center, level: 4 }});

                // waitUntilReady에서 크기를 확인하고 들어왔어도, 이후에 사이드 패널 표시/숨김,
                // 창 크기 변경, 폰트 로딩 등으로 컨테이너 크기가 또 바뀔 수 있다. 그때마다
                // 자동으로 relayout해서 카카오맵이 기억하는 크기가 항상 실제 화면과 맞도록
                // 감시해둔다 (구형 브라우저 대비 ResizeObserver 미지원 시 window resize로 대체).
                if (typeof ResizeObserver !== 'undefined') {{
                  new ResizeObserver(function() {{
                    if (map) map.relayout();
                  }}).observe(container);
                }} else {{
                  window.addEventListener('resize', function() {{
                    if (map) map.relayout();
                  }});
                }}

                // 목적지 핀을 기본 카카오 마커 대신 브랜드 컬러로 - "내 위치" 파란 점과
                // 시각적으로 확실히 구분되게 한다.
                var pinSvg = 'data:image/svg+xml;charset=UTF-8,' + encodeURIComponent(
                  '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="40" viewBox="0 0 32 40">' +
                  '<path d="M16 0C7.163 0 0 7.163 0 16c0 12 16 24 16 24s16-12 16-24C32 7.163 24.837 0 16 0z" fill="' + routeColor + '"/>' +
                  '<circle cx="16" cy="15" r="6.5" fill="#fff"/>' +
                  '</svg>'
                );
                var pinImage = new kakao.maps.MarkerImage(
                  pinSvg, new kakao.maps.Size(32, 40), {{ offset: new kakao.maps.Point(16, 40) }}
                );

                function placeMarker(y, x, label) {{
                  var coords = new kakao.maps.LatLng(y, x);
                  new kakao.maps.Marker({{ map: map, position: coords, image: pinImage, title: label }});
                  // 지도 생성 시점엔 NiceGUI(Vue)가 아직 컨테이너 최종 크기를 확정하기 전일 수
                  // 있어서, 첫 마커를 찍을 때도 relayout으로 크기를 다시 맞춘 뒤 중심을 잡는다.
                  map.relayout();
                  map.setCenter(coords);
                  var link = document.getElementById('kdt-route-link');
                  if (link) {{
                    link.href = "https://map.kakao.com/link/to/" + encodeURIComponent(label) + "," + y + "," + x;
                  }}
                  // 카카오 API가 좌표를 문자열로 주는 경우가 있어서, 이후 숫자 연산(중간점 계산 등)에서
                  // "문자열 이어붙이기"로 잘못 처리돼 NaN이 나오지 않도록 여기서 숫자로 확정해둔다.
                  destLatG = parseFloat(y);
                  destLngG = parseFloat(x);
                }}

                geocoder = new kakao.maps.services.Geocoder();
                places = new kakao.maps.services.Places();

                function geocodeAddress(address, label, onFail) {{
                  geocoder.addressSearch(address, function(result, gStatus) {{
                    if (gStatus === kakao.maps.services.Status.OK) {{
                      placeMarker(result[0].y, result[0].x, label);
                    }} else {{
                      onFail();
                    }}
                  }});
                }}

                function finalFallback() {{
                  geocodeAddress(fullAddress, fullAddress, function() {{
                    showError(container, "지도를 표시할 수 없습니다 (장소를 찾지 못했어요). 길찾기 버튼으로 검색해주세요.");
                  }});
                }}

                places.keywordSearch(keyword, function(data, status) {{
                  if (status === kakao.maps.services.Status.OK && data.length > 0) {{
                    placeMarker(data[0].y, data[0].x, keyword);
                    return;
                  }}
                  // 대학 내부 교육관처럼 keywordSearch(POI 검색)로는 안 잡히는 건물은,
                  // 등록해둔 실제 도로명주소로 한 번 더 시도한다 (있으면 거의 항상 성공).
                  if (knownAddress) {{
                    geocodeAddress(knownAddress, knownAddress, finalFallback);
                  }} else {{
                    finalFallback();
                  }}
                }}, {{ location: center, radius: 20000 }});
              }} catch (err) {{
                showError(container, "지도를 불러오는 중 오류가 발생했습니다 (" + err.message + "). 길찾기 버튼으로 이용해주세요.");
              }}
            }}

            waitUntilReady(100);
          }})();
        """
    )
