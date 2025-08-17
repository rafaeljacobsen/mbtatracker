# Simple MBTA stops extraction - stops only with accurate locations
Write-Host "=== SCRIPT STARTED ==="
Write-Host "Extracting MBTA stops with accurate locations..."

# Function to parse CSV line properly
function Parse-CsvLine {
    param([string]$line)
    $result = @()
    $current = ""
    $inQuotes = $false
    
    for ($i = 0; $i -lt $line.Length; $i++) {
        $char = $line[$i]
        
        if ($char -eq '"') {
            $inQuotes = -not $inQuotes
        } elseif ($char -eq ',' -and -not $inQuotes) {
            $result += $current.Trim('"')
            $current = ""
        } else {
            $current += $char
        }
    }
    
    $result += $current.Trim('"')
    return $result
}

# Step 1: Get target routes
Write-Host "Step 1: Loading routes..."
$targetRoutes = @{}
Get-Content "mbta_gtfs/routes.txt" | Select-Object -Skip 1 | ForEach-Object {
    $fields = Parse-CsvLine $_
    if ($fields.Count -ge 6) {
        $routeId = $fields[0]
        $routeType = 0
        
        if ([int]::TryParse($fields[5], [ref]$routeType)) {
            if ($routeType -eq 0 -or $routeType -eq 1 -or $routeType -eq 2) {
                $targetRoutes[$routeId] = @{name = $fields[3]; type = $routeType}
            }
        }
    }
}

Write-Host "Found $($targetRoutes.Count) subway/commuter rail routes"

# Step 2: Get actual trips and shapes for each route
Write-Host "Step 2: Loading trips and shapes..."
$routeTrips = @{}
$routeShapes = @{}

foreach ($routeId in $targetRoutes.Keys) {
    $routeTrips[$routeId] = @()
    $routeShapes[$routeId] = @()
}

# Get trips.txt to link shape_id to route_id
Get-Content "mbta_gtfs/trips.txt" | Select-Object -Skip 1 | ForEach-Object {
    $fields = Parse-CsvLine $_
    if ($fields.Count -ge 8) {
        $routeId = $fields[0]
        $tripId = $fields[2]
        $shapeId = $fields[7]
        
        if ($targetRoutes.ContainsKey($routeId) -and $shapeId -ne "") {
            $routeTrips[$routeId] += $tripId
            if (-not $routeShapes[$routeId].Contains($shapeId)) {
                $routeShapes[$routeId] += $shapeId
            }
        }
    }
}

Write-Host "Found trips and shapes for each route:"
foreach ($routeId in $targetRoutes.Keys) {
    Write-Host "  $routeId`: $($routeTrips[$routeId].Count) trips, $($routeShapes[$routeId].Count) shapes"
}

# Step 3: Get stop coordinates
Write-Host "Step 3: Loading stops..."
$stops = @{}
Get-Content "mbta_gtfs/stops.txt" | Select-Object -Skip 1 | ForEach-Object {
    $fields = Parse-CsvLine $_
    if ($fields.Count -ge 8) {
        $stopId = $fields[0]
        $stopName = $fields[2]
        $stopLat = 0
        $stopLon = 0
        
        if ([double]::TryParse($fields[6], [ref]$stopLat) -and [double]::TryParse($fields[7], [ref]$stopLon)) {
            $stops[$stopId] = @{name = $stopName; lat = $stopLat; lon = $stopLon}
        }
    }
}

Write-Host "Loaded $($stops.Count) stops with coordinates"

# Step 4: Get stops for each route
Write-Host "Step 4: Processing stop times..."
$routeStops = @{}

foreach ($routeId in $targetRoutes.Keys) {
    $routeStops[$routeId] = @{}
}

# Get stops for each route from stop_times.txt
Write-Host "Processing stop times to get route stops..."

# Process stop_times.txt efficiently
$totalLines = (Get-Content "mbta_gtfs/stop_times.txt" | Measure-Object -Line).Lines
$processedLines = 0

Write-Host "Processing $totalLines stop-time records..."

Get-Content "mbta_gtfs/stop_times.txt" | Select-Object -Skip 1 | ForEach-Object {
    $processedLines++
    if ($processedLines % 100000 -eq 0) {
        $percent = ($processedLines / $totalLines) * 100
        Write-Host "Processed $processedLines of $totalLines ($percent%)"
    }
    
    $fields = Parse-CsvLine $_
    if ($fields.Count -ge 4) {
        $tripId = $fields[0]
        $stopId = $fields[3]
        
        # Find which route this trip belongs to
        foreach ($routeId in $targetRoutes.Keys) {
            if ($routeTrips[$routeId] -contains $tripId) {
                $routeStops[$routeId][$stopId] = $true
                break
            }
        }
    }
}

# Step 5: Load shapes efficiently
Write-Host "Step 5: Loading shapes..."
$shapes = @{}
$shapeCount = 0

# Only load shapes we actually need
$neededShapes = @()
foreach ($routeId in $targetRoutes.Keys) {
    $neededShapes += $routeShapes[$routeId]
}
$neededShapes = $neededShapes | Sort-Object -Unique

Write-Host "Loading $($neededShapes.Count) unique shapes..."

