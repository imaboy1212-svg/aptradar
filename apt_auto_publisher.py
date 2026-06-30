import os
import re
import time
import base64
import requests
import anthropic
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# .env 파일 로드: 프로젝트 폴더 우선, 없으면 홈 디렉토리 폴백
for _env_path in [
    os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"),
    os.path.expanduser("~/.env"),
]:
    if os.path.exists(_env_path):
        with open(_env_path, encoding="utf-8") as _f:
            for _line in _f:
                _line = _line.strip()
                if _line and not _line.startswith("#") and "=" in _line:
                    _k, _v = _line.split("=", 1)
                    os.environ.setdefault(_k.strip(), _v.strip())
        break

# ==========================================
# 1. 필수 설정 (GitHub Secrets 또는 .env)
# ==========================================
ANTHROPIC_API_KEY   = os.environ.get("ANTHROPIC_API_KEY")
APT_WP_SITE_URL     = os.environ.get("APT_WP_SITE_URL", "https://apt.bestwellth.org")
APT_WP_USERNAME     = os.environ.get("APT_WP_USERNAME")
APT_WP_APP_PASSWORD = os.environ.get("APT_WP_APP_PASSWORD")
PUBLIC_DATA_API_KEY_APT   = os.environ.get("PUBLIC_DATA_API_KEY_APT")
PUBLIC_DATA_API_KEY_SCORE = os.environ.get("PUBLIC_DATA_API_KEY_SCORE")
TELEGRAM_BOT_TOKEN  = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID    = os.environ.get("TELEGRAM_CHAT_ID")

for key, val in [
    ("ANTHROPIC_API_KEY", ANTHROPIC_API_KEY),
    ("APT_WP_USERNAME", APT_WP_USERNAME),
    ("APT_WP_APP_PASSWORD", APT_WP_APP_PASSWORD),
    ("PUBLIC_DATA_API_KEY_APT", PUBLIC_DATA_API_KEY_APT),
    ("PUBLIC_DATA_API_KEY_SCORE", PUBLIC_DATA_API_KEY_SCORE),
]:
    if not val:
        raise ValueError(f"{key} 환경변수가 설정되지 않았습니다.")

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
MODEL_NAME = "claude-haiku-4-5"
print(f"Using model: {MODEL_NAME}\n")

# ==========================================
# 색상 상수
# ==========================================
CAT_COLOR        = "#10b981"
CAT_LIGHT_BG     = "#ecfdf5"
CAT_LIGHT_BORDER = "#a7f3d0"
CAT_DARK         = "#059669"

CAT_ID = {
    "apt-info":     2,
    "apt-guide":    3,
    "apt-news":     4,
    "apt-schedule": 15,
}

# 청약/분양 필터 키워드
APT_KEYWORDS = [
    "청약", "분양", "청약홈", "아파트 공급", "무순위 청약", "특별공급",
    "일반공급", "청약 접수", "분양가", "청약 자격", "청약통장",
    "공공분양", "민간분양", "사전청약", "분양권", "입주권", "청약 경쟁률"
]
EXCLUDE_KEYWORDS = [
    "경매", "공매", "전세사기", "빌라 경매", "오피스텔 경매",
    "법원 경매", "임차인", "전세보증", "깡통전세"
]

# 정책 관련 키워드 (국토부 보도자료 필터링)
POLICY_KEYWORDS = [
    "청약", "분양가", "특별공급", "규제지역", "투기과열", "조정대상",
    "분양가상한제", "LTV", "DTI", "DSR", "주택공급", "청약제도",
    "공공주택", "사전청약", "청약통장", "무순위청약"
]

# 청약가이드 로테이션 주제 리스트 (30개)
GUIDE_ROTATION_TOPICS = [
    "청약통장 종류별 차이와 1순위 자격 만드는 법",
    "청약가점 계산법 완전정복 — 무주택·부양가족·납입기간",
    "신혼부부 특별공급 자격 조건과 소득 기준 총정리",
    "생애최초 특별공급 신청 자격과 주의사항",
    "다자녀 특별공급 조건과 가점 산정 방식",
    "노부모 부양 특별공급 동거 기간과 세대 요건",
    "추첨제 비율 높은 단지를 노리는 청약 전략",
    "투기과열지구 청약 자격과 대출 제한 완전 정리",
    "조정대상지역 1순위 청약 조건과 전매 제한 기간",
    "분양가상한제 단지의 전매 제한과 실거주 의무",
    "청약 당첨 후 계약금·중도금·잔금 자금 계획 가이드",
    "중도금 집단대출 조건과 규제지역별 LTV 한도",
    "청약 신청 전 반드시 확인할 서류 체크리스트",
    "부적격 당첨 사례 Top 5와 예방법",
    "청약 취소·포기 시 재당첨 제한 기간 안내",
    "무주택자 인정 기준과 세대원 주택 보유 판단법",
    "청약홈 회원가입부터 신청까지 단계별 사용법",
    "1순위와 2순위 청약 전략 차이와 선택 기준",
    "공공분양과 민간분양 차이 — 자격·가격·전매 비교",
    "사전청약 제도 개념과 일반청약과의 차이점",
    "분양권 전매 가능 시점과 세금 주의사항",
    "당첨자 발표 확인 방법과 이의신청 절차",
    "입주자저축 납입 인정 횟수 기준과 통장 관리법",
    "특별공급 중복 신청 금지 규정과 예외 사항",
    "청약 가점 극대화를 위한 세대 분리 전략",
    "공공택지 vs 민간택지 청약 조건 비교",
    "미분양 단지 무순위 줍줍 신청 방법과 조건",
    "계약 후 입주까지 타임라인과 단계별 준비 사항",
    "청약 낙첨 반복 시 대안 전략 — 추첨제·미분양 활용",
    "2025년 청약제도 주요 변경사항 총정리",
]

# ==========================================
# WordPress REST API 헬퍼
# ==========================================
def wp_auth_header():
    token = base64.b64encode(f"{APT_WP_USERNAME}:{APT_WP_APP_PASSWORD}".encode()).decode()
    return {"Authorization": f"Basic {token}", "Content-Type": "application/json"}

def wp_create_draft(title, content, excerpt, category_id, slug):
    payload = {
        "title": title, "content": content, "excerpt": excerpt,
        "status": "draft", "slug": slug,
    }
    if category_id:
        payload["categories"] = [category_id]
    resp = requests.post(
        f"{APT_WP_SITE_URL}/wp-json/wp/v2/posts",
        headers=wp_auth_header(), json=payload, timeout=15,
    )
    if not resp.ok:
        print(f"WordPress API 오류 {resp.status_code}: {resp.text[:300]}")
        return None
    return resp.json()

def wp_find_post_by_slug(slug):
    """슬러그로 포스트 ID 조회"""
    resp = requests.get(
        f"{APT_WP_SITE_URL}/wp-json/wp/v2/posts",
        headers=wp_auth_header(),
        params={"slug": slug, "status": "any", "per_page": 1},
        timeout=15,
    )
    if resp.ok:
        posts = resp.json()
        if posts:
            return posts[0]["id"]
    return None

def wp_update_post(post_id, title, content, excerpt):
    """기존 포스트 내용 업데이트"""
    payload = {"title": title, "content": content, "excerpt": excerpt}
    resp = requests.post(
        f"{APT_WP_SITE_URL}/wp-json/wp/v2/posts/{post_id}",
        headers=wp_auth_header(), json=payload, timeout=15,
    )
    if not resp.ok:
        print(f"포스트 업데이트 실패 {resp.status_code}: {resp.text[:200]}")
        return None
    print(f"포스트 업데이트 완료! ID: {post_id}")
    return resp.json()

def wp_update_rank_math(post_id, focus_keyword, meta_description):
    payload = {"meta": {
        "rank_math_focus_keyword": focus_keyword,
        "rank_math_description": meta_description,
    }}
    resp = requests.post(
        f"{APT_WP_SITE_URL}/wp-json/wp/v2/posts/{post_id}",
        headers=wp_auth_header(), json=payload, timeout=15,
    )
    if resp.status_code == 200:
        print(f"Rank Math 메타 업데이트 완료 (post_id: {post_id})")
    else:
        print(f"Rank Math 메타 업데이트 실패: {resp.status_code} {resp.text[:200]}")

# ==========================================
# 텔레그램 전송
# ==========================================
def send_telegram(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"},
            timeout=10,
        )
        print("텔레그램 전송 완료" if resp.status_code == 200 else f"텔레그램 전송 실패: {resp.text}")
    except Exception as e:
        print(f"텔레그램 전송 오류: {e}")

# ==========================================
# 데이터 수집 함수들
# ==========================================

