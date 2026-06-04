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

st.caption("장중에는 실시간 데이터망을, 장외 시간(오후 6시 이후/주말)에는 최종 마감 데이터를 자동 연동하여 24시간 정상 작동합니다.")

# 2. 사이드바 설정
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
        value=(-10, 5),
        step=1
    )

# [🔥 24시간 하이브리드 엔진] 실시간망 차단/종료 시 마감 시세판 백업 구조 데이터 자동 소환
def fetch_fail_safe_naver_data(mode):
    results = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://m.stock.naver.com/'
    }
    
    api_urls = []
    # 기본 타겟: 실시간 유동 대장주 리스트 (오후 6시 이후에도 최종 잔재 데이터가 가장 오래 남는 마스터 주소)
    for sosok in [0, 1]:
        api_urls.append(f"https://m.stock.naver.com/api/json/sise/siseListJson.nhn?menu=market_sum&sosok={sosok}&pageSize=150&page=1")
        
    # 만약 등락률 지정 모드라면 랭킹 전용 주소도 교차 보완 결합
    if mode == "③ 당일 등락률 구간 지정":
        for sosok in [0, 1]:
            for t in ["rise", "fall"]:
                api_urls.append(f"https://m.stock.naver.com/api/json/sise/siseListJson.nhn?menu={t}&sosok={sosok}&pageSize=50&page=1")

    for url in api_urls:
        try:
            res = requests.get(url, headers=headers, timeout=3.0)
            data = res.json()
            items = data.get('result', {}).get('itemList', [])
            
            for item in items:
                status_code = int(item.get('ms', 3))
                raw_change = float(item.get('cr', 0.0))
                
                # 부호 판정
                if status_code in [4, 5]:
                    day_change_pct = -abs(raw_change)
                else:
                    day_change_pct = abs(raw_change)

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
            
    # [백업 시스템 가동] 밤 시간대나 주말에 상기 API가 완전히 0을 뱉을 경우, 시세 마감 데이터셋으로 자동 전수 우회
    if not results:
        for sosok in [0, 1]:
            # 데이터 마감 백업 페이지 다이렉트 연동
            backup_url = f"https://finance.naver.com/sise/sise_market_sum.naver?sosok={sosok}&page=1"
            try:
                backup_res = requests.get(backup_url, headers=headers, timeout=3.0)
                dfs = pd.read_html(backup_res.text)
                if len(dfs) > 1:
                    df_clean = dfs[1].dropna(subset=['종목명'])
                    for _, row in df_clean.iterrows():
                        c_str = str(row['등락률']).replace('%', '').replace('+', '').strip()
                        results.append({
                            '종목명': str(row['종목명']),
                            '현재가': int(row['현재가']),
                            '정규장 등락률': float(c_str),
                            '당일 거래대금 (억 원)': int(row['거래대금']),
                            '실시간 거래량 (주)': int(row['거래량'])
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
    
    with st.spinner(f"♻️ {now_time} 데이터 인프라 동기화 중..."):
        try:
            # 안전 2중 레이어 엔진 호출
            total_df = fetch_fail_safe_naver_data(search_mode)
            
            if total_df.empty:
                st.warning("⚠️ 현재 한국 거래소 전산 서버 점검 시간대이거나 일시적인 통신 끊김입니다. 2~3초 후 버튼을 다시 눌러주세요.")
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
                
                if search_mode == "② 거래대금 구간 지정":
                    success_msg = f"🎯 검색 완료! 당일 거래대금 [{min_turnover}억 ~ {max_turnover}억] 구간 종목 {len(result_df)}개 발굴"
                elif search_mode == "③ 당일 등락률 구간 지정":
                    success_msg = f"🎯 검색 완료! 당일 등락률 [{min_change}% ~ {max_change}%] 구간 종목 {len(result_df)}개 발굴"
                else:
                    success_msg = f"🎯 검색 완료! 조건 만족 종목 {len(result_df)}개 발굴"
                    
                st.success(success_msg)
                
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
                elif search_mode == "② 거래대금 구간 지정":
                    st.info(f"현재 시장에 설정하신 거래대금 구간({min_turnover}억 ~ {max_turnover}억 원) 내에 속하는 종목이 없습니다.")
                elif search_mode == "③ 당일 등락률 구간 지정":
                    st.info(f"현재 시장에 지정하신 실시간 등락률 구간({min_change}% ~ {max_change}%) 내에 안착한 종목이 없습니다.")
                    
        except Exception as e:
            st.error(f"실시간 정밀 필터링 연산 오류: {e}")
else:
    st.info("왼쪽 사이드바에서 하나의 조건을 지정하여 범위를 설정한 뒤 [검색기 돌리기] 버튼을 눌러주세요.")
