import streamlit as st
import geopandas as gpd
import pandas as pd
import pydeck as pdk

# ------------------ CONFIG ------------------
st.set_page_config(page_title="Urban Drainage System", layout="wide")
st.title("🌧 Urban Drainage Monitoring System")

# ------------------ LOAD PIPE DATA ------------------
@st.cache_data
def load_pipes():
    pipes = gpd.read_file("pipes_final_qgis.geojson")
    pipes = pipes.to_crs(epsg=4326)
    return pipes

pipes = load_pipes()

# ------------------ SIDEBAR ------------------
st.sidebar.header("Controls")

uploaded_file = st.sidebar.file_uploader(
    "Upload Evaluation CSV",
    type=["csv"]
)

view_option = st.sidebar.radio(
    "Select View",
    ["Pipes Network", "Drain Nodes"]
)

risk = st.sidebar.selectbox(
    "Select Risk Level",
    ["All", "SAFE", "STRESSED", "CRITICAL"]
)

search_id = st.sidebar.text_input("🔍 Search ID (Pipe / Drain)")

st.subheader(view_option)

# ------------------ COLOR FUNCTION ------------------
def get_color(status):
    status = str(status).strip().upper()

    if status == "CRITICAL":
        return [255, 0, 0]
    elif status == "STRESSED":
        return [255, 165, 0]
    elif status == "SAFE":
        return [0, 255, 0]
    else:
        return [200, 200, 200]

# =========================================================
# ------------------ PIPES VIEW ------------------
# =========================================================
if view_option == "Pipes Network":

    if uploaded_file:

        df = pd.read_csv(uploaded_file)
        df.columns = df.columns.str.strip()

        # ---------------- SAFETY CHECK ----------------
        if "Pipe_ID" not in df.columns:
            st.error("CSV must contain Pipe_ID column")
            st.stop()

        # ---------------- RENAME ----------------
        df = df.rename(columns={
            "Failure_Prob": "Failure_Probability",
            "Utilization_Ratio_x": "Utilization",
            "Status_Label": "Pipe_Status"
        })

        # ---------------- CLEAN BASE DATA ----------------
        pipes_clean = pipes.copy()

        pipes_clean = pipes_clean.drop(columns=[
            "Utilization",
            "Failure_Probability",
            "Pipe_Status"
        ], errors="ignore")

        # Clean IDs
        df["Pipe_ID"] = df["Pipe_ID"].astype(str).str.strip().str.upper()
        pipes_clean["Pipe_ID"] = pipes_clean["Pipe_ID"].astype(str).str.strip().str.upper()

        # ---------------- MERGE ----------------
        pipes_clean = pipes_clean.merge(df, on="Pipe_ID", how="left")

        # Remove duplicate columns
        pipes_clean = pipes_clean.loc[:, ~pipes_clean.columns.duplicated()]

        # ---------------- HANDLE STATUS ----------------
        if "Pipe_Status" not in pipes_clean.columns:
            pipes_clean["Pipe_Status"] = "SAFE"
        else:
            pipes_clean["Pipe_Status"] = pipes_clean["Pipe_Status"].fillna("SAFE")

        pipes_clean["Pipe_Status"] = (
            pipes_clean["Pipe_Status"].astype(str).str.strip().str.upper()
        )

        # ---------------- FILTER ----------------
        filtered_pipes = pipes_clean.copy()

        if risk != "All":
            filtered_pipes = filtered_pipes[
                filtered_pipes["Pipe_Status"] == risk
            ]

        # ---------------- SEARCH ----------------
        if search_id:
            searched = filtered_pipes[
                filtered_pipes["Pipe_ID"].str.contains(
                    search_id.upper(),
                    case=False,
                    na=False
                )
            ]

            if not searched.empty:
                filtered_pipes = searched

        # ---------------- COLOR ----------------
        filtered_pipes = filtered_pipes.copy()
        filtered_pipes["color"] = filtered_pipes["Pipe_Status"].apply(get_color)

        # ---------------- MAP ----------------
        if not filtered_pipes.empty:

            layer = pdk.Layer(
                "GeoJsonLayer",
                data=filtered_pipes.__geo_interface__,
                get_line_color="properties.color",
                line_width_min_pixels=5,
                line_width_max_pixels=30,
                pickable=True,
            )

            # AUTO ZOOM
            if search_id:
                lat = filtered_pipes.geometry.centroid.y.iloc[0]
                lon = filtered_pipes.geometry.centroid.x.iloc[0]
                zoom_level = 15
            else:
                lat = filtered_pipes.geometry.centroid.y.mean()
                lon = filtered_pipes.geometry.centroid.x.mean()
                zoom_level = 13

            view_state = pdk.ViewState(
                latitude=lat,
                longitude=lon,
                zoom=zoom_level
            )

            st.pydeck_chart(
                pdk.Deck(
                    layers=[layer],
                    initial_view_state=view_state,
                    tooltip={
                        "html": "<b>Pipe:</b> {Pipe_ID}<br/>"
                                "<b>Status:</b> {Pipe_Status}<br/>"
                                "<b>Failure:</b> {Failure_Probability}"
                    }
                )
            )

            with st.expander("📊 View Pipe Data"):
                st.dataframe(filtered_pipes)

        else:
            st.warning("No pipe data to display")

    else:
        st.info("Please upload a CSV file to view pipes network")

