#!/usr/bin/env python3
"""
Retry script for routes that are missing stops or shapes.
"""

import requests
import json
from pathlib import Path
import time

def get_route_stops(route_id):
    """Get stops for a specific route"""
    url = "https://api-v3.mbta.com/stops"
    params = {
        'filter[route]': route_id,
        'page[limit]': 1000
    }
    
    max_retries = 5
    for attempt in range(max_retries):
        try:
            response = requests.get(url, params=params)
            
            if response.status_code == 429:  # Rate limited
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 3  # Progressive backoff
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
                time.sleep(3)
                continue
            else:
                print(f"Error fetching stops for route {route_id} after {max_retries} attempts: {e}")
                return []
    
    return []

def get_route_shapes(route_id):
    """Get shapes for a specific route"""
    url = "https://api-v3.mbta.com/shapes"
    params = {
        'filter[route]': route_id,
        'page[limit]': 100
    }
    
    max_retries = 5
    for attempt in range(max_retries):
        try:
            response = requests.get(url, params=params)
            
            if response.status_code == 429:  # Rate limited
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 3  # Progressive backoff
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
                    decoded_shapes.append({
                        'shape_id': shape['id'],
                        'polyline': encoded_polyline
                    })
            
            return decoded_shapes
            
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"Error fetching shapes for route {route_id} (attempt {attempt + 1}): {e}")
                time.sleep(3)
                continue
            else:
                print(f"Error fetching shapes for route {route_id} after {max_retries} attempts: {e}")
                return []
    
    return []

def retry_failed_routes():
    """Retry routes that are missing data"""
    
    # Load existing data
    js_file = Path("mbta-bus-data.js")
    if not js_file.exists():
        print("mbta-bus-data.js not found. Run the main script first.")
        return
    
    # Read the existing data to identify missing routes
    with open(js_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Extract the data (more robust approach)
    mbta_bus_data_start = content.find("const mbtaBusData = ")
    if mbta_bus_data_start == -1:
        print("Could not find mbtaBusData in file")
        return
    
    mbta_bus_data_start += len("const mbtaBusData = ")
    mbta_bus_data_end = content.find(";\n\nconst busRouteShapes", mbta_bus_data_start)
    if mbta_bus_data_end == -1:
        print("Could not find end of mbtaBusData")
        return
    
    bus_route_shapes_start = content.find("const busRouteShapes = ", mbta_bus_data_end)
    if bus_route_shapes_start == -1:
        print("Could not find busRouteShapes in file")
        return
    
    bus_route_shapes_start += len("const busRouteShapes = ")
    bus_route_shapes_end = content.find(";\n\n", bus_route_shapes_start)
    if bus_route_shapes_end == -1:
        print("Could not find end of busRouteShapes")
        return
    
    mbta_bus_data_str = content[mbta_bus_data_start:mbta_bus_data_end]
    bus_route_shapes_str = content[bus_route_shapes_start:bus_route_shapes_end]
    
    print(f"Extracted mbtaBusData: {len(mbta_bus_data_str)} characters")
    print(f"Extracted busRouteShapes: {len(bus_route_shapes_str)} characters")
    
    try:
        mbta_bus_data = json.loads(mbta_bus_data_str)
        bus_route_shapes = json.loads(bus_route_shapes_str)
    except json.JSONDecodeError as e:
        print(f"Error parsing existing data: {e}")
        print(f"mbtaBusData preview: {mbta_bus_data_str[:100]}...")
        print(f"busRouteShapes preview: {bus_route_shapes_str[:100]}...")
        return
    
    print(f"Loaded existing data: {len(mbta_bus_data)} routes with stops, {len(bus_route_shapes)} routes with shapes")
    
    # Identify routes missing data
    routes_with_both = set(mbta_bus_data.keys()) & set(bus_route_shapes.keys())
    routes_with_stops_only = set(mbta_bus_data.keys()) - set(bus_route_shapes.keys())
    routes_with_shapes_only = set(bus_route_shapes.keys()) - set(mbta_bus_data.keys())
    
    print(f"Routes with both: {len(routes_with_both)}")
    print(f"Routes with stops only: {len(routes_with_stops_only)}")
    print(f"Routes with shapes only: {len(routes_with_shapes_only)}")
    
    # Routes to retry
    routes_to_retry = list(routes_with_stops_only) + list(routes_with_shapes_only)
    
    if not routes_to_retry:
        print("No routes to retry!")
        return
    
    print(f"\nRetrying {len(routes_to_retry)} routes with missing data...")
    
    # Retry each route
    for route_id in routes_to_retry:
        print(f"\nRetrying route {route_id}...")
        
        # Get stops if missing
        if route_id not in mbta_bus_data:
            print(f"  Fetching stops...")
            stops = get_route_stops(route_id)
            if stops:
                mbta_bus_data[route_id] = stops
                print(f"  Got {len(stops)} stops")
            else:
                print(f"  Failed to get stops")
        
        # Get shapes if missing
        if route_id not in bus_route_shapes:
            print(f"  Fetching shapes...")
            shapes = get_route_shapes(route_id)
            if shapes:
                bus_route_shapes[route_id] = shapes
                print(f"  Got {len(shapes)} shapes")
            else:
                print(f"  Failed to get shapes")
        
        # Rate limiting
        time.sleep(1.0)  # 1 second between routes
    
    # Save updated data
    print(f"\nSaving updated data...")
    
    with open(js_file, 'w', encoding='utf-8') as f:
        f.write("const mbtaBusData = ")
        json.dump(mbta_bus_data, f, indent=2, ensure_ascii=False)
        f.write(";\n\n")
        
        f.write("const busRouteShapes = ")
        json.dump(bus_route_shapes, f, indent=2, ensure_ascii=False)
        f.write(";\n\n")
    
    print(f"Updated data saved to {js_file}")
    
    # Final summary
    routes_with_both = set(mbta_bus_data.keys()) & set(bus_route_shapes.keys())
    routes_with_stops_only = set(mbta_bus_data.keys()) - set(bus_route_shapes.keys())
    routes_with_shapes_only = set(bus_route_shapes.keys()) - set(mbta_bus_data.keys())
    
    print(f"\nFinal summary:")
    print(f"Total routes: {len(mbta_bus_data)}")
    print(f"Routes with both stops and shapes: {len(routes_with_both)}")
    print(f"Routes with stops only: {len(routes_with_stops_only)}")
    print(f"Routes with shapes only: {len(routes_with_shapes_only)}")

if __name__ == "__main__":
    retry_failed_routes()
