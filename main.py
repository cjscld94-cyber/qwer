import streamlit as st
import pandas as pd
import pydeck as pdk
import numpy as np
import hashlib

st.set_page_config(page_title="지하철 노선도 시각화", layout="wide")

st.title("🗺️ 지하철/노선도 시각화 (Streamlit)")
st.markdown(
    """
- 로컬 또는 업로드한 `station.csv` 파일을 읽어 지도에 역(포인트)과 노선(라인)을 그립니다.
- 권장 컬럼: `station` (역명), `line` (호선/노선명), `lat`/`lon` 또는 `latitude`/`longitude`.
- 가능하면 같은 노선 내 역들의 '순서'를 나타내는 `order` 컬럼이 있으면 정확히 연결합니다.
"""
)

########################################
# Helpers
########################################
def detect_lat_lon(df: pd.DataFrame):
    cols = [c.lower() for c in df.columns]
    lat_candidates = []
    lon_candidates = []
    for c in df.columns:
        lc = c.lower()
        if "lat" in lc and "latt" not in lc:
            lat_candidates.append(c)
        if "lon" in lc or "lng" in lc or "long" in lc:
            lon_candidates.append(c)
        if lc == "y":
            lat_candidates.append(c)
        if lc == "x":
            lon_candidates.append(c)
    if lat_candidates and lon_candidates:
        return lat_candidates[0], lon_candidates[0]
    # try commonly used names
    for alt_lat in ["latitude", "lat"]:
        for alt_lon in ["longitude", "lon", "lng"]:
            if alt_lat in df.columns and alt_lon in df.columns:
                return alt_lat, alt_lon
    # try a single 'coords' column like "lat,lon"
    for c in df.columns:
        if "coord" in c.lower() or "point" in c.lower():
            return None, None  # signal to parse coords
    return None, None

def parse_coords_column(s):
    # try to parse strings like "lat,lon" or "POINT(lon lat)"
    s = str(s).strip()
    if "," in s:
        p = [x.strip() for x in s.split(",")]
        if len(p) >= 2:
            try:
                return float(p[0]), float(p[1])
            except:
                try:
                    return float(p[1]), float(p[0])
                except:
                    return None
    if s.lower().startswith("point"):
        # POINT(lon lat) or POINT(lat lon)
        inside = s[s.find("(")+1:s.rfind(")")]
        parts = inside.split()
        if len(parts) >= 2:
            try:
                a = float(parts[0]); b = float(parts[1])
                # geometry often uses lon lat
                return b, a
            except:
                return None
    return None

def line_to_color(line_name: str):
    # deterministic color from line name (returns [r,g,b])
    h = hashlib.md5(str(line_name).encode("utf8")).hexdigest()
    r = int(h[0:2], 16)
    g = int(h[2:4], 16)
    b = int(h[4:6], 16)
    # lighten colors a bit
    r = int(r * 0.8 + 50)
    g = int(g * 0.8 + 50)
    b = int(b * 0.8 + 50)
    return [r, g, b]

@st.cache_data(show_spinner=False)
def load_csv(path_or_buffer):
    # path_or_buffer can be path string or uploaded file
    df = pd.read_csv(path_or_buffer)
    return df

########################################
# UI: Load data
########################################
col1, col2 = st.columns([1, 3])
with col1:
    st.subheader("데이터 로드")
    uploaded = st.file_uploader("CSV 파일 업로드 (없으면 앱 루트의 station.csv 사용)", type=["csv"])
    sample_button = st.button("샘플 CSV 형식 보기")

with col2:
    st.subheader("설명")
    st.markdown(
        """
- `station.csv`가 앱과 같은 폴더에 있으면 자동으로 불러옵니다.
- 업로드를 하면 업로드한 파일을 우선 사용합니다.
- `order` 컬럼이 있으면 같은 라인 내 역들을 `order` 순으로 연결합니다. 없으면 파일 내 순서(또는 그룹에 따라 가까운 순서)를 사용합니다.
"""
    )

if sample_button:
    st.code(
"""station,line,lat,lon,order
Seoul Station,1,37.556,126.972,1
City Hall,1,37.565,126.976,2
Euljiro 1-ga,2,37.566,126.987,1
""",
    language="csv")

