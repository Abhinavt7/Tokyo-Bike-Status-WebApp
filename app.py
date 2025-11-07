import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import random
from tokyo_helpers import query_station_status, get_station_latlon

# Page configuration
st.set_page_config(
    page_title="Tokyo Bike Status Tracker",
    page_icon="cycle_logo.png",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS styling
st.markdown("""
    <style>
    .metric-card {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        margin: 10px 0;
    }
    .status-good { color: #00b050; font-weight: bold; }
    .status-warning { color: #ffc000; font-weight: bold; }
    .status-critical { color: #ff0000; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# Sample data generation
# @st.cache_data

# URLs for Tokyo API endpoints
station_status_url = "https://api-public.odpt.org/api/v4/gbfs/docomo-cycle-tokyo/station_status.json"
station_info_url = "https://api-public.odpt.org/api/v4/gbfs/docomo-cycle-tokyo/station_information.json"

# Fetch live data from APIs
station_status_df = query_station_status(station_status_url)
station_info_df = get_station_latlon(station_info_url)

# Merge data on station_id
df = station_status_df.merge(station_info_df, on="station_id", how="left")

def get_random_availability(capacity):
    """Generate random bike availability"""
    return random.randint(0, capacity)

def get_status_color(bikes_available):
    """Determine status color based on availability"""
    if bikes_available > 3:
        return "green"
    elif bikes_available > 0:
        return "orange"
    else:
        return "red"

def format_timestamp(ts):
    """Format timestamp to readable datetime"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def calculate_utilization(bikes_available, capacity):
    """Calculate utilization percentage"""
    if capacity == 0:
        return 0
    return round((bikes_available / capacity) * 100, 2)

stations_base = station_status_df.merge(station_info_df, on="station_id", how="left")

stations_base = stations_base.to_dict(orient='records')

# Initialize or update session state
if 'last_update' not in st.session_state:
    st.session_state.last_update = datetime.now()
    st.session_state.stations = []
    for station in stations_base:
        station['bikes_available'] = get_random_availability(station['capacity'])
        station['docks_available'] = station['capacity'] - station['bikes_available']
        station['is_renting'] = True
        station['is_returning'] = True
        station['is_installed'] = True
        st.session_state.stations.append(station)

# Sidebar navigation
st.sidebar.title("Tokyo Bike Tracker")
st.sidebar.markdown("---")

page = st.sidebar.radio(
    "Navigate to:",
    ["Dashboard", "Stations", "Map", "Search", "Analytics", "Settings"],
    index=0
)

# Dashboard Page
if page == "Dashboard":
    st.title("Tokyo Bike Status Dashboard")
    
    df = pd.DataFrame(st.session_state.stations)
    
    # Key metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Stations", len(df))
    
    with col2:
        total_bikes = df['bikes_available'].sum()
        st.metric("Total Bikes Available", int(total_bikes))
    
    with col3:
        total_docks = df['docks_available'].sum()
        st.metric("Total Docks Available", int(total_docks))
    
    with col4:
        last_update_time = st.session_state.last_update.strftime("%H:%M:%S")
        st.metric("Last Updated", last_update_time)
    
    st.markdown("---")
    
    # Summary statistics
    col1, col2, col3 = st.columns(3)
    
    with col1:
        avg_bikes = df['bikes_available'].mean()
        st.info(f"Average Bikes/Station: **{avg_bikes:.1f}**")
    
    with col2:
        avg_utilization = calculate_utilization(df['bikes_available'].sum(), df['capacity'].sum())
        st.info(f"Average Utilization: **{avg_utilization:.1f}%**")
    
    with col3:
        stations_active = len(df[df['is_renting'] == True])
        st.success(f"Active Stations: **{stations_active}/{len(df)}**")
    
    st.markdown("---")
    #st.divider()
    
    # Recent activity
    st.subheader("Recent Status")
    recent_df = df[['station_id', 'name', 'bikes_available', 'capacity', 'region_id']].head(10)
    st.dataframe(recent_df, use_container_width=True)

# Stations Page
elif page == "Stations":
    st.title("All Stations")
    
    df = pd.DataFrame(st.session_state.stations)
    
    # Add utilization rate
    df['utilization_rate'] = df.apply(
        lambda row: calculate_utilization(row['bikes_available'], row['capacity']), axis=1
    )
    
    # Region filter
    regions = df['region_id'].unique()
    region_filter = st.selectbox(
        "Filter by Region ID:",
        ["All"] + sorted(map(str, regions))
    )
    
    if region_filter != "All":
        df = df[df['region_id'].astype(str) == region_filter]
    
    # Sort options
    sort_by = st.selectbox(
        "Sort by:",
        ["Bikes Available", "Utilization Rate", "Station Name", "Capacity"]
    )
    
    sort_map = {
        "Bikes Available": "bikes_available",
        "Utilization Rate": "utilization_rate",
        "Station Name": "name",
        "Capacity": "capacity"
    }
    
    df = df.sort_values(sort_map[sort_by], ascending=False)
    
    # Display table
    display_df = df[['station_id', 'name', 'bikes_available', 'capacity', 'docks_available', 'utilization_rate', 'region_id']].copy()
    display_df.columns = ['Station ID', 'Station Name', 'Bikes Available', 'Capacity', 'Docks Available', 'Utilization %', 'Region']
    
    st.dataframe(display_df, use_container_width=True)

# Map Page
elif page == "Map":
    st.title("Map_Tokyo")
    
    df = pd.DataFrame(st.session_state.stations)
    
    # Create map centered on Tokyo
    tokyo_center = [35.6762, 139.6503]
    m = folium.Map(
        location=tokyo_center,
        zoom_start=12,
        tiles="OpenStreetMap"
    )
    
    # Add station markers
    for idx, row in df.iterrows():
        color = get_status_color(row['bikes_available'])
        
        popup_text = f"""
        <b>{row['name']}</b><br>
        Bikes: {row['bikes_available']}/{row['capacity']}<br>
        Docks: {row['docks_available']}<br>
        Region ID: {row['region_id']}<br>
        Station ID: {row['station_id']}
        """
        
        folium.CircleMarker(
            location=[row['lat'], row['lon']],
            radius=8 + (row['bikes_available'] / max (row['capacity'],1)) * 5,
            popup=folium.Popup(popup_text, max_width=250),
            color=color,
            fill=True,
            fillColor=color,
            fillOpacity=0.7,
            weight=2
        ).add_to(m)
    
    st_folium(m, width=1400, height=600)

# Search Page
elif page == "Search":
    st.title("Station Details")
    
    df = pd.DataFrame(st.session_state.stations)
    
    # Select station
    station_name = st.selectbox(
        "Select a Station:",
        df['name'].unique()
    )
    
    station_data = df[df['name'] == station_name].iloc[0]
    
    # Display station details
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader(f"{station_data['name']}")
        st.write(f"**Station ID:** {station_data['station_id']}")
        st.write(f"**Region ID:** {station_data['region_id']}")
        st.write(f"**Latitude:** {station_data['lat']}")
        st.write(f"**Longitude:** {station_data['lon']}")
    
    with col2:
        st.subheader("Availability")
        st.metric("Bikes Available", int(station_data['bikes_available']), delta=f"of {int(station_data['capacity'])}")
        st.metric("Docks Available", int(station_data['docks_available']))
        st.metric("Utilization Rate", f"{calculate_utilization(station_data['bikes_available'], station_data['capacity'])}%")
    
    st.markdown("---")
    
    # Status indicators
    col1, col2, col3 = st.columns(3)
    
    with col1:
        status = "Renting" if station_data['is_renting'] else "Not Renting"
        st.write(status)
    
    with col2:
        status = "Returning" if station_data['is_returning'] else "Not Returning"
        st.write(status)
    
    with col3:
        status = "Installed" if station_data['is_installed'] else "Not Installed"
        st.write(status)
    
    st.markdown("---")
    st.write(f"**Last Updated:** {format_timestamp(None)}")

# Analytics Page
elif page == "Analytics":
    st.title("Analytics & Statistics")
    
    df = pd.DataFrame(st.session_state.stations)
    df['utilization_rate'] = df.apply(
        lambda row: calculate_utilization(row['bikes_available'], row['capacity']), axis=1
    )
    
    # Charts
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Bike Availability Distribution")
        fig = px.histogram(df, x='bikes_available', nbins=15, title="Distribution of Bikes Available")
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("Stations by Region")
        region_counts = df['region_id'].value_counts()
        fig = px.pie(values=region_counts.values, names=region_counts.index, title="Stations by Region")
        st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Utilization Rate Distribution")
        fig = px.histogram(df, x='utilization_rate', nbins=15, title="Utilization Rate Distribution", labels={'utilization_rate': 'Utilization %'})
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("Capacity vs Bikes Available")
        fig = px.scatter(df, x='capacity', y='bikes_available', hover_data=['name'], title="Capacity vs Bikes Available")
        st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Top 5 Stations with Most Bikes")
        top_bikes = df.nlargest(5, 'bikes_available')[['name', 'bikes_available', 'capacity']]
        st.dataframe(top_bikes, use_container_width=True)
    
    with col2:
        st.subheader("Top 5 Stations with Most Empty Docks")
        top_docks = df.nlargest(5, 'docks_available')[['name', 'docks_available', 'capacity']]
        st.dataframe(top_docks, use_container_width=True)

# Settings Page
elif page == "Settings":
    st.title("Settings & Configuration")
    
    st.subheader("Data Management")
    
    if st.button("Refresh Data", key="refresh_button"):
        st.session_state.last_update = datetime.now()
        st.session_state.stations = []
        for station in stations_base:
            station['bikes_available'] = get_random_availability(station['capacity'])
            station['docks_available'] = station['capacity'] - station['bikes_available']
            station['is_renting'] = True
            station['is_returning'] = True
            station['is_installed'] = True
            st.session_state.stations.append(station)
        st.success("Data refreshed!")
        st.rerun()
    
    st.markdown("---")
    st.subheader("Application Information")
    
    info_col1, info_col2 = st.columns(2)
    
    with info_col1:
        st.write("**Application Name:** Tokyo Bike Status Tracker")
        st.write("**Version:** 1.0.0")
        st.write("**Last Updated:** " + st.session_state.last_update.strftime("%Y-%m-%d %H:%M:%S"))
    
    with info_col2:
        st.write("**Total Stations:** " + str(len(st.session_state.stations)))
        st.write("**Data Source:** Sample Data (Real API Integration Available)")
        st.write("**Update Frequency:** Manual/On Demand")
    
    st.markdown("---")
    st.subheader("About")
    st.write("""
    The Tokyo Bike Status Tracker provides real-time information about bike-sharing station status across Tokyo.
    
    **Features:**
    - Real-time station availability
    - Interactive maps with station locations
    - Analytics and statistics
    - Station search and detailed information
    - Regional filtering and sorting
    
    For integration with real API, use the `tokyo_helpers.py` module.
    """)
