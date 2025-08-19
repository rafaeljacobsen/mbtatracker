# Extract MBTA Bus Routes from GTFS Data
# This script extracts all bus routes from routes.txt, stops.txt, and shapes.txt

Write-Host "Extracting MBTA Bus Routes..." -ForegroundColor Green

# Read routes.txt to get all bus routes (route_type = 3)
Write-Host "Reading routes.txt..." -ForegroundColor Yellow
$routes = Get-Content "mbta_gtfs\routes.txt" | Select-Object -Skip 1 | ForEach-Object {
    $fields = $_ -split ','
    if ($fields.Length -ge 5 -and $fields[4] -eq '3') {
        @{
            route_id = $fields[0]
            route_short_name = $fields[2]
            route_long_name = $fields[3]
            route_type = $fields[4]
        }
    }
}

Write-Host "Found $($routes.Count) bus routes" -ForegroundColor Green

# Read route_patterns.txt to get shape IDs for each route (optional)
Write-Host "Reading route_patterns.txt..." -ForegroundColor Yellow
$routePatterns = Get-Content "mbta_gtfs\route_patterns.txt" | Select-Object -Skip 1 | ForEach-Object {
    $fields = $_ -split ','
    if ($fields.Length -ge 8) {
        @{
            pattern_id = $fields[0]
            route_id = $fields[1]
            direction_id = $fields[2]
            shape_id = $fields[7]
        }
    }
}

# Group patterns by route_id
$routeShapes = $routePatterns | Group-Object route_id | ForEach-Object {
    @{
        route_id = $_.Name
        patterns = $_.Group
    }
}

Write-Host "Found $($routePatterns.Count) route patterns" -ForegroundColor Green

# Read stops.txt to get all stops
Write-Host "Reading stops.txt..." -ForegroundColor Yellow
$stops = Get-Content "mbta_gtfs\stops.txt" | Select-Object -Skip 1 | ForEach-Object {
    $fields = $_ -split ','
    if ($fields.Length -ge 5) {
        @{
            stop_id = $fields[0]
            stop_name = $fields[2]
            stop_lat = $fields[4]
            stop_lon = $fields[5]
        }
    }
}

Write-Host "Found $($stops.Count) stops" -ForegroundColor Green

# Read stop_times.txt to get which stops are used by each route
Write-Host "Reading stop_times.txt..." -ForegroundColor Yellow
$stopTimes = Get-Content "mbta_gtfs\stop_times.txt" | Select-Object -Skip 1 | ForEach-Object {
    $fields = $_ -split ','
    if ($fields.Length -ge 4) {
        @{
            trip_id = $fields[0]
            stop_id = $fields[3]
            stop_sequence = $fields[4]
        }
    }
}

# Read trips.txt to get route_id for each trip
Write-Host "Reading trips.txt..." -ForegroundColor Yellow
$trips = Get-Content "mbta_gtfs\trips.txt" | Select-Object -Skip 1 | ForEach-Object {
    $fields = $_ -split ','
    if ($fields.Length -ge 3) {
        @{
            trip_id = $fields[0]
            route_id = $fields[1]
            shape_id = $fields[6]
        }
    }
}

Write-Host "Found $($trips.Count) trips" -ForegroundColor Green

# Create a mapping of route_id to stops
$routeStops = @{}
foreach ($trip in $trips) {
    if ($trip.route_id -in $routes.route_id) {
        if (-not $routeStops.ContainsKey($trip.route_id)) {
            $routeStops[$trip.route_id] = @()
        }
        
        # Get stops for this trip
        $tripStops = $stopTimes | Where-Object { $_.trip_id -eq $trip.trip_id } | Sort-Object stop_sequence
        
        foreach ($stopTime in $tripStops) {
            $stop = $stops | Where-Object { $_.stop_id -eq $stopTime.stop_id }
            if ($stop) {
                $existingStop = $routeStops[$trip.route_id] | Where-Object { $_.stop_id -eq $stop.stop_id }
                if (-not $existingStop) {
                    $routeStops[$trip.route_id] += @{
                        stop_id = $stop.stop_id
                        name = $stop.stop_name
                        coords = [double]$stop.stop_lat, [double]$stop.stop_lon
                        type = 'Bus'
                    }
                }
            }
        }
    }
}

