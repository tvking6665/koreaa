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

st.caption("정규장 데이터망과 시간외 단일가 데이터망을 완벽하게 분리하여 왜곡 없는 실시간 데이터를 제공합니다.")

# 2. 사이드바 설정
st.sidebar.header("⏰ 마켓 시간대 선택")
# [🔥 핵심 추가] 정규장과 시간외장을 유저가 직접 구분하여 선택하도록 구현
market_time_zone = st.sidebar.selectbox(
    "조회할 마켓 타임라인을 고르세요",
    ["일반 정규장 시세 (09:00 ~ 15:30)", "시간외 단일가 시세 (16:00 ~ 18:00)"]
)

st.sidebar.markdown("---")
st.sidebar.header("🔍 검색 모드 선택")
search_mode = st.sidebar.radio(
    "적용할 검색 조건을 선택하세요",
    ["① 거래량 급증", "② 거래대금 구간 지정", "③ 당일 등락률 구간 지정"]
)

st.sidebar.markdown("---")
st.sidebar.header("⚙️ 세부 수치 설정")

if search_mode == "① 거래량 급증":
    volume_ratio = st.sidebar.slider("전일 대비 거래량 증가율 (%)", min_value=50, max_value=1000, value=250, step=50)
elif search_mode == "② 거래대금 구간 지정":
    min_turnover, max_turnover = st.sidebar.slider(
        "검색할 거래대금 구간을 지정하세요 (억 원)",
        min_value=0, 
        max_value=2000, 
        value=(100, 1000), 
        step=50
    )
elif search_mode == "③ 당일 등락률 구간 지정":
    min_change, max_change = st.sidebar.slider(
        "검색할 등락률 구간을 지정하세요 (%)",
        min_value=-30, 
        max_value=30, 
        value=(-10, 5) if "시간외" not in market_time_zone else (1, 10), # 시간외 기본값은 1%~10%로 유연하게 세팅
        step=1
    )

# [🔥 정규장 / 시간외 서버 분리 데이터 테이커 엔진]
def fetch_segmented_naver_data(time_zone, mode):
    results = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://m.stock.naver.com/'
    }
    
    api_urls = []
    
    # CASE 1: 사용자가 [시간외 단일가]를 선택한 경우 -> 네이버 시간외 단일가 전용 순위서버 API 연동
    if "시간외" in time_zone:
        # 시간외 상승 상위 50개, 하락 상위 50개, 거래량 상위 50개망을 정밀 조준 결합
        for sosok in [0, 1]: # 코스피, 코스닥
            api_urls.append(f"https://m.stock.naver.com/api/json/sise/siseListJson.nhn?menu=overtime_rise&sosok={sosok}&pageSize=50&page=1")
            api_urls.append(f"https://m.stock.naver.com/api/json/sise/siseListJson.nhn?menu=overtime_fall&sosok={sosok}&pageSize=50&page=1")
            api_urls.append(f"https://m.stock.naver.com/api/json/sise/siseListJson.nhn?menu=overtime_aq&sosok={sosok}&pageSize=50&page=1")
            
    # CASE 2: 사용자가 [일반 정규장]을 선택한 경우 -> 정규장 전용 랭킹 및 시세판 API 연동
    else:
        if mode == "③ 당일 등락률 구간 지정":
            for sosok in [0, 1]:
                for t in ["rise", "fall"]:
                    api_urls.append(f"https://m.stock.naver.com/api/json/sise/siseListJson.nhn?menu={t}&sosok={sosok}&pageSize=50&page=1")
        else:
            for sosok in [0, 1]:
                api_urls.append(f"https://m.stock.naver.com/api/json/sise/siseListJson.nhn?menu=market_sum&sosok={sosok}&pageSize=100&page=1")

    # API 호출 및 표준 데이터 규격화 연산
    for url in api_urls:
        try:
            res = requests.get(url, headers=headers, timeout=3.0)
            data = res.json()
            items = data.get('result', {}).get('itemList', [])
            
            for item in items:
                status_code = int(item.get('ms', 3))
                raw_change = float(item.get('cr', 0.0))
                
                # 마이너스(-) 부호 소실 방지 보정 로직
                if status_code in [4, 5]:
                    day_change_pct = -abs(raw_change)
                else:
                    day_change_pct = abs(raw_change)

                # 거래대금 연산 (시간외용 데이터 키 규격 매핑 보완)
                raw_aa = item.get('aa', 0)
                turnover_hundred_m = int(float(raw_aa) / 100) if raw_aa else 0

                results.append({
                    '종목명': item.get('nm'),
                    '현재가': int(item.get('nv', 0)),
                    '정규장 등락률': day_change_pct,
                    '당일 거래대금 (억 원)': turnover_hundred_m,
                    '실시간 거래량 (주)': int(item.get('aq', 0))
                })
        except:
            continue
            
    df = pd.DataFrame(results)
    if not df.empty:
        df = df.drop_duplicates(subset=['종목명']).reset_index(drop=True)
    return df