# Load df
try:
    if uploaded is not None:
        df = load_csv(uploaded)
        st.success("업로드한 CSV 파일을 사용합니다.")
    else:
        # try to open station.csv in working dir
        df = load_csv("station.csv")
        st.success("앱 내의 station.csv 파일을 불러왔습니다.")
except FileNotFoundError:
    st.error("station.csv 파일을 찾을 수 없습니다. 파일을 앱 폴더에 넣거나 업로드해 주세요.")
    st.stop()
except Exception as e:
    st.error(f"CSV 로딩 중 오류: {e}")
    st.stop()

st.write(f"데이터 프레임 크기: {df.shape[0]} rows × {df.shape[1]} columns")
st.dataframe(df.head(10))

########################################
# Detect lat/lon and preprocess
########################################
lat_col, lon_col = detect_lat_lon(df)

if lat_col and lon_col:
    st.info(f"위치 컬럼 자동탐지: lat → `{lat_col}` , lon → `{lon_col}`")
    df["__lat__"] = pd.to_numeric(df[lat_col], errors="coerce")
    df["__lon__"] = pd.to_numeric(df[lon_col], errors="coerce")
else:
    # try parse coords-like or find columns 'lat,lon' case-insensitive
    parsed = False
    for c in df.columns:
        if "coord" in c.lower() or "point" in c.lower():
            # try parse every row
            lats = []
            lons = []
            for v in df[c]:
                p = parse_coords_column(v)
                if p is None:
                    lats.append(np.nan); lons.append(np.nan)
                else:
                    lat, lon = p
                    lats.append(lat); lons.append(lon)
            df["__lat__"] = lats
            df["__lon__"] = lons
            parsed = True
            st.info(f"`{c}` 컬럼에서 좌표를 파싱했습니다.")
            break
    if not parsed:
        # fallback: try common names again more rigidly
        lowercols = [c.lower() for c in df.columns]
        if "latitude" in lowercols and "longitude" in lowercols:
            lat_col = df.columns[lowercols.index("latitude")]
            lon_col = df.columns[lowercols.index("longitude")]
            df["__lat__"] = pd.to_numeric(df[lat_col], errors="coerce")
            df["__lon__"] = pd.to_numeric(df[lon_col], errors="coerce")
            st.info("latitude/longitude 컬럼을 사용했습니다.")
        else:
            st.warning("위도/경도 컬럼을 자동으로 찾지 못했습니다. `lat`/`lon` 또는 `latitude`/`longitude` 컬럼명을 사용하거나 업로드 형식을 확인하세요.")
            # stop or let user map columns manually
            st.stop()

# drop rows without coords
before_n = df.shape[0]
df = df.dropna(subset=["__lat__", "__lon__"]).reset_index(drop=True)
after_n = df.shape[0]
if after_n < before_n:
    st.warning(f"{before_n-after_n}개의 행에서 좌표를 추출하지 못해 제외했습니다.")

# Ensure essential columns exist
name_col = None
for candidate in ["station", "name", "stop", "title"]:
    if candidate in [c.lower() for c in df.columns]:
        # pick original column name
        idx = [c.lower() for c in df.columns].index(candidate)
        name_col = df.columns[idx]
        break
if name_col is None:
    name_col = df.columns[0]  # fallback to first column
    st.info(f"역명 컬럼을 자동으로 `{name_col}`로 선택했습니다. 필요하면 CSV 컬럼명을 변경하세요.")

line_col = None
for candidate in ["line", "route", "branch"]:
    if candidate in [c.lower() for c in df.columns]:
        idx = [c.lower() for c in df.columns].index(candidate)
        line_col = df.columns[idx]
        break
# If no line column, treat all points as one line
if line_col is None:
    st.info("`line` 컬럼을 찾지 못했습니다. 모든 역을 단일 그룹으로 표시합니다.")
    df["_line_tmp_"] = "Line"
    line_col = "_line_tmp_"

