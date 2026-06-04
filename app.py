import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta, timezone

# 1. 웹 페이지 레이아웃 설정
st.set_page_config(page_title="국장 정규장 조건 검색기", layout="wide")

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
    st.title("🇰🇷 한국 주식 정규장 기준 실시간 검색기")
with col2:
    if st.button("로그아웃 🔓"):
        st.session_state.logged_in = False
        st.rerun()

st.caption("장전/장후 시간외 거래를 배제하고, 오직 오전 9시~오후 3시 30분의 '정규장' 데이터를 기점으로 급등주를 발굴합니다.")

# 2. 사이드바 설정
st.sidebar.header("🔍 검색 모드 선택")
search_mode = st.sidebar.radio(
    "적용할 검색 조건을 선택하세요",
    ["① 거래량 급증", "② 대량 거래대금", "③ 당일 고상승률"]
)

st.sidebar.markdown("---")
st.sidebar.header("⚙️ 세부 수치 설정")

# [🔥 핵심 수정] 선택한 메뉴에 따라 '하나의 변수'만 화면에 띄우고 명확히 독립시킵니다.
if search_mode == "① 거래량 급증":
    volume_ratio = st.sidebar.slider("평균(5일) 대비 거래량 증가율 (%)", min_value=50, max_value=1000, value=250, step=50)
elif search_mode == "② 대량 거래대금":
    min_turnover = st.sidebar.number_input("최소 거래대금 조건 (백만 원)", min_value=0, value=10000, step=1000)
elif search_mode == "③ 당일 고상승률":
    min_change = st.sidebar.slider("당일 최소 상승률 조건 (%)", min_value=-10, max_value=30, value=8, step=1)

# 한국 시장 대장주 및 유동성 인기 종목 풀
@st.cache_data(ttl=3600)
def get_kr_tickers():
    kr_stocks = {
        '005930.KS': '삼성전자', '000660.KS': 'SK하이닉스', '005490.KS': 'POSCO홀딩스', '003550.KS': 'LG',
        '035420.KS': 'NAVER', '035720.KS': '카카오', '005380.KS': '현대차', '000270.KS': '기아',
        '003670.KS': '포스코퓨처엠', '373220.KS': 'LG에너지솔루션', '247540.KQ': '에코프로비엠', '086520.KQ': '에코프로',
        '196170.KQ': '알테오젠', '028300.KQ': 'HLB', '068270.KS': '셀트리온', '207940.KS': '삼성바이오로직스',
        '041510.KQ': '에스엠', '293490.KQ': '카카오게임즈', '253450.KQ': '스튜디오드래곤', '036570.KS': '엔씨소프트',
        '403340.KQ': '하이브', '001570.KS': '금양', '009830.KS': '한화솔루션', '012450.KS': '한화에어로스페이스',
        '003490.KS': '대한항공', '000100.KS': '유한양행', '112610.KQ': '씨젠', '015760.KS': '한국전력',
        '032640.KS': 'LG유플러스', '017670.KS': 'SK텔레콤', '010950.KS': 'S-Oil', '034730.KS': 'SK',
        '006400.KS': '삼성SDI', '010140.KS': '삼성중공업', '066570.KS': 'LG전자', '004020.KS': '현대제철',
        '011070.KS': 'LG이노텍', '009150.KS': '삼성전기', '034220.KS': 'LG디스플레이', '000810.KS': '삼성화재',
        '016360.KS': '삼성증권', '008770.KS': '호텔신라', '097950.KS': 'CJ제일제당', '030200.KS': 'KT',
        '051910.KS': 'LG화학', '051900.KS': 'LG생활건강', '090430.KS': '아모레퍼시픽'
    }
    return kr_stocks