Write-Host "Found $($routeStops.Count) routes with stop data" -ForegroundColor Green

# Read shapes.txt to get route shapes
Write-Host "Reading shapes.txt..." -ForegroundColor Yellow
$shapes = Get-Content "mbta_gtfs\shapes.txt" | Select-Object -Skip 1 | ForEach-Object {
    $fields = $_ -split ','
    if ($fields.Length -ge 4) {
        @{
            shape_id = $fields[0]
            shape_pt_lat = [double]$fields[1]
            shape_pt_lon = [double]$fields[2]
            shape_pt_sequence = [int]$fields[3]
        }
    }
}

Write-Host "Found $($shapes.Count) shape points" -ForegroundColor Green

# Group shapes by shape_id
$routeShapesData = $shapes | Group-Object shape_id | ForEach-Object {
    $sortedPoints = $_.Group | Sort-Object shape_pt_sequence
    @{
        shape_id = $_.Name
        coords = $sortedPoints | ForEach-Object { @($_.shape_pt_lat, $_.shape_pt_lon) }
    }
}

# Create the final output
$output = @"
// MBTA Bus Routes Data - Extracted from GTFS
const mbtaBusData = {
"@

foreach ($route in $routes) {
    $routeId = $route.route_id
    $routeName = if ($route.route_short_name) { $route.route_short_name } else { $route.route_long_name }
    
    if ($routeStops.ContainsKey($routeId)) {
        $output += "`n    // Route $routeName - $($route.route_long_name)`n"
        $output += "    '$routeId': ["
        
        foreach ($stop in $routeStops[$routeId]) {
            $output += "`n        {name: '$($stop.name)', coords: [$($stop.coords[0]), $($stop.coords[1])], type: 'Bus'},"
        }
        
        $output += "`n    ],"
    }
}

$output += "`n};`n`n"

# Add route shapes
$output += "// Bus route shapes from GTFS data`n"
$output += "const busRouteShapes = {`n"

foreach ($route in $routes) {
    $routeId = $route.route_id
    
    # Find shapes for this route
    $routePattern = $routePatterns | Where-Object { $_.route_id -eq $routeId }
    if ($routePattern) {
        $output += "    '$routeId': ["
        
        foreach ($pattern in $routePattern) {
            $shapeId = $pattern.shape_id
            $shapeData = $routeShapesData | Where-Object { $_.shape_id -eq $shapeId }
            
            if ($shapeData) {
                $output += "`n        {coords: ["
                foreach ($coord in $shapeData.coords) {
                    $output += "`n            [$($coord[0]), $($coord[1])],"
                }
                $output += "`n        ]}"
            }
        }
        
        $output += "`n    ],"
    } else {
        # If no shape data, create a simple straight-line shape from stops
        if ($routeStops.ContainsKey($routeId)) {
            $output += "    '$routeId': ["
            $output += "`n        {coords: ["
            foreach ($stop in $routeStops[$routeId]) {
                $output += "`n            [$($stop.coords[0]), $($stop.coords[1])],"
            }
            $output += "`n        ]}"
            $output += "`n    ],"
        }
    }
}

$output += "`n};"

# Write to file
$output | Out-File -FilePath "mbta-bus-routes-extracted.js" -Encoding UTF8

Write-Host "`nExtraction complete!" -ForegroundColor Green
Write-Host "Output written to: mbta-bus-routes-extracted.js" -ForegroundColor Green
Write-Host "`nRoutes found:" -ForegroundColor Yellow
$routes | ForEach-Object { Write-Host "  - Route $($_.route_id): $($_.route_long_name)" -ForegroundColor Cyan }
