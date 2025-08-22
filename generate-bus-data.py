#!/usr/bin/env python3
"""
Generate MBTA bus data from GTFS files.
This script extracts ALL bus routes, not just a subset.
"""

import pandas as pd
import json
from pathlib import Path
from tqdm import tqdm
import os

def load_gtfs_data():
    """Load GTFS data from files."""
    print("Loading GTFS data...")
    
    # Check if GTFS files exist
    gtfs_dir = Path("mbta_gtfs")
    if not gtfs_dir.exists():
        print("Error: GTFS directory not found. Please place your GTFS files in a 'mbta_gtfs' folder.")
        return None, None, None
    
    # Load routes
    routes_file = gtfs_dir / "routes.txt"
    if not routes_file.exists():
        print("Error: routes.txt not found in GTFS directory")
        return None, None, None
    
    routes_df = pd.read_csv(routes_file)
    print(f"Loaded {len(routes_df)} routes from GTFS")
    
    # Load stops
    stops_file = gtfs_dir / "stops.txt"
    if not stops_file.exists():
        print("Error: stops.txt not found in GTFS directory")
        return None, None, None
    
    stops_df = pd.read_csv(stops_file)
    print(f"Loaded {len(stops_df)} stops from GTFS")
    
    # Load stop_times
    stop_times_file = gtfs_dir / "stop_times.txt"
    if not stop_times_file.exists():
        print("Error: stop_times.txt not found in GTFS directory")
        return None, None, None
    
    stop_times_df = pd.read_csv(stop_times_file)
    print(f"Loaded {len(stop_times_df)} stop times from GTFS")
    
    # Load trips
    trips_file = gtfs_dir / "trips.txt"
    if not trips_file.exists():
        print("Error: trips.txt not found in GTFS directory")
        return None, None, None
    
    trips_df = pd.read_csv(trips_file)
    print(f"Loaded {len(trips_df)} trips from GTFS")
    
    # Load shapes (optional)
    shapes_file = gtfs_dir / "shapes.txt"
    shapes_df = None
    if shapes_file.exists():
        shapes_df = pd.read_csv(shapes_file)
        print(f"Loaded {len(shapes_df)} shape points from GTFS")
    
    return routes_df, stops_df, stop_times_df, trips_df, shapes_df

def get_bus_routes(routes_df):
    """Get ONLY bus routes (route_type 3), excluding shuttles."""
    # First, let's see what columns we actually have
    print("Available columns in routes.txt:", list(routes_df.columns))
    
    # Filter for ONLY bus routes (route_type 3)
    bus_routes = routes_df[routes_df['route_type'] == 3].copy()

    return bus_routes

def get_route_stops(route_id, trips_df, stop_times_df, stops_df, route_trips_dict):
    """Get all stops for a specific route using the working approach from the train script."""
    # Use the same approach as the working train script
    # Check if this route has any trips
    if route_id not in route_trips_dict or not route_trips_dict[route_id]:
        return []
    
    # Get trip IDs for this route
    trip_ids = route_trips_dict[route_id]
    
    # Find stop times for these trips
    route_stop_times = stop_times_df[stop_times_df['trip_id'].isin(trip_ids)]
    
    if route_stop_times.empty:
        return []
    
    # Get unique stops in order
    route_stops = route_stop_times.sort_values(['trip_id', 'stop_sequence']).drop_duplicates(subset=['stop_id'])
    
    # Get stop details
    stop_ids = route_stops['stop_id'].unique()
    route_stop_details = stops_df[stops_df['stop_id'].isin(stop_ids)]
    
    # Create stop objects
    stops = []
    for _, stop in route_stop_details.iterrows():
        stop_obj = {
            'name': stop['stop_name'],
            'coords': [float(stop['stop_lat']), float(stop['stop_lon'])],
            'type': 'Bus',
            'stopId': str(stop['stop_id'])
        }
        stops.append(stop_obj)
    
    return stops

def get_route_shapes(route_id, trips_df, shapes_df):
    """Get shape data for a route if available."""
    if shapes_df is None:
        return []
    
    # Get trips for this route
    route_trips = trips_df[trips_df['route_id'] == route_id]
    if route_trips.empty:
        return []
    
    # Get shape IDs
    shape_ids = route_trips['shape_id'].dropna().unique()
    if len(shape_ids) == 0:
        return []
    
    # Get shape data
    shapes = []
    for shape_id in shape_ids:
        shape_data = shapes_df[shapes_df['shape_id'] == shape_id]
        if not shape_data.empty:
            # Sort by shape_pt_sequence
            shape_data = shape_data.sort_values('shape_pt_sequence')
            
            # Create coordinate array - Leaflet expects [lat, lng] format
            coords = []
            for _, point in shape_data.iterrows():
                coords.append([float(point['shape_pt_lat']), float(point['shape_pt_lon'])])
            
            if len(coords) > 1:  # Need at least 2 points for a line
                shapes.append({
                    'shape_id': str(shape_id),
                    'coords': coords
                })
    
    return shapes