# Optional order column
order_col = None
for candidate in ["order", "seq", "sequence", "idx"]:
    if candidate in [c.lower() for c in df.columns]:
        idx = [c.lower() for c in df.columns].index(candidate)
        order_col = df.columns[idx]
        st.info(f"노선 내 역 순서로 `{order_col}` 컬럼을 사용합니다.")
        break

########################################
# Build layers for pydeck
########################################
st.subheader("지도 옵션")

midpoint = [df["__lat__"].mean(), df["__lon__"].mean()]
zoom = st.slider("초기 줌 레벨", min_value=8, max_value=16, value=12)

show_lines = st.checkbox("노선(라인) 연결 표시", value=True)
show_stations = st.checkbox("역(포인트) 표시", value=True)
station_radius = st.slider("역 포인트 반경 (미터)", min_value=50, max_value=800, value=250)
line_width_px = st.slider("노선 굵기 (픽셀)", min_value=2, max_value=10, value=4)

layers = []

# Stations layer
if show_stations:
    stations_data = df.copy()
    stations_data["color"] = stations_data[line_col].apply(lambda x: line_to_color(x))
    # pydeck expects [lon, lat] for positions in some places, but for scatterplot_layer we use lat/lon keys defined below
    stations_layer = pdk.Layer(
        "ScatterplotLayer",
        data=stations_data,
        get_position=["__lon__", "__lat__"],
        get_fill_color="color",
        get_radius=station_radius,
        pickable=True,
        auto_highlight=True,
        radius_min_pixels=3,
    )
    layers.append(stations_layer)

# Lines layer: for each line, sort by order_col if present
if show_lines:
    line_segments = []
    unique_lines = df[line_col].fillna("Unknown").unique()
    for ln in unique_lines:
        sub = df[df[line_col] == ln].copy()
        if sub.empty or sub.shape[0] < 2:
            continue
        if order_col is not None:
            sub = sub.sort_values(by=order_col)
        else:
            # try to use file order; if not, do simple nearest-neighbor chaining for visual connectivity
            sub = sub.reset_index(drop=True)
            # if more than 2 nodes, sort by angle from centroid (stable visual order)
            if sub.shape[0] > 2:
                centroid_lat = sub["__lat__"].mean()
                centroid_lon = sub["__lon__"].mean()
                angles = np.arctan2(sub["__lat__"] - centroid_lat, sub["__lon__"] - centroid_lon)
                sub["__angle__"] = angles
                sub = sub.sort_values(by="__angle__")
        coords = sub[["__lon__", "__lat__"]].values.tolist()
        line_segments.append({
            "line": ln,
            "path": coords,
            "color": line_to_color(ln),
        })

    if line_segments:
        lines_layer = pdk.Layer(
            "PathLayer",
            data=line_segments,
            get_path="path",
            get_width=line_width_px,
            get_color="color",
            pickable=True,
            cap_style="round",
            joint_style="round",
        )
        layers.append(lines_layer)

# Tooltip
tooltip = {
    "html": f"<b>역명</b>: {{{name_col}}}<br/><b>노선</b>: {{{line_col}}}",
    "style": {
        "backgroundColor": "steelblue",
        "color": "white"
    }
}

view_state = pdk.ViewState(latitude=midpoint[0], longitude=midpoint[1], zoom=zoom, bearing=0, pitch=30)

r = pdk.Deck(layers=layers, initial_view_state=view_state, tooltip=tooltip)

st.subheader("지도")
st.write("아래 지도가 렌더링됩니다. 마커를 클릭하면 툴팁 정보를 볼 수 있습니다.")
st.pydeck_chart(r, use_container_width=True)

########################################
# Export / Download
########################################
st.subheader("데이터 및 맵 설정")
with st.expander("CSV 다운로드"):
    st.download_button("현재 데이터프레임을 CSV로 다운로드", data=df.to_csv(index=False).encode("utf-8"), file_name="station_processed.csv", mime="text/csv")

st.success("완료 — 지하철 노선도가 렌더링되었습니다.")
st.caption("문제가 있거나 컬럼명이 다르게 되어있으면 CSV를 열어 컬럼명을 표준화(lat,lon,line,station 등) 해주세요.")

