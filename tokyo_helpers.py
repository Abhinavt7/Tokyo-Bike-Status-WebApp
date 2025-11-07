import urllib  # Import module for working with URLs
import json  # Import module for working with JSON data
import pandas as pd  # Import pandas for data manipulation
import folium  # Import folium for creating interactive maps
import datetime as dt  # Import datetime for working with dates and times
from geopy.distance import geodesic  # Import geodesic for calculating distances
from geopy.geocoders import Nominatim  # Import Nominatim for geocoding
import streamlit as st  # Import Streamlit for creating web apps
import requests  # Import requests for making HTTP requests

@st.cache_data  # Cache the function's output to improve performance
def query_station_status(url):
    """Query station status from Tokyo bike-sharing API"""
    with urllib.request.urlopen(url) as data_url:  # Open the URL
        data = json.loads(data_url.read().decode())  # Read and decode the JSON data
        df = pd.DataFrame(data['data']['stations'])  # Convert the data to a DataFrame
    
    # Filter for active stations (renting and returning)
    df = df[df['is_renting'] == True]  # Filter out stations that are not renting
    df = df[df['is_returning'] == True]  # Filter out stations that are not returning
    df = df.drop_duplicates(['station_id', 'last_reported'])  # Remove duplicate records
    
    # Convert timestamp to datetime
    df['last_reported'] = df['last_reported'].map(lambda x: dt.datetime.utcfromtimestamp(x))
    
    # Add the last updated time to the DataFrame
    df['time'] = df['last_reported']  # Use last_reported as time index
    df.index = df['time']  # Set the time as the index
    df.index = df.index.tz_localize('UTC')  # Localize the index to UTC
    
    return df  # Return the DataFrame

def get_station_latlon(url):
    """Get station latitude and longitude from Tokyo bike-sharing API"""
    with urllib.request.urlopen(url) as data_url:  # Open the URL
        latlon = json.loads(data_url.read().decode())  # Read and decode the JSON data
        latlon = pd.DataFrame(latlon['data']['stations'])  # Convert the data to a DataFrame
    
    return latlon  # Return the DataFrame

def join_latlon(df1, df2):
    """Join two DataFrames on station_id"""
    df = df1.merge(df2[['station_id', 'lat', 'lon', 'name', 'capacity']],
                   how='left',
                   on='station_id')  # Merge the DataFrames on station_id
    
    return df  # Return the merged DataFrame

def get_marker_color(num_bikes_available):
    """Determine marker color based on the number of bikes available"""
    if num_bikes_available > 3:
        return 'green'
    elif 0 < num_bikes_available <= 3:
        return 'yellow'
    else:
        return 'red'

def geocode(address):
    """Geocode an address using Nominatim"""
    geolocator = Nominatim(user_agent="tokyo-bike-demo")  # Create a geolocator object
    try:
        location = geolocator.geocode(address)  # Geocode the address
        if location is None:
            return ''  # Return an empty string if the address is not found
        else:
            return (location.latitude, location.longitude)  # Return the latitude and longitude
    except:
        return ''  # Return empty string on error

def get_bike_availability(latlon, df):
    """Calculate distance from each station to the user and return closest station with available bikes"""
    i = 0
    df = df.copy()  # Create a copy to avoid modifying original
    df['distance'] = ''
    
    while i < len(df):
        df.loc[i, 'distance'] = geodesic(latlon, (df['lat'].iloc[i], df['lon'].iloc[i])).km  # Calculate distance to each station
        i = i + 1
    
    # Remove stations without available bikes
    df = df.loc[df['num_bikes_available'] > 0]
    
    if len(df) == 0:
        return None  # No available bikes
    
    chosen_station = []
    chosen_station.append(df[df['distance'] == min(df['distance'])]['station_id'].iloc[0])  # Get closest station
    chosen_station.append(df[df['distance'] == min(df['distance'])]['lat'].iloc[0])
    chosen_station.append(df[df['distance'] == min(df['distance'])]['lon'].iloc[0])
    
    return chosen_station  # Return the chosen station

def get_dock_availability(latlon, df):
    """Calculate distance from each station to the user and return closest station with available docks"""
    i = 0
    df = df.copy()  # Create a copy to avoid modifying original
    df['distance'] = ''
    
    while i < len(df):
        df.loc[i, 'distance'] = geodesic(latlon, (df['lat'].iloc[i], df['lon'].iloc[i])).km  # Calculate distance to each station
        i = i + 1
    
    # Remove stations without available docks
    df = df.loc[df['num_docks_available'] > 0]
    
    if len(df) == 0:
        return None  # No available docks
    
    chosen_station = []
    chosen_station.append(df[df['distance'] == min(df['distance'])]['station_id'].iloc[0])  # Get closest station
    chosen_station.append(df[df['distance'] == min(df['distance'])]['lat'].iloc[0])
    chosen_station.append(df[df['distance'] == min(df['distance'])]['lon'].iloc[0])
    
    return chosen_station  # Return the chosen station

def run_osrm(chosen_station, iamhere):
    """Run OSRM and get route coordinates and duration"""
    start = "{},{}".format(iamhere[1], iamhere[0])  # Format the start coordinates
    end = "{},{}".format(chosen_station[2], chosen_station[1])  # Format the end coordinates
    url = 'http://router.project-osrm.org/route/v1/driving/{};{}?geometries=geojson'.format(start, end)  # Create the OSRM API URL
    
    headers = {'Content-type': 'application/json'}
    
    try:
        r = requests.get(url, headers=headers)  # Make the API request
        print("Calling API ...:", r.status_code)  # Print the status code
        routejson = r.json()  # Parse the JSON response
        
        coordinates = []
        i = 0
        lst = routejson['routes'][0]['geometry']['coordinates']
        
        while i < len(lst):
            coordinates.append([lst[i][1], lst[i][0]])  # Extract coordinates
            i = i + 1
        
        duration = round(routejson['routes'][0]['duration'] / 60, 1)  # Convert duration to minutes
        
        return coordinates, duration  # Return the coordinates and duration
    except Exception as e:
        print(f"Error calling OSRM API: {e}")
        return None, None

def calculate_station_utilization(df):
    """Calculate utilization rate for each station"""
    if 'capacity' in df.columns:
        df['utilization_rate'] = (df['num_bikes_available'] / df['capacity'] * 100).round(2)
    return df

def filter_stations_by_region(df, region_id):
    """Filter stations by region_id"""
    if 'region_id' in df.columns:
        df = df[df['region_id'] == region_id]
    return df