# =========================================================
# ------------------ DRAIN NODES VIEW ------------------
# =========================================================
elif view_option == "Drain Nodes":

    if uploaded_file:

        drains = pd.read_csv(uploaded_file)
        drains.columns = drains.columns.str.strip()

        # Fix column names
        if "lat" in drains.columns:
            drains = drains.rename(columns={"lat": "latitude"})

        if "lon" in drains.columns:
            drains = drains.rename(columns={"lon": "longitude"})

        # Required columns
        required_cols = ["latitude", "longitude", "Operational_Status"]

        for col in required_cols:
            if col not in drains.columns:
                st.error(f"Missing column: {col}")
                st.stop()

        # Fix Data
        drains["Operational_Status"] = (
            drains["Operational_Status"]
            .fillna("SAFE")
            .astype(str)
            .str.strip()
            .str.upper()
        )

        # ---------------- FILTER ----------------
        filtered_drains = drains.copy()

        if risk != "All":
            filtered_drains = filtered_drains[
                filtered_drains["Operational_Status"] == risk
            ]

        # ---------------- SEARCH ----------------
        if search_id and "Drain_ID" in filtered_drains.columns:
            searched = filtered_drains[
                filtered_drains["Drain_ID"]
                .astype(str)
                .str.contains(search_id, case=False, na=False)
            ]

            if not searched.empty:
                filtered_drains = searched

        # ---------------- COLOR ----------------
        filtered_drains = filtered_drains.copy()
        filtered_drains["color"] = filtered_drains["Operational_Status"].apply(get_color)

        # ---------------- MAP ----------------
        if not filtered_drains.empty:

            layer = pdk.Layer(
                "ScatterplotLayer",
                data=filtered_drains,
                get_position='[longitude, latitude]',
                get_fill_color="color",
                radius_min_pixels=6,
                radius_max_pixels=40,
                pickable=True,
            )

            # AUTO ZOOM
            if search_id:
                lat = filtered_drains["latitude"].iloc[0]
                lon = filtered_drains["longitude"].iloc[0]
                zoom_level = 16
            else:
                lat = filtered_drains["latitude"].mean()
                lon = filtered_drains["longitude"].mean()
                zoom_level = 12

            view_state = pdk.ViewState(
                latitude=lat,
                longitude=lon,
                zoom=zoom_level
            )

            st.pydeck_chart(
                pdk.Deck(
                    layers=[layer],
                    initial_view_state=view_state,
                    tooltip={
                        "html": "<b>Drain:</b> {Drain_ID}<br/>"
                                "<b>Status:</b> {Operational_Status}"
                    }
                )
            )

            st.dataframe(filtered_drains)
            st.write("Filtered rows:", len(filtered_drains))

        else:
            st.warning("No drain nodes match the selected filters")

    else:
        st.info("Please upload a CSV file to view drain nodes")
