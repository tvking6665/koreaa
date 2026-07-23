import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from streamlit_folium import st_folium
import folium

# 1. 페이지 기본 설정 (와이드 모드)
st.set_page_config(
    page_title="STEELMANIA Dashboard",
    page_icon="📊",
    layout="wide"
)

# 커스텀 CSS (헤더 및 스타일 간소화)
st.markdown("""
    <style>
    .main .block-container { padding-top: 1.5rem; padding-bottom: 1.5rem; }
    div[data-testid="stMetricValue"] { font-size: 1.5rem; }
    </style>
""", unsafe_allow_html=True)

# 타이틀
st.title("🖥️ 경영 / 매출 관리 대시보드")

# 2. 사이드바 - 엑셀 파일 업로드
st.sidebar.header("📁 데이터 업로드")
uploaded_file = st.sidebar.file_uploader("엑셀 파일(.xlsx)을 업로드하세요", type=["xlsx", "csv"])

# 샘플 데이터 생성 함수 (업로드된 파일이 없을 경우 구도 확인용)
@st.cache_data
def load_sample_data():
    sales_df = pd.DataFrame({
        '매출처': ['(주)동작플랜지', '유승메탈(부산)', '백두에스티', '(주)동진워터텍'],
        '내용': ['STS CR SHEET 304 2B', 'STS CR COIL 304 1.2T', 'STS CR SHEET 304 1.2T', 'PLATE SS400 8T'],
        '수량': [30, 1, 100, 3],
        '중량': [648, 3000, 2628, 2799],
        '공급가': [2798400, 9600000, 9049600, 1959300],
        '입력시간': ['2026-02-28 04:23', '2026-02-28 04:22', '2026-02-28 04:21', '2026-02-28 04:21']
    })
    
    daily_df = pd.DataFrame({
        '일자': ['02-24', '02-12', '02-11'],
        '수량': [31, 100, 3],
        '중량': [3848, 2828, 2799],
        '공급가': [12398.4, 9049.6, 1959.3],
        '부가세': [1239.84, 904.96, 195.93],
        '합계금액': [13638.24, 9954.56, 2155.23]
    })
    
    return sales_df, daily_df

if uploaded_file is not None:
    # 엑셀 파일 읽기 (필요시 시트별로 분리 가능)
    sales_df = pd.read_excel(uploaded_file, sheet_name=0)
    daily_df = pd.read_excel(uploaded_file, sheet_name=1) if len(pd.ExcelFile(uploaded_file).sheet_names) > 1 else load_sample_data()[1]
else:
    st.sidebar.info("💡 업로드된 파일이 없어 **샘플 데이터**로 구도를 표시합니다.")
    sales_df, daily_df = load_sample_data()

# ==========================================
# 레이아웃 구도 작성 (3개 컬럼 구도)
# ==========================================

col1, col2, col3 = st.columns([1.2, 1.2, 1])

# ------------------------------------------
# 첫 번째 컬럼 (좌측): 최근 매출 / 채권 / 환율
# ------------------------------------------
with col1:
    st.subheader("📌 최근 매출현황")
    st.dataframe(sales_df, height=180, use_container_width=True)

    st.subheader("💰 채권현황")
    receivables = pd.DataFrame({
        '거래처': ['(주)중앙금속', '(주)동진워터텍', '(주)동작플랜지', '유승메탈(부산)', '백두에스티'],
        '잔액': [-1500000, 2155230, 3078240, 9780000, 9954560]
    })
    fig_rec = px.bar(
        receivables, y='거래처', x='잔액', orientation='h',
        text_auto=',d', color='잔액', color_continuous_scale='Blues'
    )
    fig_rec.update_layout(margin=dict(l=0, r=0, t=10, b=10), height=180, showlegend=False)
    st.plotly_chart(fig_rec, use_container_width=True)

    st.subheader("🌐 환율 정보 (08:35:00)")
    fx_data = pd.DataFrame({
        '코드': ['USD', 'EUR', 'JPY(100)', 'CNH'],
        '매매기준율': [1388.4, 1421.2, 910.2, 190.2],
        '전일대비': ['▲ 2.5', '▼ 1.1', '▲ 0.5', '▲ 0.2']
    })
    st.dataframe(fx_data, height=140, use_container_width=True)

# ------------------------------------------
# 두 번째 컬럼 (중앙): 일별 매출 / 수금지급 / 매출 현황 차트
# ------------------------------------------
with col2:
    st.subheader("📅 일별 매출현황")
    st.dataframe(daily_df, height=180, use_container_width=True)

    st.subheader("📈 수금지급 흐름")
    pay_data = pd.DataFrame({
        '날짜': ['02-03', '02-12', '02-19'],
        '금액': [110, 85, 125]
    })
    fig_pay = px.line(pay_data, x='날짜', y='금액', markers=True)
    fig_pay.update_layout(margin=dict(l=0, r=0, t=10, b=10), height=180)
    st.plotly_chart(fig_pay, use_container_width=True)

    st.subheader("📊 매출 구분 차트")
    chart_data = pd.DataFrame({
        '일자': ['02-24', '02-12', '02-11'],
        '수량': [10, 25, 15],
        '중량': [40, 60, 45],
        '공급가': [120, 90, 30]
    })
    fig_bar = px.bar(chart_data, x='일자', y=['수량', '중량', '공급가'], barmode='group')
    fig_bar.update_layout(margin=dict(l=0, r=0, t=10, b=10), height=200, legend=dict(orientation="h", y=-0.2))
    st.plotly_chart(fig_bar, use_container_width=True)

# ------------------------------------------
# 세 번째 컬럼 (우측): 재고 도넛차트 / 매출처 지도
# ------------------------------------------
with col3:
    st.subheader("📦 재고현황")
    stock_data = pd.DataFrame({
        '품목': ['STS CR COIL', 'STS CR SHEET'],
        '재고량': [4500, 2112]
    })
    fig_donut = px.pie(
        stock_data, values='재고량', names='품목', hole=0.6,
        color_discrete_sequence=['#1f77b4', '#a52a2a']
    )
    fig_donut.add_annotation(text="TOTAL<br><b>6,612 kg</b>", showarrow=False, font_size=14)
    fig_donut.update_layout(margin=dict(l=0, r=0, t=10, b=10), height=260, showlegend=False)
    st.plotly_chart(fig_donut, use_container_width=True)

    st.subheader("📍 주요 매출처 위치")
    # 서울 등촌동 부근 지도 (이미지 참고 좌표)
    m = folium.Map(location=[37.558, 126.860], zoom_start=13)
    folium.Marker([37.558, 126.860], popup="강서구 등촌동 매출처", tooltip="등촌동 거래처").add_to(m)
    st_folium(m, height=270, use_container_width=True)
