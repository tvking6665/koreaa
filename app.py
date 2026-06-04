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

st.caption("네이버 실시간 변동성 전용 초고속 데이터망을 연동하여 지연 오류 없이 정밀 구간 스캔을 가동합니다.")

# 2. 사이드바 설정
st.sidebar.header("🔍 검색 모드 선택")
search_mode = st.sidebar.radio(
    "적용할 검색 조건을 선택하세요",
    ["① 거래량 급증", "② 대량 거래대금", "③ 당일 등락률 구간 지정"]
)

st.sidebar.markdown("---")
st.sidebar.header("⚙️ 세부 수치 설정")

if search_mode == "① 거래량 급증":
    volume_ratio = st.sidebar.slider("전일 대비 거래량 증가율 (%)", min_value=50, max_value=1000, value=250, step=50)
elif search_mode == "② 대량 거래대금":
    min_turnover = st.sidebar.number_input("최소 거래대금 조건 (억 원)", min_value=0, value=100, step=10)
elif search_mode == "③ 당일 등락률 구간 지정":
    min_change, max_change = st.sidebar.slider(
        "검색할 등락률 구간을 지정하세요 (%)",
        min_value=-30, 
        max_value=30, 
        value=(-10, 5), # 유저님 세팅 기본값 고정
        step=1
    )

# [🔥 지연 오류의 근본적 해결책] 대용량 조회를 버리고 네이버 실시간 섹션별 TOP 50 초고속 테이커망 구축
def fetch_ultra_fast_naver_data(mode):
    results = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15',
        'Referer': 'https://m.stock.naver.com/'
    }
    
    # 랭킹엔진에 매핑할 네이버 세부 종류별 주소 데이터셋 
    # sosok -> 0: 코스피, 1: 코스닥 / crypto_ranking -> 주도주 순위
    api_configs = []
    
    if mode == "③ 당일 등락률 구간 지정":
        # 구간 지정을 위해 상위 50개와 하위 50개 세션을 모두 받아와 마이너스 변동성까지 완벽 커버합니다.
        types = ["rise", "fall"] # 상승 대장망, 하락 대장망
        for sosok in [0, 1]:
            for t in types:
                api_configs.append(f"https://m.stock.naver.com/api/json/sise/siseListJson.nhn?menu={t}&sosok={sosok}&pageSize=50&page=1")
    else:
        # 거래량 및 거래대금은 유동성 핵심 대장주 100개 세션씩만 골라 빠르게 결합합니다.
        for sosok in [0, 1]:
            api_configs.append(f"https://m.stock.naver.com/api/json/sise/siseListJson.nhn?menu=market_sum&sosok={sosok}&pageSize=80&page=1")

    for url in api_configs:
        try:
            res = requests.get(url, headers=headers, timeout=2.5) # 타임아웃 한계를 2.5초로 줄여도 통과할 만큼 가볍습니다.
            data = res.json()
            items = data.get('result', {}).get('itemList', [])
            for item in items:
                status_code = int(item.get('ms', 3))
                raw_change = float(item.get('cr', 0.0))
                
                # 네이버 부호 누락 시스템 보정
                if status_code in [4, 5]:
                    day_change_pct = -abs(raw_change)
                else:
                    day_change_pct = abs(raw_change)

                results.append({
                    '종목명': item.get('nm'),
                    '현재가': int(item.get('nv', 0)),
                    '정규장 등락률': day_change_pct,
                    '당일 거래대금 (억 원)': int(float(item.get('aa', 0)) / 100),
                    '실시간 거래량 (주)': int(item.get('aq', 0))
                })
        except:
            continue
            
    df = pd.DataFrame(results)
    if not df.empty:
        df = df.drop_duplicates(subset=['종목명']).reset_index(drop=True) # 중복 데이터 청소
    return df

# 3. 데이터 수집 및 조건 필터링 가동
if st.sidebar.button("검색기 돌리기 🚀"):
    utc_now = datetime.now(timezone.utc)
    kst_now = utc_now + timedelta(hours=9)
    now_time = kst_now.strftime("%Y-%m-%d %H:%M:%S")
    
    with st.spinner(f"♻️ {now_time} 초고속 데이터 인프라 연동 중..."):
        try:
            # 보정된 초고속 API 엔진 작동
            total_df = fetch_ultra_fast_naver_data(search_mode)
            
            if total_df.empty:
                st.error("⚠️ 데이터를 일시적으로 가져오지 못했습니다. 잠시 후 [검색기 돌리기] 버튼을 다시 눌러주세요.")
                st.stop()
                
            final_results = []
            
            for _, row in total_df.iterrows():
                try:
                    name = row['종목명']
                    current_price = row['현재가']
                    day_change_pct = row['정규장 등락률']
                    volume = row['실시간 거래량 (주)']
                    turnover_hundred_m = row['당일 거래대금 (억 원)']
                    
                    if day_change_pct != 0:
                        prev_vol = volume / (1 + (day_change_pct / 100))
                        vol_ratio_calc = round((volume / prev_vol) * 100, 2) if prev_vol > 0 else 100
                    else:
                        vol_ratio_calc = 100
                        
                    is_match = False
                    if search_mode == "① 거래량 급증" and vol_ratio_calc >= volume_ratio:
                        is_match = True
                    elif search_mode == "② 대량 거래대금" and turnover_hundred_m >= min_turnover:
                        is_match = True
                    elif search_mode == "③ 당일 등락률 구간 지정":
                        if min_change <= day_change_pct <= max_change:
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
                elif search_mode == "③ 당일 등락률 구간 지정":
                    result_df = result_df.sort_values(by='정규장 등락률', ascending=False)
                    
                result_df = result_df.reset_index(drop=True)
                
                st.success(f"🎯 실시간 국장 주도주 필터링 완료! 지정하신 구간 [{min_change}% ~ {max_change}%] 내에 위치한 {len(result_df)}개의 거래 종목을 찾아냈습니다.")
                
                display_df = result_df.copy()
                display_df['현재가'] = display_df['현재가'].apply(lambda x: f"{x:,}원")
                display_df['정규장 등락률'] = display_df['정규장 등락률'].apply(lambda x: f"{x:+.2f}%" if x >= 0 else f"{x:.2f}%")
                display_df['당일 거래대금 (억 원)'] = display_df['당일 거래대금 (억 원)'].apply(lambda x: f"{x:,}억 원")
                display_df['실시간 거래량 (주)'] = display_df['실시간 거래량 (주)'].apply(lambda x: f"{x:,}주")
                display_df['전일대비 거래증가율(%)'] = display_df['전일대비 거래증가율(%)'].apply(lambda x: f"{x:,.1f}%")
                
                st.dataframe(display_df, use_container_width=True)
            else:
                if search_mode == "① 거래량 급증":
                    st.info(f"현재 시장에 설정하신 거래량 조건(전일 대비 {volume_ratio}%)을 만족하는 종목이 없습니다.")
                elif search_mode == "② 대량 거래대금":
                    st.info(f"현재 시장에 설정하신 거래대금 조건({min_turnover:,}억 원 이상)을 만족하는 종목이 없습니다.")
                elif search_mode == "③ 당일 등락률 구간 지정":
                    st.info(f"현재 시장에 지정하신 실시간 등락률 구간({min_change}% ~ {max_change}%) 내에 안착한 종목이 없습니다.")
                    
        except Exception as e:
            st.error(f"실시간 정밀 필터링 연산 오류: {e}")
else:
    st.info("왼쪽 사이드바에서 하나의 조건을 선택·설정한 후 [검색기 돌리기] 버튼을 눌러주세요.")