def fetch_applyhome_today_schedule():
    """
    청약홈 청약캘린더 페이지 스크래핑으로 당일 접수 단지 수집
    https://www.applyhome.co.kr/ai/aib/selectSubscrptCalenderView.do
    """
    print("청약홈 당일 청약 일정 수집 중...")
    today = datetime.now()
    today_str = today.strftime("%Y%m%d")
    ym = today.strftime("%Y%m")
    results = []

    hdrs = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "ko-KR,ko;q=0.9",
        "Referer": "https://www.applyhome.co.kr/",
    }

    def _make_entry(name, href, region="", cat_label="당일 접수", is_remndr=False):
        full_url = (f"https://www.applyhome.co.kr{href}" if href.startswith("/") else href) if href else "https://www.applyhome.co.kr/ai/aib/selectSubscrptHouseListSup.do"
        return {
            "house_nm": name, "region": region, "supply_cnt": "",
            "rcrit_pblanc_de": today_str,
            "subscrpt_rcept_bgnde": today_str, "subscrpt_rcept_endde": "",
            "przwner_presnatn_de": "", "cntrct_cncls_bgnde": "",
            "house_secd_nm": "APT", "house_dtl_secd_nm": "",
            "bsns_mby_nm": "", "hssply_adres": "",
            "pblanc_url": full_url,
            "speclt_rdn_earth_at": "", "mdat_trget_area_secd": "", "parcprc_uls_at": "",
            "subs_category": cat_label,
            "is_remndr": is_remndr,
        }

    # ── 1단계: 캘린더 AJAX (JSON) ──────────────────────────────
    ajax_urls = [
        ("POST", "https://www.applyhome.co.kr/ai/aib/selectSubscrptCalenderListJson.do",
         {"searchYm": ym, "houseSecd": "APT"}),
        ("POST", "https://www.applyhome.co.kr/ai/aia/selectListApplyHomePblancListJson.do",
         {"searchDate": today_str, "houseSecd": ""}),
        ("GET",  f"https://www.applyhome.co.kr/ai/aib/selectSubscrptCalenderListJson.do?searchYm={ym}&houseSecd=APT",
         {}),
    ]
    for method, url, payload in ajax_urls:
        try:
            ajax_hdrs = {**hdrs, "Accept": "application/json, */*", "X-Requested-With": "XMLHttpRequest"}
            if method == "POST":
                resp = requests.post(url, data=payload, headers=ajax_hdrs, timeout=15)
            else:
                resp = requests.get(url, headers=ajax_hdrs, timeout=15)
            if resp.status_code != 200:
                continue
            data = resp.json()
            # 캘린더 API: 날짜별 리스트 구조 처리
            cat_map = [
                ("spclSuplyList", "APT 특별공급", False),
                ("rank1List",     "APT 1순위",    False),
                ("rank2List",     "APT 2순위",    False),
                ("remndrList",    "APT 잔여세대",  True),
            ]
            if isinstance(data, dict):
                # 날짜-키 구조: {"20260616": [...]} or {"spclSuplyList": [...]}
                for v in data.values():
                    if isinstance(v, list):
                        for item in v:
                            if not isinstance(item, dict):
                                continue
                            name = item.get("houseNm") or item.get("house_nm", "")
                            if not name:
                                continue
                            cat = item.get("subscrptType") or item.get("house_secd_nm", "당일 접수")
                            is_rem = "잔여" in cat or "무순위" in cat
                            results.append(_make_entry(
                                name,
                                item.get("pblancUrl") or item.get("pblanc_url", ""),
                                item.get("subscrptAreaCodeNm") or item.get("region", ""),
                                cat, is_rem,
                            ))
                for cat_key, cat_label, is_rem in cat_map:
                    for item in data.get(cat_key, []):
                        name = item.get("houseNm") or item.get("house_nm", "")
                        if not name:
                            continue
                        results.append(_make_entry(
                            name,
                            item.get("pblancUrl") or item.get("pblanc_url", ""),
                            item.get("subscrptAreaCodeNm") or item.get("hssplyAdres", ""),
                            cat_label, is_rem,
                        ))
            if results:
                print(f"청약홈 캘린더 AJAX {len(results)}건 수집 ({url[-50:]})")
                return results
        except Exception as e:
            print(f"청약홈 AJAX 실패 ({url[-40:]}): {e}")

    # ── 2단계: 캘린더 HTML 직접 파싱 ──────────────────────────
    calendar_urls = [
        "https://www.applyhome.co.kr/ai/aib/selectSubscrptCalenderView.do",
        "https://www.applyhome.co.kr/ai/aib/selectSubscrptHouseListSup.do",
        "https://www.applyhome.co.kr",
    ]
    for page_url in calendar_urls:
        try:
            resp = requests.get(page_url, headers=hdrs, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            found = []
            # 캘린더 셀 내 단지 링크
            for a in soup.find_all("a", href=True):
                href = a.get("href", "")
                name = a.get_text(strip=True)
                if not name or len(name) < 3:
                    continue
                is_rem = "잔여" in name or "무순위" in name or "줍줍" in name
                if ("APTLttotPblancDetail" in href or "APTRemndr" in href
                        or "pblancNo" in href or "houseManageNo" in href):
                    found.append(_make_entry(name, href, "", "당일 접수", is_rem))
            # 테이블 행 파싱 (목록형 페이지)
            for row in soup.select("table tbody tr, ul.list_type li"):
                tds = row.find_all(["td", "li"])
                name_tag = row.find("a", href=True)
                if not name_tag:
                    continue
                name = name_tag.get_text(strip=True)
                href = name_tag.get("href", "")
                if not name:
                    continue
                region = tds[1].get_text(strip=True) if len(tds) > 1 else ""
                is_rem = "잔여" in name or "무순위" in name
                found.append(_make_entry(name, href, region, "당일 접수", is_rem))
            # 중복 제거
            seen = set()
            for e in found:
                if e["house_nm"] not in seen:
                    seen.add(e["house_nm"])
                    results.append(e)
            if results:
                print(f"청약홈 HTML 파싱 {len(results)}건 수집 ({page_url})")
                return results
        except Exception as e:
            print(f"청약홈 HTML 파싱 실패 ({page_url}): {e}")

    print(f"청약홈 전체 수집 실패 — 0건")
    return results


def fetch_apt_remndr():
    """청약홈 무순위(줍줍) 공공데이터 API"""
    print("청약홈 무순위(줍줍) API 호출 중...")
    today = datetime.now()
    month_ago = today - timedelta(days=30)
    base_url = "https://apis.data.go.kr/B551155/APTRemndrLttotPblancDetail/getRemndrLttotPblancDetail"
    params = {
        "serviceKey": PUBLIC_DATA_API_KEY_APT,
        "startSubscrptDate": month_ago.strftime("%Y%m%d"),
        "endSubscrptDate": today.strftime("%Y%m%d"),
        "numOfRows": 10, "pageNo": 1, "_type": "json",
    }
    remndr = []
    try:
        resp = requests.get(base_url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
        if isinstance(items, dict):
            items = [items]
        for item in items:
            remndr.append({
                "house_nm":             item.get("house_nm", ""),
                "region":               item.get("subscrpt_area_code_nm", ""),
                "supply_cnt":           item.get("tot_suply_hshldco", ""),
                "rcrit_pblanc_de":      item.get("rcrit_pblanc_de", ""),
                "subscrpt_rcept_bgnde": item.get("subscrpt_rcept_bgnde", ""),
                "subscrpt_rcept_endde": item.get("subscrpt_rcept_endde", ""),
                "przwner_presnatn_de":  item.get("przwner_presnatn_de", ""),
                "cntrct_cncls_bgnde":   item.get("cntrct_cncls_bgnde", ""),
                "house_secd_nm":        item.get("house_secd_nm", ""),
                "house_dtl_secd_nm":    item.get("house_dtl_secd_nm", ""),
                "bsns_mby_nm":          item.get("bsns_mby_nm", ""),
                "hssply_adres":         item.get("hssply_adres", ""),
                "pblanc_url":           item.get("pblanc_url", ""),
                "speclt_rdn_earth_at":  item.get("speclt_rdn_earth_at", ""),
                "mdat_trget_area_secd": item.get("mdat_trget_area_secd", ""),
                "parcprc_uls_at":       item.get("parcprc_uls_at", ""),
                "is_remndr":            True,  # 무순위 표시
            })
        print(f"무순위(줍줍) 공고 {len(remndr)}건 수집 완료")
    except Exception as e:
        print(f"무순위 API 호출 실패: {e}")
    return remndr


def fetch_weekly_schedule():
    """
    이번 주(오늘~+6일) 청약 일정 수집
    - 청약홈 캘린더 AJAX (한국부동산원)
    - LH 선착순(수의)계약 목록
    반환: {"applyhome": [...], "lh": [...]}
    각 항목: {date, house_nm, region, category, pblanc_url}
    """
    today = datetime.now()
    hdrs = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, */*",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://www.applyhome.co.kr/",
    }
    applyhome_items = []

    # 이번 주 + 다음 주 달(월이 바뀔 수 있으니 2개월 처리)
    months_needed = set()
    for i in range(7):
        d = today + timedelta(days=i)
        months_needed.add(d.strftime("%Y%m"))

    date_range = set()
    for i in range(7):
        date_range.add((today + timedelta(days=i)).strftime("%Y%m%d"))

    for ym in sorted(months_needed):
        for ajax_url, payload in [
            ("https://www.applyhome.co.kr/ai/aib/selectSubscrptCalenderListJson.do",
             {"searchYm": ym, "houseSecd": "APT"}),
            ("https://www.applyhome.co.kr/ai/aia/selectListApplyHomePblancListJson.do",
             {"searchDate": today.strftime("%Y%m%d"), "houseSecd": ""}),
        ]:
            try:
                resp = requests.post(ajax_url, data=payload, headers=hdrs, timeout=15)
                if resp.status_code != 200:
                    continue
                data = resp.json()
                cat_map = [
                    ("spclSuplyList", "특별공급"),
                    ("rank1List",     "1순위"),
                    ("rank2List",     "2순위"),
                    ("remndrList",    "잔여세대"),
                ]
                found = False
                for cat_key, cat_label in cat_map:
                    for item in data.get(cat_key, []):
                        date = (item.get("subscrptRceptBgnde") or
                                item.get("rcritPblancDe") or
                                today.strftime("%Y%m%d"))
                        applyhome_items.append({
                            "date":      date,
                            "house_nm":  item.get("houseNm", ""),
                            "region":    item.get("subscrptAreaCodeNm") or item.get("hssplyAdres", ""),
                            "category":  cat_label,
                            "pblanc_url": item.get("pblancUrl", "https://www.applyhome.co.kr"),
                            "supply_cnt": item.get("totSuplyHshldco", ""),
                        })
                        found = True
                # 날짜-키 구조 처리
                if not found:
                    for k, v in data.items():
                        if k in date_range and isinstance(v, list):
                            for item in v:
                                if not isinstance(item, dict):
                                    continue
                                applyhome_items.append({
                                    "date":      k,
                                    "house_nm":  item.get("houseNm", ""),
                                    "region":    item.get("subscrptAreaCodeNm", ""),
                                    "category":  item.get("subscrptType", "청약"),
                                    "pblanc_url": item.get("pblancUrl", "https://www.applyhome.co.kr"),
                                    "supply_cnt": item.get("totSuplyHshldco", ""),
                                })
                if applyhome_items:
                    break
            except Exception as e:
                print(f"청약홈 주간 일정 AJAX 실패: {e}")
        if applyhome_items:
            break

    # HTML 캘린더 fallback
    if not applyhome_items:
        try:
            page_hdrs = {k: v for k, v in hdrs.items() if k != "Accept"}
            resp = requests.get(
                "https://www.applyhome.co.kr/ai/aib/selectSubscrptCalenderView.do",
                headers=page_hdrs, timeout=15)
            soup = BeautifulSoup(resp.text, "html.parser")
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if "pblancNo" not in href and "houseManageNo" not in href:
                    continue
                name = a.get_text(strip=True)
                if not name:
                    continue
                applyhome_items.append({
                    "date": today.strftime("%Y%m%d"),
                    "house_nm": name,
                    "region": "", "category": "청약",
                    "pblanc_url": f"https://www.applyhome.co.kr{href}" if href.startswith("/") else href,
                    "supply_cnt": "",
                })
        except Exception as e:
            print(f"청약홈 캘린더 HTML fallback 실패: {e}")

    # 이번 주 날짜만 필터
    week_items = [i for i in applyhome_items if i["date"] in date_range] or applyhome_items
    week_items.sort(key=lambda x: (x["date"], x["house_nm"]))
    print(f"청약홈 주간 일정 {len(week_items)}건 수집")

    # LH 선착순 계약 목록
    lh_items = fetch_lh_sunchaksuun()

    return {"applyhome": week_items, "lh": lh_items}


def generate_weekly_schedule_article():
    """이번 주 청약 일정 총정리 글 생성"""
    print("이번 주 청약 일정 총정리 글 생성 중...")
    today = datetime.now()
    week_end = today + timedelta(days=6)
    data = fetch_weekly_schedule()
    ah_items  = data["applyhome"]
    lh_items  = data["lh"]

    # 날짜별 그룹핑
    from collections import defaultdict
    by_date = defaultdict(list)
    for item in ah_items:
        by_date[item["date"]].append(item)

    ah_block_lines = []
    for date in sorted(by_date):
        try:
            d_fmt = datetime.strptime(date, "%Y%m%d").strftime("%m/%d(%a)")
        except Exception:
            d_fmt = date
        for item in by_date[date]:
            nm  = item["house_nm"] or "(단지명 미정)"
            reg = f" [{item['region']}]" if item["region"] else ""
            cnt = f" {item['supply_cnt']}세대" if item["supply_cnt"] else ""
            ah_block_lines.append(f"- {d_fmt} | {item['category']} | {nm}{reg}{cnt}")
    ah_block = "\n".join(ah_block_lines) if ah_block_lines else "청약홈 API에서 일정을 가져오지 못했습니다. 청약홈 캘린더를 직접 확인하세요."

    lh_lines = []
    for item in lh_items:
        area    = item.get("area", "")
        unsold  = item.get("unsold", "")
        raw_price = item.get("lh_price", "")
        # 천원 단위 → 억/만원으로 변환
        # 예: 312,450천원 = 312,450,000원 = 3억 1,245만원
        price_str = ""
        if raw_price:
            try:
                p_chon = int(str(raw_price).replace(",", "").replace("천원", "").strip())
                p_won  = p_chon * 1000          # 원 단위
                eok    = p_won // 100_000_000   # 억
                man    = (p_won % 100_000_000) // 10_000  # 나머지 만원
                if eok > 0 and man > 0:
                    price_str = f"약 {eok}억 {man:,}만원"
                elif eok > 0:
                    price_str = f"약 {eok}억원"
                else:
                    price_str = f"약 {man:,}만원"
            except Exception:
                price_str = f"{raw_price}천원"
        parts = []
        if area:   parts.append(f"전용 {area}㎡")
        if unsold: parts.append(f"미분양 {unsold}호")
        if price_str: parts.append(f"주택가격 {price_str}")
        contact = item.get("contact", "")
        if contact: parts.append(f"문의 {contact}")
        extra_str = " | ".join(parts)
        lh_lines.append(f"- {item['region']} | {item['house_nm']} | {extra_str}")
    lh_block = "\n".join(lh_lines) if lh_lines else "현재 LH 선착순 계약 물량 없음"

    date_range_str = f"{today.strftime('%Y년 %m월 %d일')} ~ {week_end.strftime('%m월 %d일')}"

    # 데이터 보유 현황에 따라 제목 지침 결정
    has_ah  = len(ah_items) > 0
    has_lh  = len(lh_items) > 0
    if not has_ah and not has_lh:
        print("청약홈·LH 데이터 모두 없음 — 청약일정 글 미발행")
        return None
    if has_ah and has_lh:
        title_guide = (
            f"제목: [청약일정] {date_range_str} 이번 주 청약 일정 총정리 (한국부동산원·LH)\n"
            "→ 한국부동산원 청약 일정과 LH 선착순 계약을 모두 포함하는 종합 정리임을 제목에 반영"
        )
    elif has_ah and not has_lh:
        title_guide = (
            f"제목: [청약일정] {date_range_str} 이번 주 한국부동산원 청약 일정\n"
            "→ 청약홈(한국부동산원) 일정만 있음. '총정리' 대신 '청약홈 청약 일정'으로 작성"
        )
    elif not has_ah and has_lh:
        title_guide = (
            f"제목: [청약일정] {date_range_str} LH 선착순(수의)계약 현황 — 지금 신청 가능한 미분양 단지\n"
            "→ LH 선착순 계약 정보 중심으로 작성. '총정리'라는 표현 사용 금지"
        )
    else:
        title_guide = (
            f"제목: [청약일정] {date_range_str} 청약 일정 안내\n"
            "→ 청약홈·LH 일정 확인 방법 중심으로 작성"
        )

    html_guide = build_apt_html_guide(
        top_url="https://www.applyhome.co.kr/ai/aib/selectSubscrptCalenderView.do",
        top_btn="청약홈 전체 일정 보기",
        bottom_url="https://apply.lh.or.kr/lhapply/apply/bor_ctrt_psb_dst/1/lfn_getTabChange.do?mi=201526",
        bottom_btn="LH 선착순 계약 확인",
        ref_url="https://www.applyhome.co.kr/ai/aib/selectSubscrptCalenderView.do",
        ref_name="청약홈 청약캘린더",
    )

    prompt = f"""당신은 apt.bestwellth.org 청약일정팀 전문 에디터입니다.

아래 데이터를 바탕으로 청약 일정 안내 글을 작성하세요.
독자는 청약을 준비 중인 실수요자이며, 정확하고 신뢰할 수 있는 정보만을 원합니다.

[수집된 데이터 현황]
- 한국부동산원(청약홈) 이번 주 일정: {len(ah_items)}건
- LH 선착순(수의)계약 현황: {len(lh_items)}건

[이번 주 청약홈(한국부동산원) 일정]
{ah_block}

[LH 선착순(수의)계약 현황 — 미분양 물량 선착순 계약 가능]
{lh_block}

[제목 작성 기준 — 반드시 준수]
{title_guide}

[작성 원칙]
- 제목은 위 [제목 작성 기준]을 반드시 따를 것
- 수집된 데이터만으로 팩트 중심 작성. API 접근 실패·데이터 부재 등 내부 상황 언급 절대 금지
- 한국부동산원 일정이 있을 경우 날짜·단지명·청약 구분(특별공급/1순위/2순위/잔여세대)을 표 형태로 정리
- LH 선착순 계약은 지역·단지명·미분양호수·가격을 표로 정리하고 "줍줍 성격의 미분양 물량"임을 설명
- LH 주택가격은 데이터에 이미 "약 3억 1,245만원" 형식으로 변환되어 있음 — 그대로 사용할 것. 절대 임의 수치 생성 금지
- 문어체(이다/한다/했다), 구어체·Markdown·이모티콘 금지
- HTML을 ```html 또는 ``` 마크다운 코드블록으로 감싸지 말 것 — 순수 HTML만 출력
- [청약일정] 접두어 필수, 느낌표 금지
- 글 반드시 끝까지 완성

{html_guide}

[SEO — 반드시 출력]
[FOCUS_KW]3~4단어 롱테일 키워드[/FOCUS_KW]
[META_DESC]140~160자 메타 설명[/META_DESC]
[SLUG]영문 슬러그[/SLUG]
[EXCERPT]100~150자 발췌문[/EXCERPT]

[응답 형식]
[TITLE][청약일정] 제목[/TITLE]
본문 HTML
[FOCUS_KW]...[/FOCUS_KW][META_DESC]...[/META_DESC][SLUG]...[/SLUG][EXCERPT]...[/EXCERPT]"""
    return call_claude(prompt, "청약일정(주간)")


def fetch_applyhome_pblanc_list():
    """
    청약홈 분양정보 APT 목록 수집 + 상세 팝업 HTML 파싱.
    Stage1: 공공데이터 API로 현재 청약 접수 중/예정 단지 목록 수집 (houseManageNo, pblancNo 확보)
    Stage2: 청약홈 selectAPTLttotPblancDetail.do 팝업으로 상세 정보 파싱
    """
    import re as _re
    print("청약홈 분양정보 목록 수집 중...")

    # ── Stage 1: odcloud 청약홈 분양정보 API (api.odcloud.kr) ──
    # 승인된 서비스: 한국부동산원_청약홈 분양정보 조회 서비스 (stage 37000)
    # Base URL: api.odcloud.kr/api
    import urllib.parse as _up
    today = datetime.now()
    start = (today - timedelta(days=30)).strftime("%Y%m%d")
    end   = (today + timedelta(days=60)).strftime("%Y%m%d")
    items_raw = []

    KEY = PUBLIC_DATA_API_KEY_APT
    ODCLOUD_BASE = "https://api.odcloud.kr/api/ApplyhomeInfoDetailSvc/v1"

    api_attempts = [
        # 1) odcloud 목록 - 청약 접수일 기준
        f"{ODCLOUD_BASE}/getAPTLttotPblancList?serviceKey={KEY}&startSubscrptDate={start}&endSubscrptDate={end}&perPage=20&page=1",
        # 2) odcloud 목록 - 파라미터 없이 최신
        f"{ODCLOUD_BASE}/getAPTLttotPblancList?serviceKey={KEY}&perPage=20&page=1",
        # 3) odcloud 상세 목록
        f"{ODCLOUD_BASE}/getAPTLttotPblancDetail?serviceKey={KEY}&perPage=20&page=1",
        # 4) odcloud 다른 서비스명 시도
        f"https://api.odcloud.kr/api/ApplyhomeLttotPblancSvc/v1/getAPTLttotPblancList?serviceKey={KEY}&perPage=20&page=1",
    ]
    for raw_url in api_attempts:
        try:
            resp = requests.get(raw_url, timeout=15)
            ct = resp.headers.get("content-type", "")
            print(f"  청약홈API: {resp.status_code} ct={ct[:40]} len={len(resp.text)}")
            if not resp.ok or "html" in ct.lower():
                print(f"  청약홈API 오류 → 다음 시도. 응답: {resp.text[:120]}")
                continue
            try:
                data = resp.json()
            except Exception:
                print(f"  청약홈API JSON 파싱 실패: {resp.text[:100]}")
                continue
            # odcloud 응답 구조: {"data": [...], "totalCount": N, ...}
            # 또는 표준 공공API: {"response": {"body": {"items": {...}}}}
            if "data" in data:
                items_raw = data["data"] if isinstance(data["data"], list) else []
            else:
                body  = data.get("response", {}).get("body", {})
                items = body.get("items", {})
                if isinstance(items, dict):
                    items = items.get("item", [])
                if isinstance(items, dict):
                    items = [items]
                items_raw = [i for i in (items or []) if i]
            if items_raw:
                print(f"  청약홈API {len(items_raw)}건 수집 성공 (URL: {raw_url[60:100]}...)")
                break
            print(f"  청약홈API OK지만 데이터 없음: {str(data)[:200]}")
        except Exception as e:
            print(f"  청약홈API 실패: {e}")

    if not items_raw:
        print("  청약홈 공공API 모든 시도 실패 → 빈 결과 반환")
        return []

    # 첫 번째 아이템의 키 목록 출력 (디버깅)
    print(f"  odcloud 응답 필드: {list(items_raw[0].keys())[:15]}")

    # ── Stage 2: API 데이터 직접 사용 + 청약홈 상세 팝업 보완 ──
    results = []
    hdrs = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept-Language": "ko-KR,ko;q=0.9",
        "Referer": "https://www.applyhome.co.kr/ai/aia/selectAPTLttotPblancListView.do",
    }
    session = requests.Session()
    session.headers.update(hdrs)

    for item in items_raw[:5]:
        if len(results) >= 3:
            break
        # odcloud API 필드명은 UPPERCASE (HOUSE_NM, PBLANC_NO 등)
        def _f(*keys):
            for k in keys:
                v = item.get(k)
                if v:
                    return str(v)
            return ""
        house_manage_no = _f("HOUSE_MANAGE_NO", "houseManageNo", "house_manage_no")
        pblanc_no       = _f("PBLANC_NO", "pblancNo", "pblanc_no") or house_manage_no
        house_nm_raw    = _f("HOUSE_NM", "houseNm", "house_nm", "단지명", "주택명")
        if not house_nm_raw:
            # 키 목록에서 이름 관련 필드 찾기
            for k, v in item.items():
                if any(word in k.lower() for word in ["nm", "name", "단지", "주택"]) and v:
                    house_nm_raw = str(v)
                    print(f"  house_nm fallback key: {k}={v}")
                    break
        if not house_nm_raw:
            print(f"  house_nm 없음, 건너뜀. 키: {list(item.keys())}")
            continue

        # 청약홈 detail 팝업 시도
        detail_url = (
            f"https://www.applyhome.co.kr/ai/aia/selectAPTLttotPblancDetail.do"
            f"?houseManageNo={house_manage_no or pblanc_no}&pblancNo={pblanc_no}"
        )
        try:
            resp = session.get(detail_url, timeout=15)
            print(f"  상세 [{pblanc_no}] {resp.status_code}, len={len(resp.text)}")
            if resp.status_code != 200 or len(resp.text) < 500:
                continue
            soup = BeautifulSoup(resp.text, "html.parser")

            def cell_after(label):
                for el in soup.find_all(["th", "td"]):
                    if label in el.get_text():
                        nxt = el.find_next_sibling("td")
                        if nxt:
                            return nxt.get_text(strip=True)
                return ""

            name_el = soup.select_one("thead th[colspan]")
            name    = name_el.get_text(strip=True) if name_el else house_nm_raw
            addr    = cell_after("공급위치")
            supply  = cell_after("공급규모")

            rcrit_de  = cell_after("모집공고일").split("(")[0].strip()
            sp_date = rnk1_date = rnk2_date = ""
            winner_de = cell_after("당첨자 발표일").split("(")[0].strip()
            cntrct_de = cell_after("계약일")
            for row in soup.select("table tbody tr"):
                cells = [td.get_text(strip=True) for td in row.find_all(["th","td"])]
                row_text = " ".join(cells)
                if "특별공급" in row_text and not sp_date:
                    for c in cells:
                        if _re.match(r"\d{4}-\d{2}-\d{2}", c):
                            sp_date = c; break
                if "1순위" in row_text and not rnk1_date:
                    for c in cells:
                        if _re.match(r"\d{4}-\d{2}-\d{2}", c):
                            rnk1_date = c; break
                if "2순위" in row_text and not rnk2_date:
                    for c in cells:
                        if _re.match(r"\d{4}-\d{2}-\d{2}", c):
                            rnk2_date = c; break

            price_rows = []
            price_unit = "만원"  # 기본값
            for table in soup.find_all("table"):
                cap = table.find("caption")
                if cap and "공급금액" in cap.get_text():
                    # 표 우측상단 단위 텍스트 탐색 (caption 또는 표 위 텍스트)
                    # 예: "공급금액(단위:만원)" 또는 "공급금액(단위:천원)"
                    cap_text = cap.get_text()
                    # 표 바깥 가장 가까운 단위 표기 탐색
                    unit_text = cap_text
                    # thead 포함 전체 표 텍스트에서도 탐색
                    thead = table.find("thead")
                    if thead:
                        unit_text += thead.get_text()
                    # 표 앞뒤 sibling text도 확인
                    prev_sib = table.find_previous_sibling()
                    if prev_sib:
                        unit_text += prev_sib.get_text()
                    if "단위:천원" in unit_text or "단위 : 천원" in unit_text or "(천원)" in unit_text:
                        price_unit = "천원"
                    elif "단위:만원" in unit_text or "단위 : 만원" in unit_text or "(만원)" in unit_text:
                        price_unit = "만원"
                    print(f"  공급금액 단위 감지: {price_unit}")
                    for row in table.select("tbody tr"):
                        cols = [td.get_text(strip=True) for td in row.find_all("td")]
                        if len(cols) >= 2 and cols[0] and cols[1]:
                            price_rows.append(f"{cols[0]}㎡ {cols[1]}{price_unit}")
                    break
            # 가격 변환: 천원 단위면 억/만원으로, 만원 단위면 억 단위로 표기
            def _fmt_price(val_str, unit):
                try:
                    v = int(val_str.replace(",", "").replace(unit, "").strip())
                    if unit == "천원":
                        won = v * 1000
                    else:  # 만원
                        won = v * 10000
                    eok = won // 100_000_000
                    man = (won % 100_000_000) // 10_000
                    if eok > 0 and man > 0:
                        return f"약 {eok}억 {man:,}만원"
                    elif eok > 0:
                        return f"약 {eok}억원"
                    else:
                        return f"약 {man:,}만원"
                except Exception:
                    return val_str + unit
            converted_prices = []
            for pr in price_rows[:4]:
                # pr 형식: "084.98㎡ 65,460만원"
                parts2 = pr.rsplit(" ", 1)
                if len(parts2) == 2:
                    typ, val_with_unit = parts2
                    val = val_with_unit.replace(price_unit, "").strip()
                    converted_prices.append(f"{typ} {_fmt_price(val, price_unit)}")
                else:
                    converted_prices.append(pr)
            price_summary = " / ".join(converted_prices) if converted_prices else ""

            move_in = ""
            for li in soup.select("ul.inde_txt li"):
                text = li.get_text(strip=True)
                if "입주예정월" in text:
                    m = _re.search(r"(\d{4}\.\d{1,2})", text)
                    if m:
                        move_in = m.group(1); break

            special_types = set()
            for th in soup.select("thead th"):
                for sp in ["다자녀", "신혼부부", "생애최초", "청년", "노부모", "신생아", "기관추천"]:
                    if sp in th.get_text(strip=True):
                        special_types.add(sp)

            constructor = ""
            for row in soup.select("table tbody tr"):
                cols = [td.get_text(strip=True) for td in row.find_all("td")]
                if len(cols) >= 2:
                    h = row.find_previous("thead")
                    if h and "시공사" in h.get_text():
                        constructor = cols[1] if len(cols) > 1 else cols[0]
                        break

            extra_parts = []
            if price_summary: extra_parts.append(f"공급금액(만원): {price_summary}")
            if move_in:        extra_parts.append(f"입주예정 {move_in}")
            if special_types:  extra_parts.append(f"특별공급: {', '.join(sorted(special_types))}")
            if constructor:    extra_parts.append(f"시공사: {constructor}")

            results.append({
                "house_nm":             name,
                "region":               addr.split(" ")[0] if addr else "",
                "hssply_adres":         addr,
                "supply_cnt":           supply.replace("세대", ""),
                "rcrit_pblanc_de":      rcrit_de,
                "subscrpt_rcept_bgnde": sp_date or rnk1_date,
                "subscrpt_rcept_endde": rnk2_date,
                "przwner_presnatn_de":  winner_de,
                "cntrct_cncls_bgnde":   cntrct_de,
                "house_secd_nm":        "민간분양",
                "house_dtl_secd_nm":    "분양주택",
                "bsns_mby_nm":          _f("BSNS_MBY_NM", "bsnsMbyNm", "bsns_mby_nm"),
                "hssply_adres":         addr,
                "pblanc_url":           detail_url,
                "speclt_rdn_earth_at":  _f("SPECLT_RDN_EARTH_AT", "specltRdnEarthAt"),
                "mdat_trget_area_secd": _f("MDAT_TRGET_AREA_SECD", "mdatTrgetAreaSecd"),
                "parcprc_uls_at":       _f("PARCPRC_ULS_AT", "parcprcUlsAt"),
                "subs_category":        "청약홈 분양",
                "is_remndr":            False,
                "extra_info":           " | ".join(extra_parts),
            })
            print(f"  청약홈 상세 파싱 완료: {name}")
        except Exception as e:
            print(f"  상세 파싱 실패 [{pblanc_no}]: {e} → 공공API 데이터로 대체")
            # 청약홈 detail 실패 시 공공API 데이터 직접 사용
            # API 직접 사용 시 청약 일정 정보 구성
            spsply_bgnde = _f("SPSPLY_RCEPT_BGNDE")
            rnk1_date    = _f("GNRL_RNK1_CRSPAREA_RCPTDE", "GNRL_RNK1_ETC_AREA_RCPTDE")
            rnk2_date    = _f("GNRL_RNK2_CRSPAREA_RCPTDE", "GNRL_RNK2_ETC_AREA_RCPTDE")
            rcept_bgn    = _f("RCEPT_BGNDE")
            rcept_end    = _f("RCEPT_ENDDE")
            mvn_ym       = _f("MVN_PREARNGE_YM")
            cnstrct      = _f("CNSTRCT_ENTRPS_NM")
            hmpg         = _f("HMPG_ADRES")
            pblanc_url_v = _f("PBLANC_URL") or hmpg or "https://www.applyhome.co.kr"
            extra_parts  = []
            if mvn_ym:   extra_parts.append(f"입주예정 {mvn_ym}")
            if cnstrct:  extra_parts.append(f"시공사: {cnstrct}")
            results.append({
                "house_nm":             _f("HOUSE_NM"),
                "region":               _f("SUBSCRPT_AREA_CODE_NM"),
                "hssply_adres":         _f("HSSPLY_ADRES"),
                "supply_cnt":           _f("TOT_SUPLY_HSHLDCO"),
                "rcrit_pblanc_de":      _f("RCRIT_PBLANC_DE"),
                "subscrpt_rcept_bgnde": spsply_bgnde or rnk1_date or rcept_bgn,
                "subscrpt_rcept_endde": rcept_end,
                "przwner_presnatn_de":  _f("PRZWNER_PRESNATN_DE"),
                "cntrct_cncls_bgnde":   _f("CNTRCT_CNCLS_BGNDE"),
                "house_secd_nm":        _f("HOUSE_SECD_NM") or "민간분양",
                "house_dtl_secd_nm":    _f("HOUSE_DTL_SECD_NM"),
                "bsns_mby_nm":          _f("BSNS_MBY_NM"),
                "pblanc_url":           pblanc_url_v,
                "speclt_rdn_earth_at":  _f("SPECLT_RDN_EARTH_AT"),
                "mdat_trget_area_secd": _f("MDAT_TRGET_AREA_SECD"),
                "parcprc_uls_at":       _f("PARCPRC_ULS_AT"),
                "subs_category":        "청약홈 분양",
                "is_remndr":            False,
                "extra_info":           " | ".join(extra_parts),
            })

    print(f"청약홈 분양정보 {len(results)}건 수집 완료")
    return results


def fetch_lh_sunchaksuun():
    """
    LH 선착순(수의)계약 분양주택 목록 스크래핑
    https://apply.lh.or.kr/lhapply/apply/bor_ctrt_psb_dst/1/lfn_getTabChange.do?mi=201526
    엑셀 다운로드 우선 시도, 실패 시 HTML 테이블 파싱
    컬럼: 지역(0) 지구명(1) 블록(2) 총세대수(3) 전용면적m²(4) 미분양호수(5) 주택가격천원(6) 분양문의(7) 분양유치금지급대상(8) 비고(9)
    """
    print("LH 선착순(수의)계약 분양주택 수집 중...")
    list_url  = "https://apply.lh.or.kr/lhapply/apply/bor_ctrt_psb_dst/1/lfn_getTabChange.do?mi=201526"
    excel_url = "https://apply.lh.or.kr/lhapply/apply/bor_ctrt_psb_dst/1/lfn_excelDownload.do?mi=201526"
    hdrs = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "ko-KR,ko;q=0.9",
        "Referer": list_url,
    }
    results = []

    def _parse_rows(rows_data):
        """행 리스트(컬럼값 리스트의 리스트)를 announcement dict로 변환"""
        parsed = []
        for cols in rows_data:
            if len(cols) < 4:
                continue
            def _col(idx, default=""):
                return cols[idx].strip() if idx < len(cols) else default
            region   = _col(0)
            district = _col(1)
            block    = _col(2)
            total    = _col(3)
            area     = _col(4)    # 전용면적(m²)
            unsold   = _col(5)    # 미분양호수
            price    = _col(6)    # 주택가격(천원)
            contact  = _col(7)    # 분양문의
            note     = _col(9) if len(cols) > 9 else _col(8)   # 비고 (자격제한 등)
            if not district:
                continue
            house_nm = f"LH {district} {block}블록" if block else f"LH {district}"
            parsed.append({
                "house_nm":             house_nm,
                "region":               region,
                "supply_cnt":           total,
                "rcrit_pblanc_de":      "",
                "subscrpt_rcept_bgnde": "",
                "subscrpt_rcept_endde": "",
                "przwner_presnatn_de":  "",
                "cntrct_cncls_bgnde":   "",
                "house_secd_nm":        "공공분양",
                "house_dtl_secd_nm":    "선착순수의계약",
                "bsns_mby_nm":          "LH한국토지주택공사",
                "hssply_adres":         region,
                "pblanc_url":           list_url,
                "speclt_rdn_earth_at":  "",
                "mdat_trget_area_secd": "",
                "parcprc_uls_at":       "",
                "subs_category":        "LH 선착순 계약",
                "is_remndr":            True,
                "lh_area":              area,
                "lh_unsold":            unsold,
                "lh_price":             price,
                "lh_contact":           contact,
                "lh_note":              note,   # 비고: 신혼희망타운 전용 등 자격 제한 정보
                "extra_info": f"전용 {area}㎡ | 미분양 {unsold}호 | 주택가격 {price}천원 | 문의 {contact}",
            })
        return parsed

    try:
        # 1단계: 엑셀 다운로드 시도
        excel_resp = requests.get(excel_url, headers=hdrs, timeout=15)
        ct = excel_resp.headers.get("content-type", "")
        if excel_resp.ok and ("excel" in ct or "spreadsheet" in ct or "octet-stream" in ct):
            try:
                import io, openpyxl
                wb = openpyxl.load_workbook(io.BytesIO(excel_resp.content), data_only=True)
                ws = wb.active
                rows_data = []
                for i, row in enumerate(ws.iter_rows(values_only=True)):
                    if i == 0:
                        continue  # 헤더 스킵
                    rows_data.append([str(c) if c is not None else "" for c in row])
                results = _parse_rows(rows_data)
                print(f"LH 선착순 계약 엑셀 {len(results)}건 수집 완료")
                return results
            except Exception as xe:
                print(f"엑셀 파싱 실패({xe}), HTML로 대체")

        # 2단계: HTML 테이블 파싱
        resp = requests.get(list_url, headers=hdrs, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        table = soup.find("table")
        if not table:
            print("LH 선착순 테이블 없음")
            return results
        rows_data = []
        for row in table.find_all("tr")[1:]:
            cols = [td.get_text(" ", strip=True) for td in row.find_all("td")]
            rows_data.append(cols)
        results = _parse_rows(rows_data)
        print(f"LH 선착순 계약 HTML {len(results)}건 수집 완료")
    except Exception as e:
        print(f"LH 선착순 수집 실패: {e}")
    return results


def fetch_apt_announcements():
    """
    청약 공고 수집 — 우선순위:
    1. 청약홈 분양정보 목록 페이지 직접 스크래핑 (현재 진행 중인 전체 분양 단지)
    2. LH 선착순(수의)계약 + 무순위(줍줍) API
    3. 청약홈 당일 접수 일정 (fallback)
    4. 공공데이터 API (30일)
    """
    INVALID_NAMES = {"APT 잔여세대", "잔여세대", "APT", "아파트", ""}

    # ── 1순위: 청약홈 분양정보 목록 (현재 분양 중인 단지 전체) ──
    listings = fetch_applyhome_pblanc_list()
    if listings:
        print(f"청약홈 분양정보 {len(listings)}건 사용")
        return listings
    print("청약홈 분양정보 목록 실패 → 다음 소스로")

    # ── 2순위: LH 선착순(수의)계약 + 무순위(줍줍) API ──
    lh_remndr = fetch_lh_sunchaksuun()
    remndr    = fetch_apt_remndr()
    all_remndr = lh_remndr + remndr
    if all_remndr:
        print(f"줍줍 계열 {len(all_remndr)}건 사용 (LH {len(lh_remndr)}건 + 무순위 {len(remndr)}건)")
        return all_remndr

    # ── 3순위: 청약홈 당일 일정 ──
    today_schedule = fetch_applyhome_today_schedule()
    today_schedule = [
        a for a in today_schedule
        if a.get("house_nm", "").strip() not in INVALID_NAMES
        and len(a.get("house_nm", "").strip()) > 3
    ]
    if today_schedule:
        remndr_today = [a for a in today_schedule if a.get("is_remndr")]
        others_today = [a for a in today_schedule if not a.get("is_remndr")]
        combined = remndr_today + others_today
        print(f"당일 일정 {len(combined)}건 사용")
        return combined
    print("당일 일정 없음 → 다음 소스로")

    # ── 4순위: odcloud 청약홈 분양정보 API (30일 범위) ──
    print("청약홈 페이지 스크래핑 실패 → odcloud 청약홈 분양정보 API 시도...")
    today = datetime.now()
    month_ago = today - timedelta(days=30)
    KEY = PUBLIC_DATA_API_KEY_APT
    _s = month_ago.strftime("%Y%m%d")
    _e = today.strftime("%Y%m%d")
    raw_url = (
        f"https://api.odcloud.kr/api/ApplyhomeInfoDetailSvc/v1/getAPTLttotPblancList"
        f"?serviceKey={KEY}&startSubscrptDate={_s}&endSubscrptDate={_e}&perPage=10&page=1"
    )
    announcements = []
    try:
        resp = requests.get(raw_url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        # odcloud 응답: {"data": [...]} 또는 표준 공공API 구조
        if "data" in data:
            items = data["data"] if isinstance(data["data"], list) else []
        else:
            items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
            if isinstance(items, dict):
                items = [items]
        for item in items:
            def _g(*keys):
                for k in keys:
                    v = item.get(k)
                    if v: return str(v)
                return ""
            announcements.append({
                "house_nm":             _g("HOUSE_NM", "houseNm", "house_nm"),
                "region":               _g("SUBSCRPT_AREA_CODE_NM", "subscrptAreaCodeNm", "subscrpt_area_code_nm"),
                "supply_cnt":           _g("TOT_SUPLY_HSHLDCO", "totSuplyHshldco", "tot_suply_hshldco"),
                "rcrit_pblanc_de":      _g("RCRIT_PBLANC_DE", "rcritPblancDe", "rcrit_pblanc_de"),
                "subscrpt_rcept_bgnde": _g("SPSPLY_RCEPT_BGNDE", "GNRL_RNK1_CRSPAREA_RCPTDE", "RCEPT_BGNDE"),
                "subscrpt_rcept_endde": _g("RCEPT_ENDDE", "SUBSCRPT_RCEPT_ENDDE"),
                "przwner_presnatn_de":  _g("PRZWNER_PRESNATN_DE", "przwnerPresnatnDe", "przwner_presnatn_de"),
                "cntrct_cncls_bgnde":   _g("CNTRCT_CNCLS_BGNDE", "cntrctCnclsBgnde", "cntrct_cncls_bgnde"),
                "house_secd_nm":        _g("HOUSE_SECD_NM", "houseSecdNm", "house_secd_nm"),
                "house_dtl_secd_nm":    _g("HOUSE_DTL_SECD_NM", "houseDtlSecdNm", "house_dtl_secd_nm"),
                "bsns_mby_nm":          _g("BSNS_MBY_NM", "bsnsMbyNm", "bsns_mby_nm"),
                "hssply_adres":         _g("HSSPLY_ADRES", "hssplyAdres", "hssply_adres"),
                "pblanc_url":           _g("PBLANC_URL", "HMPG_ADRES", "pblancUrl", "pblanc_url"),
                "speclt_rdn_earth_at":  _g("SPECLT_RDN_EARTH_AT", "specltRdnEarthAt", "speclt_rdn_earth_at"),
                "mdat_trget_area_secd": _g("MDAT_TRGET_AREA_SECD", "mdatTrgetAreaSecd", "mdat_trget_area_secd"),
                "parcprc_uls_at":       _g("PARCPRC_ULS_AT", "parcprcUlsAt", "parcprc_uls_at"),
            })
        print(f"odcloud 청약홈 API 청약 공고 {len(announcements)}건 수집 완료")
    except Exception as e:
        print(f"odcloud 청약홈 API 호출 실패: {e}")

    def sort_key(a):
        return a.get("rcrit_pblanc_de", "") or ""
    combined = sorted(remndr, key=sort_key, reverse=True) + sorted(announcements, key=sort_key, reverse=True)
    if combined:
        print(f"전체 공고 {len(combined)}건")
        return combined

    # ── 5순위: 네이버 부동산 분양 ──
    print("모든 공공 소스 실패 → 네이버 부동산 분양 정보로 대체...")
    naver_listings = fetch_naver_land_presale()
    if naver_listings:
        print(f"네이버 분양 {len(naver_listings)}건으로 대체")
        return naver_listings

    print("모든 분양 공고 소스 실패")
    return []


def fetch_apt_news():
    """네이버 청약/분양 뉴스 크롤링"""
    print("네이버 청약/분양 뉴스 수집 중...")
    hdrs = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "ko-KR,ko;q=0.9",
    }
    articles = []
    search_urls = [
        # 줍줍/무순위 최우선
        "https://search.naver.com/search.naver?where=news&query=무순위+줍줍+아파트&sort=1&nso=so%3Add%2Cp%3A3d",
        "https://search.naver.com/search.naver?where=news&query=아파트+무순위+청약&sort=1&nso=so%3Add%2Cp%3A3d",
        # 신규 단지 분양
        "https://search.naver.com/search.naver?where=news&query=신규+아파트+분양+단지&sort=1&nso=so%3Add%2Cp%3A3d",
        "https://search.naver.com/search.naver?where=news&query=아파트+분양+청약&sort=1&nso=so%3Add%2Cp%3A1d",
        # 일반 청약
        "https://search.naver.com/search.naver?where=news&query=아파트+청약&sort=1&nso=so%3Add%2Cp%3A1d",
    ]
    seen_titles = set()

    # 네이버 뉴스 선택자 후보 (HTML 구조 변경 대응)
    ITEM_SELECTORS   = ["ul.list_news > li", "div.news_wrap", "li.bx", "div.bx", "div.news_area"]
    TITLE_SELECTORS  = [
        "a.news_tit", "a.title", "a[class*='news_tit']",
        "a[class*='tit']", "a.title_link", "a.tit",
    ]
    DESC_SELECTORS   = ["div.news_dsc", "div.dsc_wrap", "div[class*='dsc']", "div[class*='desc']"]
    PRESS_SELECTORS  = ["a.info.press", "a.press", "span.press", "span.info.press"]

    def try_select(soup, selectors):
        for sel in selectors:
            result = soup.select(sel)
            if result:
                return result
        return []

    def try_select_one(el, selectors):
        for sel in selectors:
            result = el.select_one(sel)
            if result:
                return result
        return None

    def find_title_tag(item):
        """title selector 실패 시 href가 있는 첫 번째 <a> 태그로 fallback"""
        tag = try_select_one(item, TITLE_SELECTORS)
        if tag:
            return tag
        for a in item.find_all("a", href=True):
            text = a.get_text(strip=True)
            if len(text) > 8:
                return a
        return None

    for url in search_urls:
        try:
            resp = requests.get(url, headers=hdrs, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            items = try_select(soup, ITEM_SELECTORS)
            print(f"  선택자로 {len(items)}개 항목 발견 (URL: {url[-40:]})")
            found_in_url = 0
            for item in items:
                title_tag = find_title_tag(item)
                desc_tag  = try_select_one(item, DESC_SELECTORS)
                press_tag = try_select_one(item, PRESS_SELECTORS)
                if not title_tag:
                    continue
                title   = title_tag.text.strip()
                link    = title_tag.get("href", "")
                summary = desc_tag.text.strip() if desc_tag else ""
                press   = press_tag.text.strip() if press_tag else ""
                if not title or title in seen_titles:
                    continue
                if any(ex in title for ex in EXCLUDE_KEYWORDS):
                    continue
                if any(kw in (title + summary) for kw in APT_KEYWORDS):
                    seen_titles.add(title)
                    articles.append({"title": title, "url": link, "summary": summary, "press": press})
                    found_in_url += 1
            if found_in_url == 0 and items:
                print(f"  ⚠ 항목은 찾았으나 제목 추출 실패 (선택자 불일치 가능성)")
        except Exception as e:
            print(f"뉴스 크롤링 실패: {e}")
        except Exception as e:
            print(f"뉴스 크롤링 실패: {e}")

    # 포털 부동산 분양 광고/단지 정보 추가 수집
    portal_articles = fetch_portal_apt_listings()
    # 줍줍/무순위 기사 앞으로 정렬
    def remndr_priority(a):
        title = a.get("title", "")
        return 0 if any(k in title for k in ["무순위", "줍줍", "잔여", "미분양"]) else 1
    articles.sort(key=remndr_priority)
    articles = (portal_articles + articles)[:15]  # 포털 정보 앞에 배치

    print(f"청약/분양 뉴스+포털 {len(articles)}건 수집 완료")
    return articles


def fetch_naver_land_presale():
    """
    네이버 부동산 분양 API에서 현재 분양 중인 아파트 단지 목록 수집.
    반환값: [{"house_nm", "region", "hssply_adres", "supply_cnt", "pblanc_url", ...}, ...]
    """
    print("네이버 부동산 분양 API 수집 중...")
    hdrs = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "ko-KR,ko;q=0.9",
        "Referer": "https://new.land.naver.com/",
    }
    results = []

    # Stage 1: Naver Land 신규 분양 API (JSON)
    api_candidates = [
        "https://new.land.naver.com/api/complexes/presale?complexCategory=APT&page=1&pageSize=10",
        "https://new.land.naver.com/api/articles?tradeType=B1&realEstateType=APT&page=1&pageSize=10",
        "https://fin.land.naver.com/api/v1/complexes/presale?page=1&pageSize=10&complexCategory=APT",
    ]
    for api_url in api_candidates:
        try:
            resp = requests.get(api_url, headers=hdrs, timeout=12)
            print(f"  Naver Land API {api_url.split('?')[0].split('/')[-1]}: {resp.status_code}, len={len(resp.text)}")
            if resp.status_code != 200:
                continue
            data = resp.json()
            # 응답 구조 파악용 로그
            print(f"  응답 키: {list(data.keys()) if isinstance(data, dict) else type(data)}")
            items = []
            if isinstance(data, dict):
                for key in ["complexList", "articleList", "list", "result", "data", "items"]:
                    if key in data:
                        items = data[key]
                        break
                if not items and "result" in data and isinstance(data["result"], dict):
                    for key in ["complexList", "list", "items"]:
                        if key in data["result"]:
                            items = data["result"][key]
                            break
            elif isinstance(data, list):
                items = data

            print(f"  파싱된 단지 수: {len(items)}")
            for item in items[:10]:
                if not isinstance(item, dict):
                    continue
                # 필드명 후보들 (API마다 다를 수 있음)
                name = (item.get("complexName") or item.get("houseNm") or
                        item.get("name") or item.get("aptName") or "")
                addr = (item.get("address") or item.get("roadAddress") or
                        item.get("hssplyAdres") or item.get("location") or "")
                area = (item.get("cortarAddress") or item.get("region") or
                        item.get("sido") or "")
                cnt  = (item.get("householdCount") or item.get("supplyCnt") or
                        item.get("totalHousehold") or "")
                url  = (item.get("landUrl") or item.get("pblancUrl") or
                        item.get("saleUrl") or "")
                price = (item.get("minPrice") or item.get("price") or
                         item.get("fromPrice") or "")
                move_in = (item.get("moveInDate") or item.get("occupancyDate") or
                           item.get("expectedMoveInDate") or "")
                if not name:
                    continue
                if url and not url.startswith("http"):
                    url = "https://new.land.naver.com" + url
                results.append({
                    "house_nm":      name,
                    "region":        area,
                    "hssply_adres":  addr,
                    "supply_cnt":    str(cnt),
                    "pblanc_url":    url or "https://new.land.naver.com/",
                    "extra_info":    f"분양가 {price} | 입주예정 {move_in}" if price or move_in else "",
                    "house_secd_nm": "민간분양",
                    "is_remndr":     False,
                    "subs_category": "네이버부동산",
                })
            if results:
                print(f"네이버 부동산 API로 {len(results)}건 수집")
                return results
        except Exception as e:
            print(f"  Naver Land API 실패: {e}")

    # Stage 2: Naver 검색 HTML에서 분양 단지 파싱
    print("  Naver Land API 불가 → 검색 HTML 파싱 시도...")
    search_hdrs = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept-Language": "ko-KR,ko;q=0.9",
        "Referer": "https://www.naver.com/",
    }
    search_urls = [
        "https://search.naver.com/search.naver?where=web&query=네이버+부동산+분양+아파트+2026&nso=so%3Add%2Cp%3A7d",
        "https://search.naver.com/search.naver?where=web&query=아파트+분양+단지+입주+2026&nso=so%3Add%2Cp%3A7d",
        "https://search.naver.com/search.naver?where=news&query=아파트+분양+단지+입주&sort=1&nso=so%3Add%2Cp%3A3d",
    ]
    seen = set()
    for url in search_urls:
        try:
            resp = requests.get(url, headers=search_hdrs, timeout=10)
            if resp.status_code != 200:
                print(f"  검색 URL {resp.status_code}: {url[:60]}")
                continue
            soup = BeautifulSoup(resp.text, "html.parser")

            # 분양 단지 카드 또는 뉴스 항목에서 추출
            for block in soup.select("li.bx, div.news_wrap, div.total_wrap li, div.api_subject_bx"):
                # 제목/링크 추출
                a_tag = None
                for sel in ["a.news_tit", "a.title_link", "a[class*='tit']", "a[href]"]:
                    a_tag = block.select_one(sel)
                    if a_tag and len(a_tag.get_text(strip=True)) > 5:
                        break
                if not a_tag:
                    continue
                title = a_tag.get_text(strip=True)
                link  = a_tag.get("href", "")
                desc_tag = block.select_one("a.api_txt_lines, div.dsc_wrap a, p.dsc_txt_wrap")
                desc  = desc_tag.get_text(strip=True) if desc_tag else ""

                if not title or title in seen:
                    continue
                if not any(kw in (title + desc) for kw in ["분양", "아파트", "청약", "단지"]):
                    continue
                if any(ex in title for ex in EXCLUDE_KEYWORDS):
                    continue

                seen.add(title)
                # 뉴스 기반이므로 announcement 구조로 변환 (generate_apt_article에서 활용)
                results.append({
                    "house_nm":      title[:40],
                    "region":        "",
                    "hssply_adres":  "",
                    "supply_cnt":    "",
                    "pblanc_url":    link or "https://www.applyhome.co.kr",
                    "extra_info":    desc[:200] if desc else "",
                    "house_secd_nm": "민간분양",
                    "is_remndr":     any(k in title for k in ["무순위", "줍줍", "잔여"]),
                    "subs_category": "네이버검색",
                })
            if results:
                break
        except Exception as e:
            print(f"  검색 HTML 파싱 실패: {e}")

    print(f"네이버 분양 검색 {len(results)}건 수집")
    return results[:5]


def fetch_portal_apt_listings():
    """
    네이버 부동산 분양 정보 + 청약홈 분양 목록 페이지 크롤링
    줍줍/무순위/신규단지 우선 수집 (청약뉴스용 뉴스 리스트 형식)
    """
    print("포털 부동산 분양 광고/단지 정보 수집 중...")
    hdrs = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "ko-KR,ko;q=0.9",
        "Referer": "https://www.naver.com",
    }
    listings = []
    seen = set()

    portal_urls = [
        "https://search.naver.com/search.naver?where=web&query=아파트+무순위+줍줍+2026&nso=so%3Add%2Cp%3A7d",
        "https://search.naver.com/search.naver?where=web&query=신규+아파트+분양+단지+청약+공고&nso=so%3Add%2Cp%3A7d",
        "https://search.naver.com/search.naver?where=web&query=청약홈+분양+공고+2026&nso=so%3Add%2Cp%3A7d",
    ]

    TITLE_SELECTORS = ["a.tit_site", "a.link_tit", "a.total_tit", "h3.tit a", "div.title_area a"]
    DESC_SELECTORS  = ["a.dsc_site", "span.total_dsc", "p.dsc_txt", "div.desc a"]

    def try_one(el, sels):
        for s in sels:
            r = el.select_one(s)
            if r:
                return r
        return None

    for url in portal_urls:
        try:
            resp = requests.get(url, headers=hdrs, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            for block in soup.select("li.bx, div.total_wrap, div.site_area li"):
                title_tag = try_one(block, TITLE_SELECTORS)
                desc_tag  = try_one(block, DESC_SELECTORS)
                if not title_tag:
                    continue
                title = title_tag.text.strip()
                link  = title_tag.get("href", "")
                desc  = desc_tag.text.strip() if desc_tag else ""
                if not title or title in seen:
                    continue
                if any(ex in title for ex in EXCLUDE_KEYWORDS):
                    continue
                if any(kw in (title + desc) for kw in APT_KEYWORDS + ["무순위", "줍줍", "신규단지", "분양공고"]):
                    seen.add(title)
                    listings.append({"title": title, "url": link, "summary": desc, "press": "포털"})
        except Exception as e:
            print(f"포털 분양 수집 실패: {e}")

    def priority(a):
        return 0 if any(k in a.get("title", "") for k in ["무순위", "줍줍", "잔여", "미분양"]) else 1
    listings.sort(key=priority)
    print(f"포털 분양 단지 정보 {len(listings)}건 수집 완료")
    return listings[:5]


def fetch_molit_policy():
    """
    국토교통부 보도자료 크롤링 — 청약/분양 관련 신규 정책 감지
    반환값: {"title": ..., "url": ..., "date": ..., "summary": ...} or None
    """
    print("국토교통부 보도자료 확인 중...")
    hdrs = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    url = "https://www.molit.go.kr/USR/NEWS/m_71/lst.jsp"
    today = datetime.now().strftime("%Y%m%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")

    try:
        resp = requests.get(url, headers=hdrs, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        for row in soup.select("table tbody tr"):
            cols = row.select("td")
            if len(cols) < 3:
                continue

            title_tag = row.select_one("td.subject a") or row.select_one("td a")
            if not title_tag:
                continue

            title = title_tag.text.strip()
            href  = title_tag.get("href", "")
            date_text = cols[-1].text.strip().replace("-", "").replace(".", "")

            # 오늘 또는 어제 발행된 보도자료만
            if date_text not in [today, yesterday]:
                continue

            # 정책 키워드 포함 여부 확인
            if not any(kw in title for kw in POLICY_KEYWORDS):
                continue

            full_url = href if href.startswith("http") else f"https://www.molit.go.kr{href}"

            # 본문 요약 크롤링 시도
            summary = ""
            try:
                detail = requests.get(full_url, headers=hdrs, timeout=10)
                detail.raise_for_status()
                detail_soup = BeautifulSoup(detail.text, "html.parser")
                body = detail_soup.select_one("div.view_con") or detail_soup.select_one("div.content")
                if body:
                    summary = body.text.strip()[:1000]
            except Exception:
                pass

            print(f"신규 부동산 정책 감지: {title}")
            return {"title": title, "url": full_url, "date": date_text, "summary": summary}

    except Exception as e:
        print(f"국토부 보도자료 크롤링 실패: {e}")

    return None


def get_guide_topic_from_announcement(announcement):
    """
    당일 공고 특성을 분석해서 연계 가이드 주제 반환
    """
    topics = []

    if announcement.get("speclt_rdn_earth_at") == "Y":
        topics.append("투기과열지구 청약 자격과 대출 제한 완전 정리")
    if announcement.get("mdat_trget_area_secd") == "Y":
        topics.append("조정대상지역 1순위 청약 조건과 전매 제한 기간")
    if announcement.get("parcprc_uls_at") == "Y":
        topics.append("분양가상한제 단지의 전매 제한과 실거주 의무")

    house_type = announcement.get("house_secd_nm", "")
    if "국민" in house_type:
        topics.append("공공분양과 민간분양 차이 — 자격·가격·전매 비교")
    if "공공" in house_type:
        topics.append("사전청약 제도 개념과 일반청약과의 차이점")

    return topics[0] if topics else None


def get_rotation_topic():
    """날짜 기반 로테이션 주제 반환"""
    day_of_year = datetime.now().timetuple().tm_yday
    idx = day_of_year % len(GUIDE_ROTATION_TOPICS)
    return GUIDE_ROTATION_TOPICS[idx]


# ==========================================
# HTML 구조 가이드 (공통)
# ==========================================
def build_apt_html_guide(top_url: str, top_btn: str, bottom_url: str, bottom_btn: str, ref_url: str, ref_name: str):
    return f"""
[HTML 구조 — 반드시 이 순서, 이 스타일 그대로. 절대 생략 금지]

--- 1. 카테고리 뱃지 ---
<div style="display:inline-block;background:{CAT_LIGHT_BG};color:{CAT_COLOR};font-size:13px;font-weight:700;padding:4px 14px;border-radius:20px;margin-bottom:14px;">[카테고리명] · [서브라벨]</div>

--- 2. 서브 제목 (H1 절대 금지) ---
<div style="font-size:clamp(22px,4vw,28px);font-weight:800;color:#1e293b;margin:0 0 8px 0;line-height:1.4;">[서브 문구]</div>

--- 3. 핵심 정보 요약 박스 ---
<div style="background:#f8fafc;padding:28px 30px;border-radius:16px;border:1px solid #e2e8f0;margin-bottom:40px;">
  <p style="margin-top:0;font-size:13px;font-weight:700;color:#94a3b8;letter-spacing:0.08em;margin-bottom:16px;">한눈에 보기</p>
  <ul style="list-style:none !important;padding:0 !important;margin:0 0 24px 0 !important;">
    <li style="display:flex;align-items:flex-start;gap:12px;font-size:15px;color:#334155;line-height:1.8;margin-bottom:10px;list-style:none;"><span style="display:inline-block;width:6px;height:6px;min-width:6px;background:{CAT_COLOR};border-radius:50%;margin-top:9px;flex-shrink:0;"></span><span style="flex:1;">[핵심 정보 1]</span></li>
    <li style="display:flex;align-items:flex-start;gap:12px;font-size:15px;color:#334155;line-height:1.8;margin-bottom:10px;list-style:none;"><span style="display:inline-block;width:6px;height:6px;min-width:6px;background:{CAT_COLOR};border-radius:50%;margin-top:9px;flex-shrink:0;"></span><span style="flex:1;">[핵심 정보 2]</span></li>
    <li style="display:flex;align-items:flex-start;gap:12px;font-size:15px;color:#334155;line-height:1.8;list-style:none;"><span style="display:inline-block;width:6px;height:6px;min-width:6px;background:{CAT_COLOR};border-radius:50%;margin-top:9px;flex-shrink:0;"></span><span style="flex:1;">[핵심 정보 3]</span></li>
  </ul>
  <hr style="border:none;border-top:1px solid #e2e8f0;margin:0 0 20px 0;">
  <div style="display:flex;flex-wrap:wrap;gap:8px;">
    <span style="background:{CAT_LIGHT_BG};color:{CAT_COLOR};font-size:12px;font-weight:600;padding:4px 12px;border-radius:20px;">#[키워드1]</span>
    <span style="background:{CAT_LIGHT_BG};color:{CAT_COLOR};font-size:12px;font-weight:600;padding:4px 12px;border-radius:20px;">#[키워드2]</span>
    <span style="background:{CAT_LIGHT_BG};color:{CAT_COLOR};font-size:12px;font-weight:600;padding:4px 12px;border-radius:20px;">#[키워드3]</span>
  </div>
</div>

--- 4. 핵심 3가지 박스 ---
<div style="background:#064e3b;border-radius:16px;padding:28px 30px;margin-bottom:32px;">
  <p style="margin:0 0 16px 0;font-size:15px;font-weight:700;color:#ffffff !important;letter-spacing:0.08em;">핵심 3가지</p>
  <ul style="list-style:none;padding:0;margin:0;">
    <li style="display:flex;align-items:flex-start;gap:12px;margin-bottom:12px;"><span style="display:inline-block;background:#10b981;color:#fff;font-size:12px;font-weight:800;padding:2px 8px;border-radius:4px;flex-shrink:0;margin-top:2px;">01</span><span style="font-size:15px;color:#ffffff;line-height:1.7;">[핵심 포인트 1]</span></li>
    <li style="display:flex;align-items:flex-start;gap:12px;margin-bottom:12px;"><span style="display:inline-block;background:#10b981;color:#fff;font-size:12px;font-weight:800;padding:2px 8px;border-radius:4px;flex-shrink:0;margin-top:2px;">02</span><span style="font-size:15px;color:#ffffff;line-height:1.7;">[핵심 포인트 2]</span></li>
    <li style="display:flex;align-items:flex-start;gap:12px;"><span style="display:inline-block;background:#10b981;color:#fff;font-size:12px;font-weight:800;padding:2px 8px;border-radius:4px;flex-shrink:0;margin-top:2px;">03</span><span style="font-size:15px;color:#ffffff;line-height:1.7;">[핵심 포인트 3]</span></li>
  </ul>
</div>

--- 5. 상단 CTA (이 HTML을 그대로 복사, URL·텍스트 절대 수정 금지) ---
<div style="text-align:center;margin:36px 0;"><div style="display:inline-block;background:#10b981;border-radius:8px;box-shadow:0 4px 12px rgba(16,185,129,0.25);padding:14px 32px;line-height:1;"><a href="{top_url}" target="_blank" rel="noopener noreferrer" style="color:#fff;font-size:15px;font-weight:700;text-decoration:none;line-height:1;display:inline;vertical-align:middle;">{top_btn}</a></div></div>

--- 5-1. 광고 슬롯 A (상단 CTA 아래, 본문 시작 전 — 이 HTML을 그대로 복사, 절대 수정 금지) ---
<div style="margin:32px 0;">
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-6858780475640766" crossorigin="anonymous"></script>
<ins class="adsbygoogle" style="display:block" data-ad-client="ca-pub-6858780475640766" data-ad-slot="1825484842" data-ad-format="auto" data-full-width-responsive="true"></ins>
<script>(adsbygoogle = window.adsbygoogle || []).push({{}});</script>
</div>

--- 6. 본문 섹션 3개 (절대 생략 금지) ---

각 섹션은 아래 구조를 따른다:
<div style="margin-bottom:56px;padding-top:40px;border-top:1px solid #e2e8f0;">
  <h2 style="font-size:clamp(18px,3vw,22px);font-weight:800;color:#1e293b;margin:0 0 8px 0;line-height:1.4;">[제목]</h2>
  <p style="font-size:15px;color:#94a3b8;font-weight:600;margin:0 0 20px 0;">[서브 문구]</p>
  <p style="font-size:15px;color:#334155;line-height:1.9;margin-bottom:16px;">[핵심 내용 1~2줄 서술 — 이 섹션에서 말하려는 핵심 한 문장]</p>
  [아래 콘텐츠 컴포넌트 중 내용 성격에 맞게 선택하여 삽입]
</div>

[콘텐츠 컴포넌트 선택 기준 — 내용 성격에 따라 Claude가 판단]

▶ 항목 나열·조건·체크리스트 → 글머리기호 박스
<div style="background:#f8fafc;border-radius:12px;padding:20px 24px;margin:16px 0;">
  <ul style="list-style:none;padding:0;margin:0;">
    <li style="display:flex;align-items:flex-start;gap:10px;font-size:14px;color:#334155;line-height:1.8;margin-bottom:8px;"><span style="color:{CAT_COLOR};font-weight:800;flex-shrink:0;">✓</span><span>[항목 내용]</span></li>
    <li style="display:flex;align-items:flex-start;gap:10px;font-size:14px;color:#334155;line-height:1.8;margin-bottom:8px;"><span style="color:{CAT_COLOR};font-weight:800;flex-shrink:0;">✓</span><span>[항목 내용]</span></li>
    <li style="display:flex;align-items:flex-start;gap:10px;font-size:14px;color:#334155;line-height:1.8;"><span style="color:{CAT_COLOR};font-weight:800;flex-shrink:0;">✓</span><span>[항목 내용]</span></li>
  </ul>
</div>

▶ 비교·조건 대조 → 2열 비교 표
<div style="overflow-x:auto;margin:16px 0;">
  <table style="width:100%;border-collapse:collapse;font-size:14px;">
    <thead><tr style="background:{CAT_COLOR};color:#fff;">
      <th style="padding:11px 14px;text-align:center;font-weight:700;">[구분]</th>
      <th style="padding:11px 14px;text-align:center;font-weight:700;">[항목A]</th>
      <th style="padding:11px 14px;text-align:center;font-weight:700;">[항목B]</th>
    </tr></thead>
    <tbody>
      <tr style="border-bottom:1px solid #e2e8f0;"><td style="padding:11px 14px;text-align:center;color:#64748b;font-weight:600;">[행 라벨]</td><td style="padding:11px 14px;text-align:center;color:#334155;">[값A]</td><td style="padding:11px 14px;text-align:center;color:#334155;">[값B]</td></tr>
      <tr style="border-bottom:1px solid #e2e8f0;background:#f8fafc;"><td style="padding:11px 14px;text-align:center;color:#64748b;font-weight:600;">[행 라벨]</td><td style="padding:11px 14px;text-align:center;color:#334155;">[값A]</td><td style="padding:11px 14px;text-align:center;color:#334155;">[값B]</td></tr>
    </tbody>
  </table>
</div>

▶ 절차·순서·타임라인 → 스텝 박스
<div style="margin:16px 0;">
  <div style="display:flex;align-items:flex-start;gap:14px;margin-bottom:12px;">
    <div style="display:flex;flex-direction:column;align-items:center;flex-shrink:0;"><span style="background:{CAT_COLOR};color:#fff;font-size:12px;font-weight:800;width:28px;height:28px;border-radius:50%;display:flex;align-items:center;justify-content:center;">1</span><div style="width:2px;height:24px;background:{CAT_LIGHT_BORDER};margin-top:4px;"></div></div>
    <div style="padding-top:4px;"><p style="margin:0 0 4px 0;font-size:14px;font-weight:700;color:#1e293b;">[단계명]</p><p style="margin:0;font-size:14px;color:#334155;line-height:1.7;">[단계 설명 1~2줄]</p></div>
  </div>
  <div style="display:flex;align-items:flex-start;gap:14px;margin-bottom:12px;">
    <div style="display:flex;flex-direction:column;align-items:center;flex-shrink:0;"><span style="background:{CAT_COLOR};color:#fff;font-size:12px;font-weight:800;width:28px;height:28px;border-radius:50%;display:flex;align-items:center;justify-content:center;">2</span><div style="width:2px;height:24px;background:{CAT_LIGHT_BORDER};margin-top:4px;"></div></div>
    <div style="padding-top:4px;"><p style="margin:0 0 4px 0;font-size:14px;font-weight:700;color:#1e293b;">[단계명]</p><p style="margin:0;font-size:14px;color:#334155;line-height:1.7;">[단계 설명 1~2줄]</p></div>
  </div>
  <div style="display:flex;align-items:flex-start;gap:14px;">
    <div style="flex-shrink:0;"><span style="background:{CAT_COLOR};color:#fff;font-size:12px;font-weight:800;width:28px;height:28px;border-radius:50%;display:flex;align-items:center;justify-content:center;">3</span></div>
    <div style="padding-top:4px;"><p style="margin:0 0 4px 0;font-size:14px;font-weight:700;color:#1e293b;">[단계명]</p><p style="margin:0;font-size:14px;color:#334155;line-height:1.7;">[단계 설명 1~2줄]</p></div>
  </div>
</div>

▶ 경고·주의·부적격 사례 → 주의사항 박스
<div style="background:#fef9c3;border-left:4px solid #eab308;border-radius:0 12px 12px 0;padding:16px 20px;margin:16px 0;">
  <p style="margin:0 0 8px 0;font-size:13px;font-weight:800;color:#854d0e;">⚠ 주의사항</p>
  <ul style="list-style:none;padding:0;margin:0;">
    <li style="font-size:14px;color:#334155;line-height:1.8;margin-bottom:6px;">· [주의 항목 1]</li>
    <li style="font-size:14px;color:#334155;line-height:1.8;margin-bottom:6px;">· [주의 항목 2]</li>
    <li style="font-size:14px;color:#334155;line-height:1.8;">· [주의 항목 3]</li>
  </ul>
</div>

▶ 핵심 수치·기준·포인트 강조 → 인포 박스
※ 키:값 항목은 반드시 한 <li> 안에 <strong>키</strong> 값 형태로 작성 — display:flex 또는 별도 <span>/<div>로 분리 절대 금지 (모바일 줄바꿈 방지)
<div style="background:{CAT_LIGHT_BG};border:1px solid {CAT_LIGHT_BORDER};border-radius:12px;padding:16px 20px;margin:16px 0;">
  <p style="margin:0 0 8px 0;font-size:13px;font-weight:800;color:{CAT_DARK};">📌 핵심 포인트</p>
  <ul style="list-style:none;padding:0;margin:0;">
    <li style="font-size:14px;color:#334155;line-height:1.8;margin-bottom:6px;">· <strong>[키]</strong> [값]</li>
    <li style="font-size:14px;color:#334155;line-height:1.8;margin-bottom:6px;">· <strong>[키]</strong> [값]</li>
    <li style="font-size:14px;color:#334155;line-height:1.8;">· <strong>[키]</strong> [값]</li>
  </ul>
</div>

강조 문장 (본문 내 인라인):
<span style="background-color:{CAT_LIGHT_BG};padding:2px 6px;color:{CAT_COLOR};font-weight:700;">[강조 문장]</span>

--- 7. 청약 일정 표 (분양정보 전용) ---
<div style="overflow-x:auto;margin:24px 0;"><table style="width:100%;border-collapse:collapse;font-size:14px;"><thead><tr style="background:{CAT_COLOR};color:#fff;"><th style="padding:12px;text-align:center;font-weight:700;">구분</th><th style="padding:12px;text-align:center;font-weight:700;">일정</th><th style="padding:12px;text-align:center;font-weight:700;">비고</th></tr></thead><tbody><tr style="border-bottom:1px solid #e2e8f0;"><td style="padding:12px;text-align:center;color:#334155;">모집공고일</td><td style="padding:12px;text-align:center;color:#334155;font-weight:700;">[날짜]</td><td style="padding:12px;text-align:center;color:#64748b;"></td></tr><tr style="border-bottom:1px solid #e2e8f0;background:#f8fafc;"><td style="padding:12px;text-align:center;color:#334155;">청약 접수</td><td style="padding:12px;text-align:center;color:#334155;font-weight:700;">[시작일] ~ [종료일]</td><td style="padding:12px;text-align:center;color:#64748b;">청약홈</td></tr><tr style="border-bottom:1px solid #e2e8f0;"><td style="padding:12px;text-align:center;color:#334155;">당첨자 발표</td><td style="padding:12px;text-align:center;color:#334155;font-weight:700;">[날짜]</td><td style="padding:12px;text-align:center;color:#64748b;"></td></tr><tr style="background:#f8fafc;"><td style="padding:12px;text-align:center;color:#334155;">계약 체결</td><td style="padding:12px;text-align:center;color:#334155;font-weight:700;">[날짜]</td><td style="padding:12px;text-align:center;color:#64748b;"></td></tr></tbody></table></div>

--- 8. 하단 CTA (이 HTML을 그대로 복사, URL·텍스트 절대 수정 금지) ---
<div style="text-align:center;margin:36px 0;"><div style="display:inline-block;background:#059669;border-radius:8px;box-shadow:0 4px 12px rgba(16,185,129,0.25);padding:14px 32px;line-height:1;"><a href="{bottom_url}" target="_blank" rel="noopener noreferrer" style="color:#fff;font-size:15px;font-weight:700;text-decoration:none;line-height:1;display:inline;vertical-align:middle;">{bottom_btn}</a></div></div>

--- 9. 3카드 요약 (3개 모두 완성) ---
<div style="margin-top:60px;padding-top:40px;border-top:2px dashed #cbd5e1;"><h3 style="text-align:center;color:#1e293b;margin-bottom:24px;font-size:20px;font-weight:800;">3줄 핵심 요약</h3><div style="display:flex;flex-wrap:wrap;gap:14px;padding-bottom:12px;"><div style="flex:1;min-width:200px;background:{CAT_LIGHT_BG};border:1px solid {CAT_LIGHT_BORDER};padding:20px;border-radius:18px;text-align:center;"><p style="margin:0;font-weight:800;color:{CAT_COLOR};font-size:15px;margin-bottom:8px;">[카드1 제목]</p><p style="margin:0;font-size:14px;color:#334155;line-height:1.6;">[카드1 내용]</p></div><div style="flex:1;min-width:200px;background:{CAT_LIGHT_BG};border:1px solid {CAT_LIGHT_BORDER};padding:20px;border-radius:18px;text-align:center;"><p style="margin:0;font-weight:800;color:{CAT_COLOR};font-size:15px;margin-bottom:8px;">[카드2 제목]</p><p style="margin:0;font-size:14px;color:#334155;line-height:1.6;">[카드2 내용]</p></div><div style="flex:1;min-width:200px;background:{CAT_LIGHT_BG};border:1px solid {CAT_LIGHT_BORDER};padding:20px;border-radius:18px;text-align:center;"><p style="margin:0;font-weight:800;color:{CAT_COLOR};font-size:15px;margin-bottom:8px;">[카드3 제목]</p><p style="margin:0;font-size:14px;color:#334155;line-height:1.6;">[카드3 내용]</p></div></div></div>

--- 10. 참고자료 (이 HTML을 그대로 복사, URL·출처명 절대 수정 금지) ---
<div style="margin-top:48px;padding:24px;background:#f8fafc;border-radius:12px;border:1px solid #e2e8f0;"><h4 style="margin:0 0 14px 0;color:#334155;font-size:16px;font-weight:700;">참고 자료</h4><ul style="list-style:none;padding:0;margin:0;font-size:14px;color:#334155;line-height:2.2;"><li><a href="{ref_url}" target="_blank" rel="noopener" style="color:{CAT_COLOR};text-decoration:none;">{ref_name}</a></li></ul></div>

--- 11. 광고 슬롯 C (면책조항 바로 위 — 이 HTML을 그대로 복사, 절대 수정 금지) ---
<div style="margin:32px 0;"><ins class="adsbygoogle" style="display:block" data-ad-format="autorelaxed" data-ad-client="ca-pub-6858780475640766" data-ad-slot="3873632172"></ins><script>(adsbygoogle = window.adsbygoogle || []).push({{}});</script></div>

--- 12. 면책조항 (맨 끝 필수) ---
<p style="margin-top:2em;font-size:13px;color:#94a3b8;">본 콘텐츠는 정보 제공 목적으로 작성되었습니다. 청약 신청 전 청약홈 공식 공고문을 반드시 확인하시기 바랍니다.</p>
"""

# ==========================================
# 카테고리별 작성 지침
# ==========================================

GUIDELINE_APT_INFO = """
[분양정보 작성 지침]
목적: 현재 분양 중인 아파트 단지에 대해 실수요자가 실질적으로 궁금해하는 정보를 균형 있고 솔직하게 제공.
단순 홍보가 아닌 입지 여건·가격 수준·단점까지 포함한 팩트 중심 단지 분석 글.

필수 포함 요소 (원문 데이터에 없으면 "청약홈 공고문 참조" 처리)
- 단지 개요: 단지명, 위치, 공급 세대수, 주택형(평형), 사업주체, 입주 예정 시기
- 입지 분석: 교통(역세권 여부·거리), 학군, 생활 인프라(마트·병원·공원 등), 개발 호재
- 가격 수준: 분양가(공급가격), 주변 기존 아파트 시세 대비 수준, 고분양가 여부 판단
- 줍줍(무순위·선착순) 해당 시: 잔여 물량, 신청 방법, 자격 제한 여부
- 단점 및 리스크: 교통 불편, 소음·환경 문제, 분양가 대비 입지, 미분양 우려 등 실질적 단점 지적
- 청약 자격: 1순위 조건, 특별공급 유형, 규제지역 여부
- 전망: 입주 후 시세 흐름 예상 근거 (호재·악재 기반, 단정하지 않고 근거 중심 서술)

섹션 구성
- 1. 단지 개요 및 입지 분석 → 인포 박스로 기본 정보 정리 + 교통·학군·인프라 서술
- 2. 분양가 & 시세 비교 → 표로 분양가와 주변 시세 비교, 줍줍 해당 시 신청 방법 포함
- [광고 슬롯 B — 섹션 2 종료 후 섹션 3 시작 전, 아래 HTML을 그대로 삽입, 절대 수정 금지]
<div style="margin:32px 0;"><ins class="adsbygoogle" style="display:block" data-ad-format="fluid" data-ad-layout-key="-5r+d2+3d-69+9m" data-ad-client="ca-pub-6858780475640766" data-ad-slot="9373370867"></ins><script>(adsbygoogle = window.adsbygoogle || []).push({{}});</script></div>
- 3. 단점·리스크와 투자 전망 → 주의사항 박스로 단점 명시 + 향후 가치 근거 중심 서술

가독성 규칙
- 각 섹션은 핵심 내용 1~2줄 서술 후 반드시 컴포넌트(박스/표/스텝) 1개 이상 사용
- 단점과 리스크는 반드시 포함할 것 — 장점만 나열하는 홍보성 글 금지
- 수치·시세는 원문 기반으로만 작성, 없으면 "시세 별도 확인 필요" 표기

절대 금지: 경매·공매·전세·월세·빌라·오피스텔 언급 / 원문에 없는 수치 생성 / 근거 없는 시세 예측 단정 / H1 태그
"""

GUIDELINE_APT_NEWS = """
[청약뉴스 작성 지침]
목적: 곧 분양 예정인 신규 단지 소개 또는 청약·부동산 제도 변경 이슈를 다뤄 실수요자가 미리 준비하고 대응할 수 있도록 정보 제공

다루는 주제 유형 (뉴스 내용에 따라 선택)
유형 A — 분양 예정 단지 소개
- 단지명·위치·예정 공급 세대수·예정 분양 시기
- 입지 특성(교통·학군·개발 호재), 예상 분양가 또는 시세 맥락
- 청약 자격 예상(규제지역·특별공급 유형), 관심 가져야 하는 이유

유형 B — 청약·부동산 제도 변경 이슈
- 변경 내용 요약: 무엇이 바뀌는지 구체적으로
- 시행 시기 및 적용 대상
- 실수요자에게 미치는 영향: 유리한 점·불리한 점 균형 있게
- 대응 방법: 변경 전·후로 취해야 할 행동

필수 공통 요소
- 핵심 내용을 먼저 한 문장으로 요약 (리드 문장)
- 실수요자 관점에서 왜 중요한지 맥락 설명
- 바로 실행 가능한 행동 지침 1~3가지

섹션 구성
- 1. 핵심 내용 요약 → 인포 박스로 핵심 팩트 정리
- 2. 상세 분석 → 표 또는 비교 박스로 수치·조건·변경 전후 정리
- [광고 슬롯 B — 섹션 2 종료 후 섹션 3 시작 전, 아래 HTML을 그대로 삽입, 절대 수정 금지]
<div style="margin:32px 0;"><ins class="adsbygoogle" style="display:block" data-ad-format="fluid" data-ad-layout-key="-5r+d2+3d-69+9m" data-ad-client="ca-pub-6858780475640766" data-ad-slot="9373370867"></ins><script>(adsbygoogle = window.adsbygoogle || []).push({{}});</script></div>
- 3. 실수요자 대응 전략 → 글머리기호 박스로 행동 지침 간결하게

가독성 규칙
- 각 섹션은 핵심 내용 1~2줄 서술 후 반드시 컴포넌트(박스/표) 1개 이상 사용
- 수치·날짜·조건은 반드시 표 또는 인포 박스로 시각화
- 행동 지침은 글머리기호 박스로 간결하게

절대 금지: 경매·공매·전세사기·빌라 언급 / 뉴스에 없는 수치 생성 / 단순 목록 나열 / H1 태그
"""

GUIDELINE_APT_GUIDE = """
[청약가이드 작성 지침]
목적: 청약 초보자부터 재도전자까지 실전 준비에 필요한 정보를 체계적·구체적으로 제공

필수 포함 요소 (주제에 따라 해당 항목 중심으로 선택)
- 청약통장 전략: 납입 기간·횟수·금액별 유불리, 1순위 자격 기준
- 가점 구조: 무주택 기간(최대 32점)·부양가족(최대 35점)·납입 기간(최대 17점)
- 특별공급 자격: 신혼부부/생애최초/다자녀/노부모 각 조건과 소득 기준
- 자금 계획: 계약금·중도금·잔금 단계별 납부 시기와 대출 한도
- 필수 서류: 공통 서류 + 유형별 추가 서류, 발급처, 유효기간
- 당첨 후 절차: 발표 확인→계약→중도금→입주 타임라인
- 주의사항: 부적격 당첨 사례, 청약 취소 시 제한 기간, 흔한 실수

섹션 구성
- 1. 핵심 자격 및 전략 → 1~2줄 서술 + 글머리기호 박스 또는 비교 표
- 2. 단계별 실전 가이드 → 스텝 박스로 절차·타임라인 시각화
- [광고 슬롯 B — 섹션 2 종료 후 섹션 3 시작 전, 아래 HTML을 그대로 삽입, 절대 수정 금지]
<div style="margin:32px 0;"><ins class="adsbygoogle" style="display:block" data-ad-format="fluid" data-ad-layout-key="-5r+d2+3d-69+9m" data-ad-client="ca-pub-6858780475640766" data-ad-slot="9373370867"></ins><script>(adsbygoogle = window.adsbygoogle || []).push({{}});</script></div>
- 3. 주의사항 및 자주 묻는 질문 → 주의사항 박스 + 인포 박스 조합

가독성 규칙
- 각 섹션은 핵심 내용 1~2줄 서술 후 반드시 컴포넌트(박스/표/스텝) 1개 이상 사용
- 절차·순서는 반드시 스텝 박스로 표현
- 주의사항·실수 사례는 반드시 주의사항 박스로 표현
- 자격 조건·기준은 글머리기호 박스 또는 표로 정리

절대 금지: 확인되지 않은 수치 생성 (소득 기준 등 → "청약홈 공고문 참조") / 경매·전세 언급 / H1 태그
"""

# ==========================================
# 중복 발행 방지 — published_history.json
# ==========================================
HISTORY_FILE = "published_history.json"

def load_history():
    """레포의 published_history.json 로드"""
    if os.path.exists(HISTORY_FILE):
        try:
            import json
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"히스토리 로드 실패: {e}")
    return {"apt-info": [], "apt-news": [], "apt-guide": []}

def save_history(history):
    """published_history.json 저장 (git commit은 yml에서 처리)"""
    import json
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
        print(f"히스토리 저장 완료")
    except Exception as e:
        print(f"히스토리 저장 실패: {e}")

def is_duplicate(history, category, key, days=60):
    """
    최근 days일 이내 동일 key가 발행된 적 있는지 확인.
    - LH 단지(key가 'LH '로 시작): 완전 일치만 중복 처리 (지역·블록이 달라도 LH가 공통이라 오탐 방지)
    - 일반 단지: 핵심 단어(4자 이상) 2개 이상 겹치면 중복
    """
    import re as _re
    STOP_WORDS = {"아파트", "분양", "단지", "블록", "지구", "국제화", "계획지구"}
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    records = history.get(category, [])

    def key_tokens(text):
        tokens = _re.split(r'[\s\-_·,()\[\]]+', text)
        return {t for t in tokens if len(t) >= 4 and t not in STOP_WORDS}

    is_lh_key = key.startswith("LH ")
    curr_tokens = key_tokens(key)

    for record in records:
        if record.get("date", "") < cutoff:
            continue
        past_key = record.get("key", "")
        # 완전 일치
        if past_key == key:
            print(f"중복 감지 [{category}]: 완전일치 '{key}'")
            return True
        # LH 단지는 완전 일치만 — 다른 LH 단지와 오탐 방지
        if is_lh_key or past_key.startswith("LH "):
            continue
        # 일반 단지: 고유 단어 2개 이상 겹치면 중복
        past_tokens = key_tokens(past_key)
        overlap = curr_tokens & past_tokens
        if len(overlap) >= 2:
            print(f"중복 감지 [{category}]: '{key}' → '{past_key}' (공통:{overlap})")
            return True
    return False

def record_history(history, category, key, title):
    """발행 이력 추가"""
    history.setdefault(category, []).append({
        "date":  datetime.now().strftime("%Y-%m-%d"),
        "key":   key,
        "title": title,
    })
    # 90일 이상 된 기록 자동 정리
    cutoff = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
    history[category] = [
        r for r in history[category] if r.get("date", "") >= cutoff
    ]

# ==========================================
# Claude 글 작성 함수들
# ==========================================

def call_claude(prompt, label):
    """
    Claude 호출 + 응답이 중간에 끊긴 경우 이어서 생성 (continuation)
    stop_reason이 'max_tokens'이면 끊긴 것으로 판단하고 이어받기
    """
    for attempt in range(3):
        try:
            messages = [{"role": "user", "content": prompt}]
            full_text = ""
            max_continuations = 3  # 최대 이어받기 횟수

            for cont in range(max_continuations + 1):
                message = client.messages.create(
                    model=MODEL_NAME,
                    max_tokens=8192,
                    messages=messages,
                )
                chunk = message.content[0].text
                full_text += chunk

                if message.stop_reason != "max_tokens":
                    # 정상 종료
                    if cont > 0:
                        print(f"  → {cont}회 이어받기 후 완성")
                    break

                # 끊긴 경우 — 이어받기
                print(f"  → 응답 끊김 감지 (continuation {cont+1}/{max_continuations})")
                messages = [
                    {"role": "user",      "content": prompt},
                    {"role": "assistant", "content": full_text},
                    {"role": "user",      "content": "이전 응답이 중간에 끊겼습니다. [EXCERPT]...[/EXCERPT] 태그까지 포함하여 이어서 완성해주세요. 앞 내용은 반복하지 말고 끊긴 부분부터 바로 이어서 작성하세요."},
                ]
            else:
                print(f"  → 최대 이어받기 횟수 초과, 현재까지 수집된 내용으로 진행")

            print(f"Claude {label} 글 작성 완료 (총 {len(full_text)}자)")
            return full_text

        except Exception as e:
            print(f"Claude 호출 실패 ({attempt+1}/3): {e}")
            if attempt < 2:
                time.sleep(10)
            else:
                raise


def generate_apt_fallback_article():
    """청약 공고가 없을 때 이번 달 청약 동향 요약 글 생성"""
    today = datetime.now()
    month_str = today.strftime("%Y년 %m월")
    prompt = f"""당신은 apt.bestwellth.org 분양정보팀 전문 에디터입니다.
이번 달({month_str}) 청약 시장 동향과 실수요자가 알아야 할 분양정보 체크포인트를 작성하세요.

{GUIDELINE_APT_INFO}

[작성 주제]
{month_str} 청약 시장 동향 — 이번 달 주목할 분양 포인트와 청약 준비 가이드

[작성 원칙]
- 공신력 있는 기관(청약홈·국토교통부) 기준으로 작성
- 확인되지 않는 구체적 수치(단지명·분양가 등)는 "청약홈 공고문 참조"로 처리
- 문어체(이다/한다/했다), 구어체·Markdown·이모티콘 금지
- HTML을 ```html 또는 ``` 마크다운 코드블록으로 감싸지 말 것 — 순수 HTML만 출력
- CTA 버튼 내 br태그 절대 금지
- 글 반드시 끝까지 완성
- [분양정보] 접두어 필수, 느낌표 금지

[HTML 구조]
{build_apt_html_guide(
    top_url="https://www.applyhome.co.kr",
    top_btn="청약홈 바로가기",
    bottom_url="https://www.applyhome.co.kr/ai/aib/selectSubscrptCalenderView.do",
    bottom_btn="청약 일정 및 통계 확인",
    ref_url="https://www.applyhome.co.kr",
    ref_name="청약홈 공식 사이트",
)}

[SEO — 반드시 출력]
[FOCUS_KW]3~4단어 롱테일 키워드[/FOCUS_KW]
[META_DESC]130~155자 메타 설명[/META_DESC]
[SLUG]반드시 영문 소문자+하이픈만 사용. 한글 절대 금지.[/SLUG]
[EXCERPT]100~150자 발췌문[/EXCERPT]

[응답 형식]
[TITLE][분양정보] 제목[/TITLE]
본문 HTML
[FOCUS_KW]...[/FOCUS_KW][META_DESC]...[/META_DESC][SLUG]...[/SLUG][EXCERPT]...[/EXCERPT]"""
    return call_claude(prompt, "분양정보(fallback)")


def generate_news_fallback_article():
    """뉴스 크롤링 실패 시 청약 시장 분석 글 생성"""
    today = datetime.now()
    date_str = today.strftime("%Y년 %m월 %d일")
    prompt = f"""당신은 apt.bestwellth.org 청약뉴스팀 전문 에디터입니다.
{date_str} 기준 분양 예정 단지 소개 또는 청약·부동산 제도 이슈를 작성하세요.

{GUIDELINE_APT_NEWS}

[작성 주제]
{date_str} 기준 분양 예정 단지 또는 청약·부동산 제도 변경 이슈 — 실수요자 대응 전략

[작성 원칙]
- 공신력 있는 기관(청약홈·국토교통부·한국부동산원) 기준으로 작성
- 확인되지 않는 구체적 수치(경쟁률·가격)는 "청약홈·한국부동산원 통계 참조"로 처리
- 문어체(이다/한다/했다), 구어체·Markdown·이모티콘 금지
- HTML을 ```html 또는 ``` 마크다운 코드블록으로 감싸지 말 것 — 순수 HTML만 출력
- CTA 버튼 내 br태그 절대 금지
- 글 반드시 끝까지 완성
- [청약뉴스] 접두어 필수, 느낌표 금지

[HTML 구조]
{build_apt_html_guide(
    top_url="https://www.applyhome.co.kr",
    top_btn="청약홈 바로가기",
    bottom_url="https://www.applyhome.co.kr/ai/aib/selectSubscrptCalenderView.do",
    bottom_btn="청약 일정 및 통계 확인",
    ref_url="https://www.reb.or.kr",
    ref_name="한국부동산원",
)}

[SEO — 반드시 출력]
[FOCUS_KW]3~4단어 롱테일 키워드[/FOCUS_KW]
[META_DESC]130~155자 메타 설명[/META_DESC]
[SLUG]반드시 영문 소문자+하이픈만 사용. 한글 절대 금지.[/SLUG]
[EXCERPT]100~150자 발췌문[/EXCERPT]

[응답 형식]
[TITLE][청약뉴스] 제목[/TITLE]
본문 HTML
[FOCUS_KW]...[/FOCUS_KW][META_DESC]...[/META_DESC][SLUG]...[/SLUG][EXCERPT]...[/EXCERPT]"""
    return call_claude(prompt, "청약뉴스(fallback)")


def generate_apt_article(announcement):
    subs_cat = announcement.get("subs_category", "")
    is_remndr = announcement.get("is_remndr", False)
    remndr_note = "※ 이 단지는 무순위(잔여세대/줍줍) 물량입니다. 실수요자 관심이 매우 높은 유형입니다." if is_remndr else ""
    cat_note = f"청약 구분: {subs_cat}" if subs_cat else ""

    # 소스 판별: LH vs 청약홈(한국부동산원)
    is_lh = "LH" in subs_cat or "lh.or.kr" in announcement.get("pblanc_url", "")
    if is_lh:
        site_name    = "LH청약"
        top_btn      = "LH청약 공고 바로가기"
        bottom_url   = "https://apply.lh.or.kr"
        bottom_btn   = "LH청약 바로가기"
        ref_name     = "LH청약 공고문"
        default_url  = "https://apply.lh.or.kr"
    else:
        site_name    = "청약홈"
        top_btn      = "청약홈 공고 바로가기"
        bottom_url   = "https://www.applyhome.co.kr/ai/aib/selectSubscrptCalenderView.do"
        bottom_btn   = "청약홈에서 청약 신청"
        ref_name     = "청약홈 분양 공고문"
        default_url  = "https://www.applyhome.co.kr"

    pblanc_url = announcement.get('pblanc_url') or default_url

    # extra_info에서 구조화된 필드 추출 (LH 데이터: "전용 55㎡ | 미분양 83호 | 주택가격 312,450천원 | 문의 ...")
    extra_raw = announcement.get('extra_info', '')
    extra_parsed = {}
    for part in extra_raw.split('|'):
        part = part.strip()
        if '전용' in part and '㎡' in part:
            extra_parsed['전용면적'] = part
        elif '미분양' in part and '호' in part:
            extra_parsed['미분양호수'] = part
        elif '주택가격' in part:
            extra_parsed['주택가격'] = part.replace('주택가격', '').strip() + ' (단위: 천원 → 실제 가격은 해당 금액×1,000원)'
        elif '공급금액' in part:
            extra_parsed['공급금액'] = part.replace('공급금액(만원):', '').strip()
        elif '입주예정' in part:
            extra_parsed['입주예정'] = part.strip()
        elif '시공사' in part:
            extra_parsed['시공사'] = part.replace('시공사:', '').strip()
        elif '특별공급' in part:
            extra_parsed['특별공급'] = part.replace('특별공급:', '').strip()
        elif '문의' in part:
            extra_parsed['분양문의'] = part.replace('문의', '').strip()

    price_note  = f"\n주택가격(정확한값): {extra_parsed['주택가격']}" if '주택가격' in extra_parsed else ''
    # 청약홈 분양 — 공급금액(만원) 단위
    supply_price_note = f"\n공급금액(만원 단위): {extra_parsed['공급금액']}" if '공급금액' in extra_parsed else ''
    area_note   = f"\n전용면적: {extra_parsed['전용면적']}" if '전용면적' in extra_parsed else ''
    unsold_note = f"\n미분양호수: {extra_parsed['미분양호수']}" if '미분양호수' in extra_parsed else ''
    movein_note = f"\n입주예정: {extra_parsed['입주예정']}" if '입주예정' in extra_parsed else ''
    const_note  = f"\n시공사: {extra_parsed['시공사']}" if '시공사' in extra_parsed else ''
    spsply_note = f"\n특별공급유형: {extra_parsed['특별공급']}" if '특별공급' in extra_parsed else ''
    # LH 비고: 신혼희망타운 전용, 계약금 조건 등 청약 자격 제한 핵심 정보
    lh_note = announcement.get('lh_note', '')
    note_note = f"\n신청자격 제한(비고): {lh_note}" if lh_note else ''

    data_block = f"""
주택명: {announcement.get('house_nm', '')}
공급지역: {announcement.get('region', '')}
공급위치: {announcement.get('hssply_adres', '')}
주택구분: {announcement.get('house_secd_nm', '')} / {announcement.get('house_dtl_secd_nm', '')}
{cat_note}
사업주체: {announcement.get('bsns_mby_nm', '')}
총 공급세대수: {announcement.get('supply_cnt', '')}세대{area_note}{unsold_note}{price_note}{supply_price_note}{movein_note}{const_note}{spsply_note}{note_note}
모집공고일: {announcement.get('rcrit_pblanc_de', '')}
청약접수: {announcement.get('subscrpt_rcept_bgnde', '')} ~ {announcement.get('subscrpt_rcept_endde', '')}
당첨자발표: {announcement.get('przwner_presnatn_de', '')}
계약체결: {announcement.get('cntrct_cncls_bgnde', '')}
투기과열지구: {announcement.get('speclt_rdn_earth_at', '')}
조정대상지역: {announcement.get('mdat_trget_area_secd', '')}
분양가상한제: {announcement.get('parcprc_uls_at', '')}
공고 URL: {announcement.get('pblanc_url', 'https://www.applyhome.co.kr')}
{remndr_note}

⚠ 수치·자격 사용 규칙:
- 공급금액은 이미 "약 N억 N,NNN만원" 형식으로 변환된 값이 제공됨 — 그대로 사용할 것. 임의로 재계산·추정 절대 금지.
- 공급금액 데이터가 없으면 반드시 "분양가는 청약홈 공고문 참조" 문구로 대체. 임의 숫자 생성 절대 금지.
- 【중요】 청약홈 공급금액 표의 단위(만원/천원)는 표 우측상단에 명시됨. 단위가 다르면 금액이 100배 차이나므로 절대 혼동 금지. 데이터에 이미 억/만원으로 변환된 값이 제공되므로 원본 숫자를 그대로 만원 또는 천원으로 쓰지 말 것.
- 신청자격 제한(비고) 항목이 있으면 반드시 본문 상단 또는 청약 자격 섹션에서 굵은 글씨로 강조할 것
- 자격 제한이 있는 단지는 일반 실수요자에게 "본인 자격 먼저 확인" 안내 필수
"""
    is_remndr_prompt = "\n- 무순위(잔여세대/줍줍) 물량임을 본문 상단에서 명확히 강조하고, 신청 자격·기간·방법을 우선 안내할 것" if is_remndr else ""
    source_note = "LH청약 공고 단지" if is_lh else "청약홈(한국부동산원) 공고 단지"
    prompt = f"""당신은 apt.bestwellth.org 분양정보팀 전문 에디터입니다.
아래 원문 데이터를 바탕으로 실수요자를 위한 분양 정보 글을 작성하세요.
출처: {source_note}. 사람들의 관심이 집중된 실시간 분양 정보임을 반영하여 작성하세요.

{GUIDELINE_APT_INFO}

[원문 데이터]
{data_block}

[공통 규칙]
- 문어체(이다/한다/했다), 구어체·Markdown·이모티콘 금지
- HTML을 ```html 또는 ``` 마크다운 코드블록으로 감싸지 말 것 — 순수 HTML만 출력
- CTA 버튼 내 br태그 절대 금지
- 글 반드시 끝까지 완성
- [분양정보] 접두어 필수, 느낌표 금지{is_remndr_prompt}

[HTML 구조]
{build_apt_html_guide(
    top_url=pblanc_url,
    top_btn=top_btn,
    bottom_url=bottom_url,
    bottom_btn=bottom_btn,
    ref_url=pblanc_url,
    ref_name=ref_name,
)}

[SEO — 반드시 출력]
[FOCUS_KW]3~4단어 롱테일 키워드[/FOCUS_KW]
[META_DESC]130~155자 메타 설명[/META_DESC]
[SLUG]반드시 영문 소문자+하이픈만 사용. 한글 절대 금지. 예: apartment-subscription-guide-2026[/SLUG]
[EXCERPT]100~150자 발췌문[/EXCERPT]

[응답 형식]
[TITLE][분양정보] 제목[/TITLE]
본문 HTML
[FOCUS_KW]...[/FOCUS_KW][META_DESC]...[/META_DESC][SLUG]...[/SLUG][EXCERPT]...[/EXCERPT]"""
    return call_claude(prompt, "분양정보")


def generate_news_article(articles):
    news_block = "\n\n".join(
        f"제목: {a['title']}\n출처: {a.get('press','')}\nURL: {a['url']}"
        + (f"\n요약: {a['summary']}" if a["summary"] else "")
        for a in articles
    )
    # 뉴스 출처 URL 목록 (참고자료용)
    source_refs = "\n".join(
        f"- {a['title'][:30]} ({a.get('press','')}) : {a['url']}"
        for a in articles[:5] if a.get('url')
    )
    first_ref = next((a for a in articles if a.get('url')), None)
    ref_url  = first_ref['url']   if first_ref else "https://www.applyhome.co.kr"
    ref_name = (first_ref['title'][:20] if first_ref else "청약홈")
    prompt = f"""당신은 apt.bestwellth.org 청약뉴스팀 전문 에디터입니다.
아래 뉴스를 분석하여 분양 예정 단지 소개 또는 청약·부동산 제도 변경 이슈 중심의 글을 작성하세요.

{GUIDELINE_APT_NEWS}

[오늘의 청약·분양 뉴스]
{news_block}

[공통 규칙]
- 문어체(이다/한다/했다), 구어체·Markdown·이모티콘 금지
- HTML을 ```html 또는 ``` 마크다운 코드블록으로 감싸지 말 것 — 순수 HTML만 출력
- CTA 버튼 내 br태그 절대 금지
- 글 반드시 끝까지 완성
- [청약뉴스] 접두어 필수, 느낌표 금지

[HTML 구조]
{build_apt_html_guide(
    top_url="https://www.applyhome.co.kr",
    top_btn="청약홈 바로가기",
    bottom_url="https://www.applyhome.co.kr/ai/aib/selectSubscrptCalenderView.do",
    bottom_btn="청약 일정 및 통계 확인",
    ref_url=ref_url,
    ref_name=ref_name,
)}

[SEO — 반드시 출력]
[FOCUS_KW]3~4단어 롱테일 키워드[/FOCUS_KW]
[META_DESC]130~155자 메타 설명[/META_DESC]
[SLUG]반드시 영문 소문자+하이픈만 사용. 한글 절대 금지. 예: apartment-subscription-guide-2026[/SLUG]
[EXCERPT]100~150자 발췌문[/EXCERPT]

[응답 형식]
[TITLE][청약뉴스] 제목[/TITLE]
본문 HTML
[FOCUS_KW]...[/FOCUS_KW][META_DESC]...[/META_DESC][SLUG]...[/SLUG][EXCERPT]...[/EXCERPT]"""
    return call_claude(prompt, "청약뉴스")


def generate_guide_article(topic, source_type, source_data=""):
    """
    source_type: "policy" | "announcement" | "rotation"
    source_data: 정책 보도자료 내용 또는 공고 특성 설명
    """
    source_block = ""
    if source_type == "policy" and source_data:
        source_block = f"\n[참고 정책 보도자료]\n{source_data}\n"
    elif source_type == "announcement" and source_data:
        source_block = f"\n[연계 분양공고 특성]\n{source_data}\n"

    prompt = f"""당신은 apt.bestwellth.org 청약가이드팀 전문 에디터입니다.
아래 주제로 청약 실수요자를 위한 가이드 글을 작성하세요.

{GUIDELINE_APT_GUIDE}

[오늘의 가이드 주제]
{topic}

[주제 선정 배경: {source_type}]{source_block}

[작성 원칙]
- 공신력 있는 기관(청약홈·국토교통부·주택도시기금) 기준으로 작성
- 확인되지 않는 구체적 수치(소득 기준·LTV 한도 등)는 "청약홈 공고문 또는 은행 상담 참조"로 처리
- 초보자도 이해할 수 있도록 쉽고 구체적으로 설명
- 문어체(이다/한다/했다), 구어체·Markdown·이모티콘 금지
- HTML을 ```html 또는 ``` 마크다운 코드블록으로 감싸지 말 것 — 순수 HTML만 출력
- CTA 버튼 내 br태그 절대 금지
- 글 반드시 끝까지 완성
- [청약가이드] 접두어 필수, 느낌표 금지

[HTML 구조]
{build_apt_html_guide(
    top_url="https://www.applyhome.co.kr",
    top_btn="청약홈 바로가기",
    bottom_url="https://nhuf.molit.go.kr",
    bottom_btn="주택도시기금 조회",
    ref_url="https://www.applyhome.co.kr",
    ref_name="청약홈 공식 사이트",
)}

[SEO — 반드시 출력]
[FOCUS_KW]3~4단어 롱테일 키워드[/FOCUS_KW]
[META_DESC]130~155자 메타 설명[/META_DESC]
[SLUG]반드시 영문 소문자+하이픈만 사용. 한글 절대 금지. 예: apartment-subscription-guide-2026[/SLUG]
[EXCERPT]100~150자 발췌문[/EXCERPT]

[응답 형식]
[TITLE][청약가이드] 제목[/TITLE]
본문 HTML
[FOCUS_KW]...[/FOCUS_KW][META_DESC]...[/META_DESC][SLUG]...[/SLUG][EXCERPT]...[/EXCERPT]"""
    return call_claude(prompt, "청약가이드")


# ==========================================
# 공통 파싱 + 발행
# ==========================================
def parse_and_publish(raw, category_id, label):
    def extract(tag, default=""):
        m = re.search(rf'\[{tag}\](.*?)\[/{tag}\]', raw, re.DOTALL)
        return m.group(1).strip() if m else default

    title     = extract("TITLE",     f"[{label}] 오늘의 정보")
    focus_kw  = extract("FOCUS_KW",  "")
    meta_desc = extract("META_DESC", "")
    slug      = extract("SLUG",      "")
    excerpt   = extract("EXCERPT",   "")

    # 슬러그 안전장치 — 한글 포함 시 영문만 추출 후 재조합
    import unicodedata
    def is_korean(c):
        return unicodedata.category(c) in ("Lo",) and ord(c) >= 0xAC00
    if any(is_korean(c) for c in slug):
        print(f"슬러그 한글 감지 → 영문 변환 처리: {slug}")
        # 영문·숫자·하이픈만 남기고 나머지 제거
        clean = re.sub(r'[^a-zA-Z0-9\-]', '-', slug)
        clean = re.sub(r'-+', '-', clean).strip('-').lower()
        # 영문이 너무 짧으면 날짜 기반 슬러그로 대체
        if len(clean) < 5:
            today_str = datetime.now().strftime("%Y-%m-%d")
            cat_map = {"분양정보": "apt-info", "청약뉴스": "apt-news", "청약가이드": "apt-guide"}
            clean = f"{cat_map.get(label, 'apt')}-{today_str}"
        slug = clean
        print(f"변환된 슬러그: {slug}")

    # 슬러그에 과거 연도 포함 시 현재 연도로 교정 (예: 2025 → 2026)
    current_year = str(datetime.now().year)
    for past_year in ["2020", "2021", "2022", "2023", "2024", "2025"]:
        if past_year in slug:
            slug = slug.replace(past_year, current_year)
            print(f"슬러그 연도 교정: {past_year} → {current_year}")
            break

    body = raw
    for tag in ["TITLE", "FOCUS_KW", "META_DESC", "SLUG", "EXCERPT"]:
        body = re.sub(rf'\[{tag}\].*?\[/{tag}\]\n?', '', body, flags=re.DOTALL)
    body = body.strip()
    # 마크다운 코드블록 제거 (```html ... ``` 또는 ``` ... ```)
    body = re.sub(r'^```[a-zA-Z]*\n?', '', body, flags=re.MULTILINE)
    body = re.sub(r'\n?```\s*$', '', body, flags=re.MULTILINE)
    body = body.strip()
    body = re.sub(r'(?<=href=")(.*?)(?=")', lambda m: m.group(0).replace("&amp;", "&"), body)
    # 줄바꿈으로 분리된 닫는 태그 수정: </li\n> → </li>
    body = re.sub(r'</([A-Za-z][A-Za-z0-9]*)\s+>', lambda m: f'</{m.group(1).lower()}>', body)
    # 대소문자 혼용 닫는 태그 소문자 통일: </P>, </H2> 등 (> 있는 경우만)
    body = re.sub(r'</(P|H[1-6]|DIV|SPAN|TABLE|TR|TD|TH|UL|OL|LI|A|STRONG|EM|B|I)>',
                  lambda m: f'</{m.group(1).lower()}>', body)
    # > 없는 잘못된 닫는 태그 수정: </P 다음에 비알파숫자 문자가 오는 경우
    body = re.sub(r'</(P|H[1-6]|DIV|SPAN|TABLE|TR|TD|TH|UL|OL|LI|A|STRONG|EM|B|I)(?=[^a-zA-Z0-9>])',
                  lambda m: f'</{m.group(1).lower()}>', body)

    print(f"제목: {title}")
    print(f"포커스 키워드: {focus_kw}")
    print(f"슬러그: {slug}")

    result = wp_create_draft(
        title=title, content=body, excerpt=excerpt,
        category_id=category_id, slug=slug,
    )
    if not result:
        print(f"포스트 생성 실패 (WordPress API 오류) — 건너뜀")
        return None
    post_id  = result.get("id", "")
    edit_url = f"{APT_WP_SITE_URL}/wp-admin/post.php?post={post_id}&action=edit"
    print(f"포스트 생성 완료! ID: {post_id}")

    if post_id and focus_kw:
        wp_update_rank_math(post_id, focus_kw, meta_desc)

    send_telegram(
        f"<b>apt.bestwellth.org 자동 발행 완료</b>\n\n"
        f"카테고리: {label}\n제목: {title}\n"
        f"포커스 키워드: {focus_kw}\n슬러그: {slug}\n\n"
        f"편집: {edit_url}"
    )
    return title

# ==========================================
# 메인 실행
# ==========================================
def run():
    print("apt.bestwellth.org 청약 자동 발행 시작...\n")

    history = load_history()
    history_updated = False
    today_str = datetime.now().strftime("%Y-%m-%d")
    weekday   = datetime.now().weekday()   # 0=월, 1=화 ... 6=일
    is_monday = (weekday == 0)

    # ── 청약일정 글 강제 재발행 (REWRITE_SCHEDULE=1 환경변수로 트리거) ──
    if os.environ.get("REWRITE_SCHEDULE") == "1":
        print("[재발행 모드] 청약일정 글 재생성 및 업데이트 중...")
        rewrite_slug = os.environ.get("REWRITE_SLUG", "")
        raw = generate_weekly_schedule_article()
        if not raw:
            print("청약일정 데이터 없음 — 재발행 불가")
            return
        if rewrite_slug:
            # 슬러그로 기존 포스트 찾아 내용 업데이트
            import re as _re2
            title_m = _re2.search(r'\[TITLE\](.*?)\[/TITLE\]', raw, _re2.DOTALL)
            title   = title_m.group(1).strip() if title_m else "[청약일정] 업데이트"
            body    = raw
            for tag in ["TITLE","FOCUS_KW","META_DESC","SLUG","EXCERPT"]:
                body = _re2.sub(rf'\[{tag}\].*?\[/{tag}\]\n?', '', body, flags=_re2.DOTALL)
            body = _re2.sub(r'^```[a-zA-Z]*\n?', '', body.strip(), flags=_re2.MULTILINE)
            body = _re2.sub(r'\n?```\s*$', '', body, flags=_re2.MULTILINE).strip()
            post_id = wp_find_post_by_slug(rewrite_slug)
            if post_id:
                wp_update_post(post_id, title, body, "")
                focus_m   = _re2.search(r'\[FOCUS_KW\](.*?)\[/FOCUS_KW\]', raw, _re2.DOTALL)
                metadesc_m= _re2.search(r'\[META_DESC\](.*?)\[/META_DESC\]', raw, _re2.DOTALL)
                if focus_m and metadesc_m:
                    wp_update_rank_math(post_id, focus_m.group(1).strip(), metadesc_m.group(1).strip())
            else:
                print(f"슬러그 '{rewrite_slug}' 포스트 없음 → 새 글로 발행")
                parse_and_publish(raw, CAT_ID["apt-schedule"], "청약일정")
        else:
            parse_and_publish(raw, CAT_ID["apt-schedule"], "청약일정")
        print("[재발행 모드] 완료")
        return

    # ── 긴급 여부 판단 ──────────────────────────────────────────────
    # 신규 부동산 정책이 있으면 긴급으로 간주 → 당일 청약가이드 강제 발행
    policy = fetch_molit_policy()
    is_urgent_policy = bool(policy)

    # ── 월요일: 주간 청약 및 분양일정만 발행 ───────────────────────
    if is_monday:
        print("오늘은 월요일 → 주간 청약일정 발행")
        schedule_this_week = any(
            r.get("date", "") >= (datetime.now() - timedelta(days=weekday)).strftime("%Y-%m-%d")
            for r in history.get("apt-schedule", [])
        )
        if schedule_this_week:
            print("청약일정 총정리 — 이번 주 이미 발행됨, 스킵")
        else:
            print("청약일정 글 생성 중...")
            schedule_key = f"weekly-schedule-{datetime.now().strftime('%Y-W%U')}"
            raw = generate_weekly_schedule_article()
            if raw:
                title = parse_and_publish(raw, CAT_ID["apt-schedule"], "청약일정")
                record_history(history, "apt-schedule", schedule_key, title)
                history_updated = True
            else:
                print("청약일정 데이터 없음 — 스킵")

        # 긴급 정책이 있으면 청약가이드도 추가 발행
        if is_urgent_policy:
            print(f"\n[긴급] 신규 정책 감지 → 청약가이드 추가 발행")
            guide_topic = f"신규 부동산 정책 — {policy['title']}"
            guide_source_data = f"제목: {policy['title']}\nURL: {policy['url']}\n내용: {policy['summary']}"
            if not is_duplicate(history, "apt-guide", guide_topic, days=60):
                raw = generate_guide_article(guide_topic, "policy", guide_source_data)
                title = parse_and_publish(raw, CAT_ID["apt-guide"], "청약가이드")
                record_history(history, "apt-guide", guide_topic, title)
                history_updated = True

        if history_updated:
            save_history(history)
        print("\n전체 발행 완료")
        return

    # ── 화~일: 하루 1개 발행 ────────────────────────────────────────
    # 오늘 이미 발행된 카테고리 확인
    published_today = set()
    for cat in ["apt-info", "apt-news", "apt-guide"]:
        if any(r.get("date") == today_str for r in history.get(cat, [])):
            published_today.add(cat)

    if len(published_today) >= 1 and not is_urgent_policy:
        print(f"오늘 이미 발행됨 ({published_today}) — 긴급 아니면 스킵")
        # 긴급 정책이 없으면 종료
        print("\n전체 발행 완료")
        return

    # 발행 순서 결정: 요일 기반 로테이션 (화=분양정보, 수=청약뉴스, 목=청약가이드, 반복)
    # weekday: 1=화, 2=수, 3=목, 4=금, 5=토, 6=일
    rotation_order = ["apt-info", "apt-news", "apt-guide"]
    today_slot = rotation_order[(weekday - 1) % 3]  # 화(1)→0, 수(2)→1, 목(3)→2, 금(4)→0, ...

    # 오늘 슬롯이 이미 발행됐으면 다른 미발행 카테고리로 대체
    candidates = [today_slot] + [c for c in rotation_order if c != today_slot]
    target_cat = None
    for cat in candidates:
        if cat not in published_today:
            target_cat = cat
            break

    if not target_cat:
        print("오늘 모든 카테고리 발행 완료 — 스킵")
        if history_updated:
            save_history(history)
        print("\n전체 발행 완료")
        return

    print(f"오늘 발행 카테고리: {target_cat} (슬롯: {today_slot})")

    # ── 분양정보 발행 ──────────────────────────────────────────────
    if target_cat == "apt-info":
        announcements = fetch_apt_announcements()
        latest = None
        for ann in announcements:
            house_nm = ann.get("house_nm", "")
            if not is_duplicate(history, "apt-info", house_nm):
                latest = ann
                break

        if latest:
            house_nm = latest.get("house_nm", "")
            # 긴급 여부: 청약 접수 마감이 3일 이내이면 긴급 표기
            endde = latest.get("subscrpt_rcept_endde", "")
            is_urgent_apt = False
            if endde:
                try:
                    end_dt = datetime.strptime(endde, "%Y%m%d")
                    is_urgent_apt = (end_dt - datetime.now()).days <= 3
                except Exception:
                    pass
            if is_urgent_apt:
                print(f"[긴급] 청약 마감 임박: {house_nm} ({endde})")
            print(f"\n선택 단지: {house_nm} ({latest.get('region')})")
            raw = generate_apt_article(latest)
            title = parse_and_publish(raw, CAT_ID["apt-info"], "분양정보")
            record_history(history, "apt-info", house_nm, title)
            history_updated = True
        else:
            print("신규 청약 공고 없음 — fallback 분양정보 글 생성")
            fallback_key = f"apt-info-fallback-{datetime.now().strftime('%Y-%m')}"
            if not is_duplicate(history, "apt-info", fallback_key, days=25):
                raw = generate_apt_fallback_article()
                title = parse_and_publish(raw, CAT_ID["apt-info"], "분양정보")
                record_history(history, "apt-info", fallback_key, title)
                history_updated = True
            else:
                print("이번 달 분양정보 fallback 이미 발행됨 — 스킵")

    # ── 청약뉴스 발행 ──────────────────────────────────────────────
    elif target_cat == "apt-news":
        articles = fetch_apt_news()
        if articles:
            news_key = " ".join(a["title"][:20] for a in articles[:3])
            if is_duplicate(history, "apt-news", news_key, days=1):
                print("청약뉴스 중복 스킵")
            else:
                raw = generate_news_article(articles)
                title = parse_and_publish(raw, CAT_ID["apt-news"], "청약뉴스")
                record_history(history, "apt-news", news_key, title)
                history_updated = True
        else:
            print("청약/분양 뉴스 수집 실패 — fallback 뉴스 글 생성")
            fallback_key = f"apt-news-fallback-{today_str}"
            raw = generate_news_fallback_article()
            title = parse_and_publish(raw, CAT_ID["apt-news"], "청약뉴스")
            record_history(history, "apt-news", fallback_key, title)
            history_updated = True

    # ── 청약가이드 발행 ────────────────────────────────────────────
    elif target_cat == "apt-guide":
        guide_topic = None
        guide_source_type = None
        guide_source_data = ""

        # 1순위: 신규 부동산 정책
        if is_urgent_policy:
            guide_topic       = f"신규 부동산 정책 — {policy['title']}"
            guide_source_type = "policy"
            guide_source_data = f"제목: {policy['title']}\nURL: {policy['url']}\n내용: {policy['summary']}"
            print(f"가이드 주제: 정책 감지 → {guide_topic}")

        # 2순위: 로테이션
        if not guide_topic:
            for offset in range(len(GUIDE_ROTATION_TOPICS)):
                day_of_year = datetime.now().timetuple().tm_yday
                idx = (day_of_year + offset) % len(GUIDE_ROTATION_TOPICS)
                candidate = GUIDE_ROTATION_TOPICS[idx]
                if not is_duplicate(history, "apt-guide", candidate, days=60):
                    guide_topic       = candidate
                    guide_source_type = "rotation"
                    print(f"가이드 주제: 로테이션 → {guide_topic}")
                    break
            else:
                guide_topic       = GUIDE_ROTATION_TOPICS[0]
                guide_source_type = "rotation"
                print("가이드 로테이션 소진 — 첫 번째 주제 재사용")

        if guide_topic:
            if is_duplicate(history, "apt-guide", guide_topic, days=60):
                print(f"청약가이드 중복 스킵: {guide_topic}")
            else:
                raw = generate_guide_article(guide_topic, guide_source_type, guide_source_data)
                title = parse_and_publish(raw, CAT_ID["apt-guide"], "청약가이드")
                record_history(history, "apt-guide", guide_topic, title)
                history_updated = True

    # 히스토리 저장
    if history_updated:
        save_history(history)

    print("\n전체 발행 완료")

if __name__ == "__main__":
    run()
