#!/usr/bin/env python3
"""
Generate MBTA bus data using MBTA's V3 API for shapes.
This should give us complete shape data for all routes.
"""

import requests
import json
from pathlib import Path
from tqdm import tqdm
import time

def get_bus_routes():
    """Get all bus routes from MBTA API"""
    print("Fetching bus routes from MBTA API...")
    
    url = "https://api-v3.mbta.com/routes"
    params = {
        'filter[type]': '3',  # Bus routes only
        'page[limit]': 1000
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        
        data = response.json()
        routes = data.get('data', [])
        
        print(f"Found {len(routes)} bus routes")
        return routes
        
    except Exception as e:
        print(f"Error fetching routes: {e}")
        return []

def get_route_shapes(route_id):
    """Get shapes for a specific route"""
    url = "https://api-v3.mbta.com/shapes"
    params = {
        'filter[route]': route_id,
        'page[limit]': 100
    }
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.get(url, params=params)
            
            if response.status_code == 429:  # Rate limited
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2  # Progressive backoff
                    print(f"Rate limited, waiting {wait_time} seconds...")
                    time.sleep(wait_time)
                    continue
                else:
                    print(f"Rate limited after {max_retries} attempts for route {route_id}")
                    return []
            
            response.raise_for_status()
            
            data = response.json()
            shapes = data.get('data', [])
            
            # Convert encoded polylines to coordinate arrays
            decoded_shapes = []
            for shape in shapes:
                if 'polyline' in shape.get('attributes', {}):
                    encoded_polyline = shape['attributes']['polyline']
                    # For now, we'll store the encoded polyline - Leaflet can decode it directly
                    decoded_shapes.append({
                        'shape_id': shape['id'],
                        'polyline': encoded_polyline
                    })
            
            return decoded_shapes
            
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"Error fetching shapes for route {route_id} (attempt {attempt + 1}): {e}")
                time.sleep(2)
                continue
            else:
                print(f"Error fetching shapes for route {route_id} after {max_retries} attempts: {e}")
                return []
    
    return []

def get_route_stops(route_id):
    """Get stops for a specific route"""
    url = "https://api-v3.mbta.com/stops"
    params = {
        'filter[route]': route_id,
        'page[limit]': 1000
    }
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.get(url, params=params)
            
            if response.status_code == 429:  # Rate limited
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2  # Progressive backoff
                    print(f"Rate limited, waiting {wait_time} seconds...")
                    time.sleep(wait_time)
                    continue
                else:
                    print(f"Rate limited after {max_retries} attempts for route {route_id}")
                    return []
            
            response.raise_for_status()
            
            data = response.json()
            stops = data.get('data', [])
            
            # Convert to our format
            formatted_stops = []
            for stop in stops:
                attributes = stop.get('attributes', {})
                if 'latitude' in attributes and 'longitude' in attributes:
                    formatted_stops.append({
                        'name': attributes.get('name', 'Unknown'),
                        'coords': [float(attributes['latitude']), float(attributes['longitude'])],
                        'type': 'Bus',
                        'stopId': stop['id']
                    })
            
            return formatted_stops
            
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"Error fetching stops for route {route_id} (attempt {attempt + 1}): {e}")
                time.sleep(2)
                continue
            else:
                print(f"Error fetching stops for route {route_id} after {max_retries} attempts: {e}")
                return []
    
    return []

def generate_bus_data():
    """Generate complete bus data using MBTA API"""
    print("Starting bus data generation using MBTA API...")
    
    # Get all bus routes
    routes = get_bus_routes()
    if not routes:
        print("No routes found")
        return
    
    # Generate bus data
    mbta_bus_data = {}
    bus_route_shapes = {}
    
    print("Processing routes...")
    for route in tqdm(routes, desc="Processing routes"):
        route_id = route['id']
        route_name = route.get('attributes', {}).get('long_name', 'Unknown')
        
        print(f"Processing route {route_id}: {route_name}")
        
        # Get stops for this route
        stops = get_route_stops(route_id)
        print(f"  Found {len(stops)} stops")
        
        # Get shapes for this route
        shapes = get_route_shapes(route_id)
        print(f"  Found {len(shapes)} shapes")
        
        # Store the data
        if stops:
            mbta_bus_data[route_id] = stops
        
        if shapes:
            bus_route_shapes[route_id] = shapes
        
        # Rate limiting - be more respectful of the API
        time.sleep(0.5)  # 500ms between requests
    
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

if __name__ == "__main__":
    generate_bus_data()
