import streamlit as st
import pandas as pd
import pydeck as pdk

# 제목
st.title("🚇 서울 지하철 노선도 시각화")

# 데이터 불러오기
@st.cache_data
def load_data():
    df = pd.read_csv("station.csv")
    df.columns = df.columns.str.strip()  # 공백 제거
    return df

df = load_data()

# 데이터 확인
st.subheader("데이터 미리보기")
st.dataframe(df.head())

# 컬럼 자동 탐색
lat_col = None
lon_col = None
line_col = None
name_col = None

for col in df.columns:
    if 'lat' in col.lower() or '위도' in col:
        lat_col = col
    if 'lon' in col.lower() or 'lng' in col.lower() or '경도' in col:
        lon_col = col
    if 'line' in col.lower() or '노선' in col:
        line_col = col
    if 'name' in col.lower() or '역명' in col:
        name_col = col

# 필수 컬럼 확인
if not lat_col or not lon_col:
    st.error("❌ 위도(lat)와 경도(lon) 컬럼이 CSV 파일에 필요합니다.")
    st.stop()

# 노선 선택
if line_col:
    lines = df[line_col].unique()
    selected_lines = st.multiselect("표시할 노선을 선택하세요", lines, default=list(lines))
    filtered_df = df[df[line_col].isin(selected_lines)]
else:
    filtered_df = df

# 지도 표시
st.subheader("📍 지하철 노선도")
st.map(filtered_df[[lat_col, lon_col]])

# pydeck 고급 지도 시각화
st.subheader("🗺️ Pydeck 지도 (노선별 색상)")
if line_col:
    color_map = {line: [int(hash(line) % 255), int(hash(line*2) % 255), int(hash(line*3) % 255)] for line in df[line_col].unique()}
    filtered_df["color"] = filtered_df[line_col].map(color_map)
else:
    filtered_df["color"] = [[0, 128, 255]] * len(filtered_df)

layer = pdk.Layer(
    "ScatterplotLayer",
    data=filtered_df,
    get_position=f"[{lon_col}, {lat_col}]",
    get_fill_color="color",
    get_radius=80,
    pickable=True
)

view_state = pdk.ViewState(
    latitude=filtered_df[lat_col].mean(),
    longitude=filtered_df[lon_col].mean(),
    zoom=11,
    pitch=0
)

r = pdk.Deck(layers=[layer], initial_view_state=view_state, tooltip={"text": f"{name_col}: {{{name_col}}}\n노선: {{{line_col}}}"})
st.pydeck_chart(r)

