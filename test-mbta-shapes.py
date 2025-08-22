#!/usr/bin/env python3
"""
Test script to check MBTA's shapes API endpoint
"""

import requests
import json

def test_mbta_shapes_api():
    """Test the MBTA shapes API endpoint"""
    
    # Test with a few known bus route IDs
    test_routes = ['1', '4', '71', '741']  # Some common bus routes
    
    for route_id in test_routes:
        print(f"\nTesting route {route_id}:")
        
        # Make API request
        url = "https://api-v3.mbta.com/shapes"
        params = {
            'filter[route]': route_id,
            'page[limit]': 10
        }
        
        try:
            response = requests.get(url, params=params)
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"Response keys: {list(data.keys())}")
                
                if 'data' in data:
                    shapes = data['data']
                    print(f"Found {len(shapes)} shapes")
                    
                    if shapes:
                        # Show first shape details
                        first_shape = shapes[0]
                        print(f"First shape ID: {first_shape.get('id')}")
                        print(f"First shape attributes: {list(first_shape.get('attributes', {}).keys())}")
                        
                        if 'polyline' in first_shape.get('attributes', {}):
                            polyline = first_shape['attributes']['polyline']
                            print(f"Polyline length: {len(polyline)} characters")
                            print(f"Polyline preview: {polyline[:100]}...")
                        else:
                            print("No polyline found in attributes")
                else:
                    print("No 'data' key in response")
                    print(f"Response: {json.dumps(data, indent=2)[:500]}...")
            else:
                print(f"Error response: {response.text[:200]}...")
                
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    test_mbta_shapes_api()
