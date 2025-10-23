# streamlit_station_app.py
# Streamlit app for exploring Seoul subway station locations
# Save this file and run with: streamlit run streamlit_station_app.py
# Place station.csv in the same directory as this script.

import streamlit as st
import pandas as pd
import numpy as np
from math import radians, cos, sin, asin, sqrt

# Visualization
import plotly.express as px

# Try to import folium and streamlit_folium if available; fall back to st.map
try:
    import folium
    from streamlit_folium import st_folium
    FOLIUM_AVAILABLE = True
except Exception:
    FOLIUM_AVAILABLE = False

st.set_page_config(page_title="Seoul Station Explorer", layout="wide")

# ---------------------- Helper functions ----------------------
@st.cache_data
def load_data(path: str = "station.csv") -> pd.DataFrame:
    """Load station CSV with common Korean encodings fallback."""
    encodings = ["cp949", "euc-kr", "utf-8-sig", "utf-8"]
    for enc in encodings:
        try:
            df = pd.read_csv(path, encoding=enc)
            df.columns = df.columns.str.strip()
            return df
        except Exception:
            continue
    raise UnicodeDecodeError("Unable to read CSV with tried encodings.")


def haversine(lon1, lat1, lon2, lat2):
    # haversine distance in kilometers
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    km = 6371 * c
    return km

# ---------------------- App layout ----------------------
st.title("🚉 Seoul Subway Station Explorer")
st.markdown(
    "데이터를 불러와서 노선별 분포, 지도 시각화, 검색(위도/경도로 가장 가까운 역 찾기), 파일 다운로드를 할 수 있습니다."
)

# Load data
with st.spinner("데이터 불러오는 중…"):
    try:
        df = load_data("station.csv")
    except Exception as e:
        st.error(f"station.csv 파일을 불러오지 못했습니다: {e}")
        st.stop()

# Basic column standardization
expected_cols = {"역ID": None, "역명": None, "노선명": None, "위도": None, "경도": None}
cols_lower = {c.lower(): c for c in df.columns}
# Try to map typical Korean/English variations
col_map = {}
for exp in expected_cols.keys():
    lower = exp.lower()
    if lower in cols_lower:
        col_map[cols_lower[lower]] = exp
# If direct mapping not found, try fuzzy alternatives
candidates = {
    "id": ["id", "역id", "station_id"],
    "name": ["name", "역명", "station_name", "역"],
    "line": ["노선명", "line", "line_name", "노선"],
    "lat": ["위도", "latitude", "lat"],
    "lon": ["경도", "longitude", "lon", "lng"]
}
for std, opts in candidates.items():
    for o in opts:
        for c in df.columns:
            if c.lower() == o:
                if std == 'id':
                    df = df.rename(columns={c: '역ID'})
                elif std == 'name':
                    df = df.rename(columns={c: '역명'})
                elif std == 'line':
                    df = df.rename(columns={c: '노선명'})
                elif std == 'lat':
                    df = df.rename(columns={c: '위도'})
                elif std == 'lon':
                    df = df.rename(columns={c: '경도'})

# Ensure required columns exist
required = ["역ID", "역명", "노선명", "위도", "경도"]
if not all(c in df.columns for c in required):
    st.error("CSV에 필요한 열(역ID, 역명, 노선명, 위도, 경도)이 모두 포함되어 있지 않습니다. 열 이름을 확인해주세요.")
    st.write("현재 열:", df.columns.tolist())
    st.stop()

# Convert coords to numeric
for c in ["위도", "경도"]:
    df[c] = pd.to_numeric(df[c], errors="coerce")

# Sidebar controls
st.sidebar.header("필터 & 검색")
lines = ["전체"] + sorted(df["노선명"].astype(str).unique().tolist())
selected_line = st.sidebar.selectbox("노선 선택", lines)
search_name = st.sidebar.text_input("역명으로 검색 (부분일치 가능)")

st.sidebar.markdown("---")
st.sidebar.subheader("가장 가까운 역 찾기")
input_lat = st.sidebar.number_input("위도 (예: 37.55)", value=37.55, format="%.6f")
input_lon = st.sidebar.number_input("경도 (예: 126.97)", value=126.97, format="%.6f")
if st.sidebar.button("가까운 역 찾기"):
    df['distance_km'] = df.apply(lambda r: haversine(input_lon, input_lat, r['경도'], r['위도']), axis=1)
    nearest = df.sort_values('distance_km').iloc[0]
    st.sidebar.success(f"가장 가까운 역: {nearest['역명']} ({nearest['노선명']}) — {nearest['distance_km']:.3f} km")

st.sidebar.markdown("---")
st.sidebar.markdown("앱 설정")
if FOLIUM_AVAILABLE:
    st.sidebar.caption("지도: folium + streamlit_folium 사용")
else:
    st.sidebar.caption("지도: 기본 st.map 사용 (folium 또는 streamlit_folium 설치 권장)")

# Apply filters
filtered = df.copy()
if selected_line != "전체":
    filtered = filtered[filtered['노선명'] == selected_line]
if search_name:
    filtered = filtered[filtered['역명'].astype(str).str.contains(search_name, na=False)]

col1, col2 = st.columns([2, 1])
with col1:
    st.subheader("지도")
    if filtered.empty:
        st.info("필터 결과가 없습니다.")
    else:
        if FOLIUM_AVAILABLE:
            # Center map on mean coordinates
            mean_lat = filtered['위도'].mean()
            mean_lon = filtered['경도'].mean()
            m = folium.Map(location=[mean_lat, mean_lon], zoom_start=12)
            for _, r in filtered.iterrows():
                popup = f"<b>{r['역명']}</b><br/>{r['노선명']}"
                folium.CircleMarker([r['위도'], r['경도']], radius=5, popup=popup).add_to(m)
            st_folium(m, width="100%", height=600)
        else:
            # Use st.map as a fallback
            st.map(filtered.rename(columns={'위도':'lat','경도':'lon'})[['lat','lon']])

with col2:
    st.subheader("요약 통계")
    st.metric("필터된 역 수", len(filtered))
    st.write("노선 수:", filtered['노선명'].nunique())
    st.write("위도 평균 / 경도 평균:")
    st.write(filtered[['위도','경도']].mean().round(6))

    st.markdown("### 노선별 역 개수")
    counts = filtered['노선명'].value_counts().reset_index()
    counts.columns = ['노선명','역개수']
    st.dataframe(counts)

    # Download
    csv = filtered.to_csv(index=False).encode('utf-8-sig')
    st.download_button("필터된 CSV 다운로드", data=csv, file_name="stations_filtered.csv", mime='text/csv')

st.markdown("---")

# Plot: 노선별 역 개수 (전체 데이터 기준)
st.subheader("노선별 역 개수 (전체 데이터 기준)")
counts_all = df['노선명'].value_counts().reset_index()
counts_all.columns = ['노선명','역개수']
fig = px.bar(counts_all, x='노선명', y='역개수', text='역개수')
fig.update_layout(xaxis_title='노선', yaxis_title='역 개수', xaxis_tickangle=-45, height=400)
st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

# Show table and allow selecting a row to highlight on the map
st.subheader("역 목록")
st.dataframe(filtered.reset_index(drop=True))

st.info("사용법: station.csv 파일을 앱 폴더에 넣고 Streamlit Cloud에 배포하세요. requirements.txt에 folium, streamlit_folium, plotly를 추가하면 지도/그래프가 향상됩니다.")

# End of file
