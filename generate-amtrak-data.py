#!/usr/bin/env python3
"""
Amtrak Data Generator - Creates local JSON files for routes and stations
Similar to your MBTA data generation scripts
"""

import requests
import json
import time
from datetime import datetime
from typing import Dict, List, Any

# Amtrak V3 API endpoints
AMTRAK_V3_BASE_URL = "https://api-v3.amtraker.com"
USDOT_NTAD_URL = "https://services.arcgis.com/xOi1kZaI0eWDREZv/ArcGIS/rest/services/NTAD_Amtrak_Routes/FeatureServer/0/query"

class AmtrakDataGenerator:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"accept": "application/json"})
    
    def get_amtrak_stations(self) -> Dict[str, Any]:
        """Fetch all Amtrak stations from the API"""
        print("Fetching Amtrak stations...")
        
        try:
            response = self.session.get(f"{AMTRAK_V3_BASE_URL}/v3/stations", timeout=30)
            response.raise_for_status()
            stations_data = response.json()
            
            print(f"Found {len(stations_data)} stations")
            return stations_data
            
        except Exception as e:
            print(f"Error fetching stations: {e}")
            return {}
    
    def get_amtrak_routes_ntad(self) -> Dict[str, Any]:
        """Fetch Amtrak routes from USDOT NTAD ArcGIS service"""
        print("Fetching Amtrak routes from USDOT NTAD...")
        
        # Query parameters
        params = {
            "where": "1=1",
            "outFields": "*",
            "outSR": 4326,
            "f": "geojson",
            "returnGeometry": "true"
        }
        
        try:
            response = self.session.get(USDOT_NTAD_URL, params=params, timeout=60)
            response.raise_for_status()
            routes_data = response.json()
            
            if routes_data.get('features'):
                print(f"Found {len(routes_data['features'])} routes from NTAD")
                return routes_data
            else:
                print("No routes found in NTAD response")
                return {}
                
        except Exception as e:
            print(f"Error fetching NTAD routes: {e}")
            return {}
    
    def get_amtrak_routes_amtraker(self) -> Dict[str, Any]:
        """Fetch Amtrak routes from Amtraker API as fallback"""
        print("Fetching Amtrak routes from Amtraker API...")
        
        try:
            response = self.session.get(f"{AMTRAK_V3_BASE_URL}/v3/trains", timeout=30)
            response.raise_for_status()
            trains_data = response.json()
            
            # Extract unique routes from train data
            routes = {}
            for train_num, trains in trains_data.items():
                for train in trains:
                    if 'routeName' in train and train['routeName']:
                        route_name = train['routeName']
                        if route_name not in routes:
                            routes[route_name] = {
                                'name': route_name,
                                'trains': []
                            }
                        routes[route_name]['trains'].append(train)
            
            print(f"Found {len(routes)} routes from Amtraker API")
            return routes
            
        except Exception as e:
            print(f"Error fetching Amtraker routes: {e}")
            return {}
    
    def process_stations_data(self, stations_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Process and clean stations data"""
        processed_stations = []
        
        for station_id, station_info in stations_data.items():
            if station_info and isinstance(station_info, dict):
                processed_station = {
                    'stationId': station_id,
                    'name': station_info.get('name') or station_info.get('stationName') or 'Unknown',
                    'city': station_info.get('city'),
                    'state': station_info.get('state'),
                    'tz': station_info.get('tz'),
                    'lat': station_info.get('lat'),
                    'lon': station_info.get('lon')
                }
                
                # Only include stations with valid coordinates
                if processed_station['lat'] and processed_station['lon']:
                    processed_stations.append(processed_station)
        
        return processed_stations
    
    def process_routes_data(self, routes_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Process and clean routes data"""
        processed_routes = []
        
        if 'features' in routes_data:
            # NTAD GeoJSON format
            for feature in routes_data['features']:
                if feature.get('geometry') and feature['geometry'].get('coordinates'):
                    route_info = {
                        'name': (feature['properties'].get('ROUTE_NAME') or 
                                feature['properties'].get('NAME') or 
                                feature['properties'].get('ROUTE') or 
                                'Amtrak Route'),
                        'coordinates': feature['geometry']['coordinates'],
                        'geometryType': feature['geometry']['type'],
                        'properties': feature['properties']
                    }
                    processed_routes.append(route_info)
        else:
            # Amtraker API format
            for route_name, route_info in routes_data.items():
                processed_route = {
                    'name': route_name,
                    'trains': route_info.get('trains', []),
                    'totalTrains': len(route_info.get('trains', []))
                }
                processed_routes.append(processed_route)
        
        return processed_routes
    
    def save_data_to_file(self, data: Any, filename: str):
        """Save data to JSON file"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"✅ Data saved to {filename}")
        except Exception as e:
            print(f"❌ Error saving {filename}: {e}")
    
    def generate_all_data(self):
        """Generate all Amtrak data files"""
        timestamp = datetime.now().isoformat()
        
        # 1. Generate stations data
        print("\n" + "="*50)
        print("GENERATING AMTRAK STATIONS DATA")
        print("="*50)
        
        stations_data = self.get_amtrak_stations()
        if stations_data:
            processed_stations = self.process_stations_data(stations_data)
            
            stations_output = {
                'timestamp': timestamp,
                'source': 'Amtraker V3 API',
                'totalStations': len(processed_stations),
                'stations': processed_stations
            }
            
            self.save_data_to_file(stations_output, 'amtrak-stations-data.js')
            
            # Also save as pure JSON for reference
            self.save_data_to_file(stations_output, 'amtrak-stations-data.json')
        
        # 2. Generate routes data
        print("\n" + "="*50)
        print("GENERATING AMTRAK ROUTES DATA")
        print("="*50)
        
        # Try NTAD first, then fallback to Amtraker
        routes_data = self.get_amtrak_routes_ntad()
        if not routes_data:
            print("NTAD failed, trying Amtraker API...")
            routes_data = self.get_amtrak_routes_amtraker()
        
        if routes_data:
            processed_routes = self.process_routes_data(routes_data)
            
            routes_output = {
                'timestamp': timestamp,
                'source': 'USDOT NTAD + Amtraker V3 API',
                'totalRoutes': len(processed_routes),
                'routes': processed_routes
            }
            
            self.save_data_to_file(routes_output, 'amtrak-routes-data.js')
            
            # Also save as pure JSON for reference
            self.save_data_to_file(routes_output, 'amtrak-routes-data.json')
        
        print("\n" + "="*50)
        print("AMTRAK DATA GENERATION COMPLETE!")
        print("="*50)
        print("Files generated:")
        print("- amtrak-stations-data.js (for web use)")
        print("- amtrak-stations-data.json (for reference)")
        print("- amtrak-routes-data.js (for web use)")
        print("- amtrak-routes-data.json (for reference)")

def main():
    """Main function"""
    print("🚂 Amtrak Data Generator")
    print("This script will generate local JSON files for Amtrak routes and stations")
    print("Similar to your MBTA data generation scripts\n")
    
    generator = AmtrakDataGenerator()
    generator.generate_all_data()

if __name__ == "__main__":
    main()
