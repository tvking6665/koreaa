import streamlit as st
from pykrx import stock
from datetime import datetime, timedelta
import pandas as pd

# 1. 웹 페이지 레이아웃 설정
st.set_page_config(page_title="국장 거래량 급증 검색기", layout="wide")
st.title("📈 한국 주식 거래량 급증 검색기")
st.caption("최근 영업일 기준 전일 대비 거래량이 급증한 종목을 실시간으로 검색합니다.")

# 2. 사이드바 설정 (조건 조절용)
st.sidebar.header("🔍 검색 조건 설정")
volume_ratio = st.sidebar.slider("거래량 증가율 조건 (%)", min_value=100, max_value=1000, value=300, step=50)

# 3. 데이터 수집 버튼
if st.sidebar.button("검색기 돌리기 🚀"):
    with st.spinner("한국 거래소 전체 종목 분석 중... 잠시만 기다려주세요."):
        try:
            # 최근 2영업일 날짜 구하기 (주말/공휴일 고려를 위해 5일치 확보 후 마지막 2일 사용)
            today = datetime.today().strftime("%Y%m%d")
            five_days_ago = (datetime.today() - timedelta(days=5)).strftime("%Y%m%d")
            
            # 종합 주가지수 데이터로 실제 영업일 목록 가져오기
            sample_df = stock.get_market_ohlcv_by_date(five_days_ago, today, "005930")
            trading_days = sample_df.index.strftime("%Y%m%d").tolist()
            
            if len(trading_days) < 2:
                st.error("영업일 데이터를 충분히 가져오지 못했습니다. 장 시작 전이거나 휴일일 수 있습니다.")
            else:
                prev_day = trading_days[-2]   # 전 영업일
                target_day = trading_days[-1] # 최근 영업일
                
                # 두 날짜의 전 종목 시세 데이터 가져오기
                df_prev = stock.get_market_ohlcv_by_ticker(prev_day, market="ALL")
                df_target = stock.get_market_ohlcv_by_ticker(target_day, market="ALL")
                
                # 필요한 컬럼만 추출 (종목명, 거래량, 종가)
                df_prev_vol = df_prev[['거래량']].rename(columns={'거래량': '전일거래량'})
                df_target_vol = df_target[['종목명', '종가', '거래량']].rename(columns={'거래량': '금일거래량'})
                
                # 두 데이터 병합
                merged_df = pd.merge(df_target_vol, df_prev_vol, left_index=True, right_index=True)
                
                # 전일 거래량이 0인 종목 제외 (나눗셈 에러 방지)
                merged_df = merged_df[merged_df['전일거래량'] > 0]
                
                # 거래량 증가율 계산 (%)
                merged_df['거래량 증가율(%)'] = round((merged_df['금일거래량'] / merged_df['전일거래량']) * 100, 2)
                
                # 사용자가 설정한 조건 (예: 300%) 이상인 종목만 필터링
                result_df = merged_df[merged_df['거래량 증가율(%)'] >= volume_ratio]
                
                # 정렬 및 포맷팅
                result_df = result_df.sort_values(by='거래량 증가율(%)', ascending=False)
                result_df.index.name = "종목코드"
                result_df = result_df.reset_index()
                
                # 결과 출력
                st.success(f"🔥 {target_day} 기준, 전일({prev_day}) 대비 거래량 {volume_ratio}% 이상 급증한 종목 {len(result_df)}개를 찾았습니다!")
                
                # 데이터 테이블 보기 좋게 출력
                st.dataframe(
                    result_df[['종목명', '종목코드', '종가', '전일거래량', '금일거래량', '거래량 증가율(%)']],
                    use_container_width=True
                )
        except Exception as e:
            st.error(f"데이터를 가져오는 중 오류가 발생했습니다: {e}")
else:
    st.info("왼쪽 사이드바에서 조건을 설정한 후 [검색기 돌리기] 버튼을 눌러주세요.")