def generate_bus_data():
    """Generate complete bus data."""
    print("Starting bus data generation...")
    
    # Load GTFS data
    gtfs_data = load_gtfs_data()
    if gtfs_data[0] is None:
        return
    
    routes_df, stops_df, stop_times_df, trips_df, shapes_df = gtfs_data
    
    # Get all routes to process
    all_routes = get_bus_routes(routes_df)
    
    # Build route_trips mapping first (like the working train script does)
    print("Building route-trips mapping...")
    route_trips_dict = {}
    
    for _, route in all_routes.iterrows():
        route_id = str(route['route_id'])
        route_trips_dict[route_id] = []
    
    # Populate route_trips_dict from trips.txt
    for _, trip in trips_df.iterrows():
        route_id = str(trip['route_id'])
        trip_id = str(trip['trip_id'])
        if route_id in route_trips_dict:
            route_trips_dict[route_id].append(trip_id)
    
    print(f"Built mapping for {len(route_trips_dict)} routes")
    
    # Now process stop_times.txt directly like the train script does
    print("Processing stop_times.txt to get route stops...")
    route_stops_dict = {}
    
    for _, route in all_routes.iterrows():
        route_id = str(route['route_id'])
        route_stops_dict[route_id] = set()
    
    # Process stop_times.txt line by line
    total_lines = len(stop_times_df)
    print(f"Processing {total_lines} stop-time records...")
    
    for idx, row in stop_times_df.iterrows():
        if idx % 100000 == 0:
            percent = (idx / total_lines) * 100
            print(f"Processed {idx} of {total_lines} ({percent:.1f}%)")
        
        trip_id = str(row['trip_id'])
        stop_id = str(row['stop_id'])
        
        # Find which route this trip belongs to
        for route_id in route_trips_dict:
            if trip_id in route_trips_dict[route_id]:
                route_stops_dict[route_id].add(stop_id)
                break
    
    print("Finished processing stop_times.txt")
    
    # Generate bus data
    mbta_bus_data = {}
    bus_route_shapes = {}
    
    print("Processing routes...")
    for _, route in all_routes.iterrows():
        route_id = str(route['route_id'])
        route_name = route['route_long_name']
        
        # Skip shuttle routes
        if pd.isna(route_name) or 'shuttle' in str(route_name).lower() or 'Shuttle-' in str(route_id):
            continue
        
        print(f"Processing route {route_id}: {route_name}")
        
        # Get stops for this route from the processed data
        stop_ids = route_stops_dict.get(route_id, set())
        stops = []
        
        for stop_id in stop_ids:
            stop_details = stops_df[stops_df['stop_id'] == stop_id]
            if not stop_details.empty:
                stop = stop_details.iloc[0]
                stop_obj = {
                    'name': stop['stop_name'],
                    'coords': [float(stop['stop_lat']), float(stop['stop_lon'])],
                    'type': 'Bus',
                    'stopId': str(stop['stop_id'])
                }
                stops.append(stop_obj)
        
        print(f"  Found {len(stops)} stops")
        
        # Debug route 71 specifically
        if route_id == '71':
            print(f"DEBUG Route 71:")
            print(f"  - Found {len(stops)} stops")
            print(f"  - Route name: {route_name}")
            # Check if route exists in trips
            route_trips = trips_df[trips_df['route_id'] == route_id]
            print(f"  - Found {len(route_trips)} trips")
            if not route_trips.empty:
                trip_ids = route_trips['trip_id'].unique()
                print(f"  - Trip IDs: {trip_ids[:5]}")  # Show first 5
                # Check stop times for these trips
                route_stop_times = stop_times_df[stop_times_df['trip_id'].isin(trip_ids)]
                print(f"  - Found {len(route_stop_times)} stop times")
                if not route_stop_times.empty:
                    unique_stops = route_stop_times['stop_id'].unique()
                    print(f"  - Unique stop IDs: {unique_stops[:10]}")  # Show first 10
                
                # Check if any of these trip IDs exist in stop_times at all
                print(f"  - Checking if trip IDs exist in stop_times.txt...")
                for trip_id in trip_ids[:3]:  # Check first 3
                    trip_stop_times = stop_times_df[stop_times_df['trip_id'] == trip_id]
                    print(f"    Trip {trip_id}: {len(trip_stop_times)} stop times")
                
                # Check data types
                print(f"  - Trip ID data type in trips.txt: {type(trip_ids[0])}")
                print(f"  - Trip ID data type in stop_times.txt: {type(stop_times_df['trip_id'].iloc[0]) if len(stop_times_df) > 0 else 'N/A'}")
                
                # Check if there are any stop_times at all
                print(f"  - Total stop_times in file: {len(stop_times_df)}")
                print(f"  - Sample stop_times trip_ids: {stop_times_df['trip_id'].head(5).tolist()}")
                
                # Check if any stop_times have route_id '71' (they might be stored differently)
                print(f"  - Checking if route 71 exists in stop_times...")
                if 'route_id' in stop_times_df.columns:
                    route_71_stop_times = stop_times_df[stop_times_df['route_id'] == '71']
                    print(f"    Found {len(route_71_stop_times)} stop times with route_id '71'")
                else:
                    print(f"    No 'route_id' column in stop_times.txt")
                
                # Check if any of the trip IDs from route 71 exist in stop_times at all
                print(f"  - Checking if any route 71 trip IDs exist in stop_times...")
                matching_trips = stop_times_df[stop_times_df['trip_id'].isin(trip_ids)]
                print(f"    Found {len(matching_trips)} stop times with matching trip IDs")
        
        # Get shapes for this route
        shapes = get_route_shapes(route_id, trips_df, shapes_df)
        
        # Create route data in the format HTML expects
        # Include routes that have either stops OR shapes OR both
        if stops or shapes:
            if stops:
                mbta_bus_data[route_id] = stops
            else:
                # If no stops but has shapes, create empty stops array
                mbta_bus_data[route_id] = []
        
        if shapes:
            bus_route_shapes[route_id] = shapes
    
    print(f"Generated data for {len(mbta_bus_data)} routes")
    print(f"Generated shapes for {len(bus_route_shapes)} routes")
    
    # Save to files
    output_dir = Path(".")
    
    # Save as JavaScript file
    js_file = output_dir / "mbta-bus-data.js"
    with open(js_file, 'w', encoding='utf-8') as f:
        f.write("const mbtaBusData = ")
        json.dump(mbta_bus_data, f, indent=2, ensure_ascii=False)
        f.write(";\n\n")
        
        f.write("const busRouteShapes = ")
        json.dump(bus_route_shapes, f, indent=2, ensure_ascii=False)
        f.write(";\n\n")
        
        
    
    print(f"Saved bus data to {js_file}")
    
    # Save as JSON file for reference
    json_file = output_dir / "mbta-bus-data.json"
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump({
            'mbtaBusData': mbta_bus_data,
            'busRouteShapes': bus_route_shapes
        }, f, indent=2, ensure_ascii=False)
    
    print(f"Saved JSON reference to {json_file}")
    
    # Print summary
    print("\n" + "="*50)
    print("BUS DATA GENERATION COMPLETE")
    print("="*50)
    print(f"Total routes processed: {len(mbta_bus_data)}")
    print(f"Routes with shapes: {len(bus_route_shapes)}")
    # Calculate routes that have both stops and shapes
    routes_with_both = set(mbta_bus_data.keys()) & set(bus_route_shapes.keys())
    routes_with_stops_only = set(mbta_bus_data.keys()) - set(bus_route_shapes.keys())
    routes_with_shapes_only = set(bus_route_shapes.keys()) - set(mbta_bus_data.keys())
    
    print(f"Routes with both stops and shapes: {len(routes_with_both)}")
    print(f"Routes with stops only: {len(routes_with_stops_only)}")
    print(f"Routes with shapes only: {len(routes_with_shapes_only)}")
    print(f"Total routes with data: {len(mbta_bus_data)}")
    print(f"Total routes with shapes: {len(bus_route_shapes)}")
    
    # Show some example routes
    print("\nExample routes:")
    for i, (route_id, stops) in enumerate(list(mbta_bus_data.items())[:5]):
        print(f"  {route_id}: {len(stops)} stops")
    
    if len(mbta_bus_data) > 5:
        print(f"  ... and {len(mbta_bus_data) - 5} more routes")

if __name__ == "__main__":
    generate_bus_data()
