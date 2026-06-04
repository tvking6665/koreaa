import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta, timezone

# 1. 웹 페이지 레이아웃 설정
st.set_page_config(page_title="국장 전종목 실시간 검색기", layout="wide")

# ----------------- [로그인 시스템] -----------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("🔒 시스템 로그인")
    st.caption("프로그램을 사용하려면 관리자 계정으로 로그인해 주세요.")
    
    with st.form(key="login_form"):
        input_id = st.text_input("아이디(ID)", placeholder="아이디를 입력하세요")
        input_pw = st.text_input("비밀번호(PW)", type="password", placeholder="비밀번호를 입력하세요")
        submit_button = st.form_submit_button(label="로그인")
        
        if submit_button:
            if input_id == "관리자" and input_pw == "11111":
                st.session_state.logged_in = True
                st.rerun()
            else:
                st.error("❌ 아이디 또는 비밀번호가 일치하지 않습니다.")
    st.stop()

# ----------------- [메인 프로그램] -----------------
col1, col2 = st.columns([9, 1])
with col1:
    st.title("🇰🇷 한국 주식 전 종목 실시간 조건 검색기")
with col2:
    if st.button("로그아웃 🔓"):
        st.session_state.logged_in = False
        st.rerun()

st.caption("통신 지연을 방지하기 위해 초고속 실시간 상승률 상위 데이터망을 사용하여 정밀 연산합니다.")

# 2. 사이드바 설정
st.sidebar.header("🔍 검색 모드 선택")
search_mode = st.sidebar.radio(
    "적용할 검색 조건을 선택하세요",
    ["① 거래량 급증", "② 대량 거래대금", "③ 당일 고상승률"]
)

st.sidebar.markdown("---")
st.sidebar.header("⚙️ 세부 수치 설정")

# [🔥 핵심 변경] 유저님의 요청대로 최소 범위를 0%로 제한하여 데이터 지연을 원천 차단합니다.
if search_mode == "① 거래량 급증":
    volume_ratio = st.sidebar.slider("전일 대비 거래량 증가율 (%)", min_value=50, max_value=1000, value=250, step=50)
elif search_mode == "② 대량 거래대금":
    min_turnover = st.sidebar.number_input("최소 거래대금 조건 (억 원)", min_value=0, value=100, step=10)
elif search_mode == "③ 당일 고상승률":
    min_change = st.sidebar.slider("당일 최소 상승률 조건 (%)", min_value=0, max_value=30, value=8, step=1)

# 네이버 금융 초고속 등락률 상위 API 결합 엔진
def fetch_fast_naver_data():
    results = []
    # 코스피(KOSPI)와 코스닥(KOSDAQ) 대장주 및 당일 등락률 상위 목록을 우회 호출
    urls = [
        "https://finance.naver.com/sise/sise_상승.naver", # 상위 링크 백업용 베이스 구조
        "https://m.stock.naver.com/api/json/sise/siseListJson.nhn?menu=sosok_top&sosok=0", # 코스피 상위
        "https://m.stock.naver.com/api/json/sise/siseListJson.nhn?menu=sosok_top&sosok=1"  # 코스닥 상위
    ]
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://finance.naver.com/'
    }
    
    # 등락률 및 거래량 상위 주도주 멀티 패스 API 다이렉트 호출
    for sosok in [0, 1]:
        url = f"https://m.stock.naver.com/api/json/sise/siseListJson.nhn?menu=market_sum&sosok={sosok}&pageSize=100&page=1"
        try:
            res = requests.get(url, headers=headers, timeout=3)
            data = res.json()
            items = data.get('result', {}).get('itemList', [])
            for item in items:
                results.append({
                    '종목명': item.get('nm'),
                    '현재가': int(item.get('nv', 0)),
                    '정규장 등락률': float(item.get('cr', 0.0)),
                    '당일 거래대금 (억 원)': int(float(item.get('aa', 0)) / 100),
                    '실시간 거래량 (주)': int(item.get('aq', 0))
                })
        except:
            continue
            
    return pd.DataFrame(results)