if ($neededShapes.Count -gt 0) {
    # Use Select-String for much faster filtering instead of reading entire file
    foreach ($shapeId in $neededShapes) {
        $shapeLines = Select-String -Path "mbta_gtfs/shapes.txt" -Pattern "^$shapeId," | ForEach-Object { $_.Line }
        
        foreach ($line in $shapeLines) {
            $fields = Parse-CsvLine $line
            if ($fields.Count -ge 4) {
                $shapeLat = 0
                $shapeLon = 0
                $shapeSequence = 0
                
                if ([double]::TryParse($fields[1], [ref]$shapeLat) -and [double]::TryParse($fields[2], [ref]$shapeLon) -and [int]::TryParse($fields[3], [ref]$shapeSequence)) {
                    if (-not $shapes.ContainsKey($shapeId)) {
                        $shapes[$shapeId] = @()
                    }
                    $shapes[$shapeId] += @{
                        lat = $shapeLat
                        lon = $shapeLon
                        sequence = $shapeSequence
                        distance = if ($fields.Count -ge 5 -and $fields[4] -ne "") { [double]$fields[4] } else { 0 }
                    }
                    $shapeCount++
                }
            }
        }
    }
}

Write-Host "Loaded $shapeCount shape points for $($neededShapes.Count) shapes"

# Step 6: Build final data structure
Write-Host "Step 6: Building final data structure..."
$finalData = @{}
$stopToRoutes = @{}

foreach ($routeId in $routeStops.Keys) {
    $routeName = $targetRoutes[$routeId].name
    $routeType = $targetRoutes[$routeId].type
    $routeStopsList = @()
    
    foreach ($stopId in $routeStops[$routeId].Keys) {
        if ($stops.ContainsKey($stopId)) {
            $stop = $stops[$stopId]
            $stopType = if ($routeType -eq 2) { "Commuter Rail" } else { "Subway" }
            
            $routeStopsList += @{
                name = $stop.name
                coords = @($stop.lat, $stop.lon)
                type = $stopType
                stopId = $stopId
            }
            
            # Track which routes serve each stop
            if (-not $stopToRoutes.ContainsKey($stopId)) {
                $stopToRoutes[$stopId] = @()
            }
            $stopToRoutes[$stopId] += $routeName
        }
    }
    
    if ($routeStopsList.Count -gt 0) {
        $finalData[$routeName] = $routeStopsList
    }
}

# Step 7: Generate JavaScript
Write-Host "Step 7: Generating JavaScript..."
$jsContent = "// MBTA Stops Data - Extracted from GTFS Static Data with Shapes`n"
$jsContent += "const mbtaStopsData = {`n"

foreach ($routeName in $finalData.Keys | Sort-Object) {
    $jsContent += "    '$routeName': [`n"
    $stops = $finalData[$routeName] | Sort-Object -Property name
    foreach ($stop in $stops) {
        # Use double quotes for stop names to avoid escaping issues
        $jsContent += "        {name: `"$($stop.name)`", coords: [$($stop.coords[0]), $($stop.coords[1])], type: '$($stop.type)', stopId: '$($stop.stopId)'},`n"
    }
    $jsContent += "    ],`n`n"
}

$jsContent += "};`n`n"

# Add shapes data
$jsContent += "// Track shapes for each route`n"
$jsContent += "const routeShapes = {`n"

foreach ($routeId in $targetRoutes.Keys) {
    $routeName = $targetRoutes[$routeId].name
    $jsContent += "    '$routeName': [`n"
    
    foreach ($shapeId in $routeShapes[$routeId]) {
        if ($shapes.ContainsKey($shapeId)) {
            $jsContent += "        {`n"
            $jsContent += "            shapeId: '$shapeId',`n"
            $jsContent += "            coords: [`n"
            
            $shapePoints = $shapes[$shapeId] | Sort-Object -Property { [int]$_.sequence }
            
            foreach ($point in $shapePoints) {
                $jsContent += "                [$($point.lat), $($point.lon)],`n"
            }
            
            $jsContent += "            ],`n"
            $jsContent += "            distances: [`n"
            
            foreach ($point in $shapePoints) {
                $jsContent += "                $($point.distance),`n"
            }
            
            $jsContent += "            ]`n"
            $jsContent += "        },`n"
        }
    }
    
    $jsContent += "    ],`n`n"
}

$jsContent += "};`n`n"

# Add stop-to-routes mapping for multi-line stops
$jsContent += "// Stop to routes mapping for multi-line stops`n"
$jsContent += "const stopToRoutes = {`n"
foreach ($stopId in $stopToRoutes.Keys | Sort-Object) {
    $routes = $stopToRoutes[$stopId] | Sort-Object
    $jsContent += "    '$stopId': ['$($routes -join "', '")'],`n"
}
$jsContent += "};`n`n"

$jsContent += "// Export for use in other files`n"
$jsContent += "if (typeof module !== 'undefined' && module.exports) {`n"
$jsContent += "    module.exports = { mbtaStopsData, stopToRoutes, routeShapes };`n"
$jsContent += "}`n"

# Save to file
$jsContent | Out-File -FilePath "mbta-stops-accurate.js" -Encoding UTF8

Write-Host "Generated mbta-stops-accurate.js with accurate coordinates"
Write-Host "Routes found: $($finalData.Keys.Count)"
foreach ($routeName in $finalData.Keys | Sort-Object) {
    $stopCount = $finalData[$routeName].Count
    Write-Host "  $routeName`: $stopCount stops"
}

# Count multi-line stops
$multiLineStops = ($stopToRoutes.Values | Where-Object { $_.Count -gt 1 }).Count
Write-Host "Multi-line stops found: $multiLineStops"