# 3. 데이터 수집 및 조건 필터링 가동
if st.sidebar.button("검색기 돌리기 🚀"):
    utc_now = datetime.now(timezone.utc)
    kst_now = utc_now + timedelta(hours=9)
    now_time = kst_now.strftime("%Y-%m-%d %H:%M:%S")
    
    with st.spinner(f"♻️ {now_time} 기준 한국 시장 정규장 데이터 분석 중..."):
        try:
            ticker_map = get_kr_tickers()
            tickers_list = list(ticker_map.keys())
            
            end_date = datetime.today() + timedelta(days=1)
            start_date = end_date - timedelta(days=25)
            
            group_data = yf.download(tickers_list, start=start_date.strftime("%Y-%m-%d"), end=end_date.strftime("%Y-%m-%d"), group_by='ticker', prepost=False)
            
            results = []
            
            for ticker in tickers_list:
                if ticker in group_data.columns.levels[0]:
                    df_stock = group_data[ticker].dropna()
                    
                    if len(df_stock) >= 2:
                        # 정규장 마감 후 혹은 개장 전 빈 거래량 행 가드
                        if df_stock['Volume'].iloc[-1] == 0:
                            df_stock = df_stock.iloc[:-1]

                    if len(df_stock) >= 6:
                        latest_close = float(df_stock['Close'].iloc[-1])
                        prev_close = float(df_stock['Close'].iloc[-2])
                        latest_vol = float(df_stock['Volume'].iloc[-1])
                        latest_date = df_stock.index[-1].strftime("%Y-%m-%d")
                        
                        # 지표 연산
                        day_change_pct = round(((latest_close - prev_close) / prev_close) * 100, 2)
                        turnover_m = round((latest_close * latest_vol) / 1_000_000, 2)
                        five_day_avg_vol = df_stock['Volume'].iloc[-6:-1].mean()
                        vol_ratio_calc = round((latest_vol / five_day_avg_vol) * 100, 2) if five_day_avg_vol > 0 else 0
                        
                        # [🔥 핵심 수정] 라디오 버튼으로 선택한 '단 한 개의 조건'만 개별 판정합니다.
                        is_match = False
                        if search_mode == "① 거래량 급증" and vol_ratio_calc >= volume_ratio:
                            is_match = True
                        elif search_mode == "② 대량 거래대금" and turnover_m >= min_turnover:
                            is_match = True
                        elif search_mode == "③ 당일 고상승률" and day_change_pct >= min_change:
                            is_match = True
                            
                        if is_match:
                            results.append({
                                '종목명': ticker_map.get(ticker, ticker),
                                '종목코드': ticker.split('.')[0],
                                '정규장 종가': int(latest_close),
                                '정규장 등락률': day_change_pct,
                                '정규장 거래대금': turnover_m,
                                '5일 평균 거래량(정규)': int(five_day_avg_vol),
                                '당일 정규장 거래량': int(latest_vol),
                                '거래량 증가율(%)': vol_ratio_calc
                            })
            
            if results:
                result_df = pd.DataFrame(results)
                
                # 정렬 기준 매칭
                if search_mode == "① 거래량 급증":
                    result_df = result_df.sort_values(by='거래량 증가율(%)', ascending=False)
                elif search_mode == "② 대량 거래대금":
                    result_df = result_df.sort_values(by='정규장 거래대금', ascending=False)
                elif search_mode == "③ 당일 고상승률":
                    result_df = result_df.sort_values(by='정규장 등락률', ascending=False)
                    
                result_df = result_df.reset_index(drop=True)
                
                st.success(f"🎯 정규장 데이터 기준일({latest_date}) 기점, [{search_mode}] 조건을 만족하는 종목 {len(result_df)}개를 발굴했습니다!")
                
                display_df = result_df.copy()
                display_df['정규장 종가'] = display_df['정규장 종가'].apply(lambda x: f"{x:,}원")
                display_df['정규장 등락률'] = display_df['정규장 등락률'].apply(lambda x: f"{x:+.2f}%")
                display_df['정규장 거래대금'] = display_df['정규장 거래대금'].apply(lambda x: f"{int(x):,}백만 원")
                display_df['5일 평균 거래량(정규)'] = display_df['5일 평균 거래량(정규)'].apply(lambda x: f"{x:,}")
                display_df['당일 정규장 거래량'] = display_df['당일 정규장 거래량'].apply(lambda x: f"{x:,}")
                
                st.dataframe(display_df, use_container_width=True)
            else:
                # [🔥 핵심 수정] 안내 메시지도 내가 고른 조건 수치에 맞게 일치시켜 가독성을 올립니다.
                if search_mode == "① 거래량 급증":
                    st.info(f"선정된 종목 풀 내에 설정하신 거래량 조건(평균 대비 {volume_ratio}%)을 충족하는 종목이 현재 마켓에 없습니다.")
                elif search_mode == "② 대량 거래대금":
                    st.info(f"선정된 종목 풀 내에 설정하신 거래대금 조건({min_turnover:,}백만 원 이상)을 충족하는 종목이 현재 마켓에 없습니다.")
                elif search_mode == "③ 당일 고상승률":
                    st.info(f"선정된 종목 풀 내에 설정하신 등락률 조건({min_change}%)을 충족하는 종목이 현재 마켓에 없습니다.")
                
        except Exception as e:
            st.error(f"정규장 데이터 연산 오류: {e}")
else:
    st.info("왼쪽 사이드바에서 하나의 조건을 선택·설정한 후 [검색기 돌리기] 버튼을 눌러주세요.")