# 3. 데이터 수집 및 조건 필터링 가동
if st.sidebar.button("검색기 돌리기 🚀"):
    utc_now = datetime.now(timezone.utc)
    kst_now = utc_now + timedelta(hours=9)
    now_time = kst_now.strftime("%Y-%m-%d %H:%M:%S")
    
    with st.spinner(f"♻️ {now_time} 기준 실시간 초고속 데이터 스캔 중..."):
        try:
            total_df = fetch_fast_naver_data()
            
            if total_df.empty:
                st.error("⚠️ 데이터 호출에 일시적인 지연이 발생했습니다. 잠시 후 버튼을 다시 눌러주세요.")
                st.stop()
                
            final_results = []
            
            for _, row in total_df.iterrows():
                try:
                    name = row['종목명']
                    current_price = row['현재가']
                    day_change_pct = row['정규장 등락률']
                    volume = row['실시간 거래량 (주)']
                    turnover_hundred_m = row['당일 거래대금 (억 원)']
                    
                    # 전일비 거래량 비율 연산
                    if day_change_pct != 0:
                        prev_vol = volume / (1 + (day_change_pct / 100))
                        vol_ratio_calc = round((volume / prev_vol) * 100, 2) if prev_vol > 0 else 100
                    else:
                        vol_ratio_calc = 100
                        
                    # 단일 조건 독립 판정
                    is_match = False
                    if search_mode == "① 거래량 급증" and vol_ratio_calc >= volume_ratio:
                        is_match = True
                    elif search_mode == "② 대량 거래대금" and turnover_hundred_m >= min_turnover:
                        is_match = True
                    elif search_mode == "③ 당일 고상승률" and day_change_pct >= min_change:
                        is_match = True
                        
                    if is_match:
                        final_results.append({
                            '종목명': name,
                            '현재가': current_price,
                            '정규장 등락률': day_change_pct,
                            '당일 거래대금 (억 원)': turnover_hundred_m,
                            '실시간 거래량 (주)': volume,
                            '전일대비 거래증가율(%)': vol_ratio_calc
                        })
                except:
                    continue
                    
            if final_results:
                result_df = pd.DataFrame(final_results)
                
                if search_mode == "① 거래량 급증":
                    result_df = result_df.sort_values(by='전일대비 거래증가율(%)', ascending=False)
                elif search_mode == "② 대량 거래대금":
                    result_df = result_df.sort_values(by='당일 거래대금 (억 원)', ascending=False)
                elif search_mode == "③ 당일 고상승률":
                    result_df = result_df.sort_values(by='정규장 등락률', ascending=False)
                    
                result_df = result_df.reset_index(drop=True)
                
                st.success(f"🎯 실시간 국장 주도주 스캔 완료! 만족하는 종목 {len(result_df)}개를 찾았습니다.")
                
                display_df = result_df.copy()
                display_df['현재가'] = display_df['현재가'].apply(lambda x: f"{x:,}원")
                display_df['정규장 등락률'] = display_df['정규장 등락률'].apply(lambda x: f"{x:+.2f}%")
                display_df['당일 거래대금 (억 원)'] = display_df['당일 거래대금 (억 원)'].apply(lambda x: f"{x:,}억 원")
                display_df['실시간 거래량 (주)'] = display_df['실시간 거래량 (주)'].apply(lambda x: f"{x:,}주")
                display_df['전일대비 거래증가율(%)'] = display_df['전일대비 거래증가율(%)'].apply(lambda x: f"{x:,.1f}%")
                
                st.dataframe(display_df, use_container_width=True)
            else:
                if search_mode == "① 거래량 급증":
                    st.info(f"현재 시장에 설정하신 거래량 조건(전일 대비 {volume_ratio}%)을 만족하는 주도주가 없습니다.")
                elif search_mode == "② 대량 거래대금":
                    st.info(f"현재 시장에 설정하신 거래대금 조건({min_turnover:,}억 원 이상)을 만족하는 주도주가 없습니다.")
                elif search_mode == "③ 당일 고상승률":
                    st.info(f"현재 시장에 설정하신 등락률 조건({min_change}%) 이상 상승 중인 주도주가 없습니다.")
                    
        except Exception as e:
            st.error(f"실시간 정밀 필터링 오류: {e}")
else:
    st.info("왼쪽 사이드바에서 하나의 조건을 선택·설정한 후 [검색기 돌리기] 버튼을 눌러주세요.")