# 3. 데이터 수집 및 조건 필터링 가동
if st.sidebar.button("검색기 돌리기 🚀"):
    utc_now = datetime.now(timezone.utc)
    kst_now = utc_now + timedelta(hours=9)
    now_time = kst_now.strftime("%Y-%m-%d %H:%M:%S")
    
    with st.spinner(f"♻️ [{market_time_zone}] 조건에 따라 데이터망 정밀 분석 중..."):
        try:
            # 시간대 분리형 API 가동
            total_df = fetch_segmented_naver_data(market_time_zone, search_mode)
            
            if total_df.empty:
                st.warning(f"⚠️ 현재 [{market_time_zone}] 데이터가 비어있거나 마켓 점검 중입니다. 정규장외 시간이라면 '시간외 시세' 모드로 변경해 보세요.")
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
                    elif search_mode == "② 거래대금 구간 지정":
                        if min_turnover <= turnover_hundred_m <= max_turnover:
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
                elif search_mode == "② 거래대금 구간 지정":
                    result_df = result_df.sort_values(by='당일 거래대금 (억 원)', ascending=False)
                elif search_mode == "③ 당일 등락률 구간 지정":
                    result_df = result_df.sort_values(by='정규장 등락률', ascending=False)
                    
                result_df = result_df.reset_index(drop=True)
                
                # 결과 컬럼명 동적 변경 조절 (시간외 가독성 최적화)
                target_col_name = "정규장 등락률" if "일반" in market_time_zone else "시간외 등락률"
                result_df = result_df.rename(columns={'정규장 등락률': target_col_name})
                
                st.success(f"🎯 [{market_time_zone}] 필터링 완료! {len(result_df)}개의 종목을 포착했습니다.")
                
                display_df = result_df.copy()
                display_df['현재가'] = display_df['현재가'].apply(lambda x: f"{x:,}원")
                display_df[target_col_name] = display_df[target_col_name].apply(lambda x: f"{x:+.2f}%" if x >= 0 else f"{x:.2f}%")
                display_df['당일 거래대금 (억 원)'] = display_df['당일 거래대금 (억 원)'].apply(lambda x: f"{x:,}억 원")
                display_df['실시간 거래량 (주)'] = display_df['실시간 거래량 (주)'].apply(lambda x: f"{x:,}주")
                display_df['전일대비 거래증가율(%)'] = display_df['전일대비 거래증가율(%)'].apply(lambda x: f"{x:,.1f}%")
                
                st.dataframe(display_df, use_container_width=True)
            else:
                st.info(f"선택하신 조건 및 마켓 시간대({market_time_zone}) 기준, 현재 필터링 조건에 매칭되는 종목이 마켓에 존재하지 않습니다.")
                    
        except Exception as e:
            st.error(f"마켓 분리 시스템 연산 처리 오류: {e}")
else:
    st.info("왼쪽 사이드바에서 상단의 [마켓 시간대]와 아래 [조건 범위]를 맞춘 뒤 [검색기 돌리기] 버튼을 눌러주세요.")
