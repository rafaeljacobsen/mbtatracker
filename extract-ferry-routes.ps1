# Extract MBTA Ferry Routes from GTFS Data
# This script extracts all ferry routes from routes.txt, stops.txt, and shapes.txt

Write-Host "Extracting MBTA Ferry Routes..." -ForegroundColor Green

# Function to parse CSV line properly (same as working script)
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

# Step 1: Get ferry routes from routes.txt
Write-Host "Step 1: Loading ferry routes..." -ForegroundColor Yellow
$targetRoutes = @{}
Get-Content "mbta_gtfs/routes.txt" | Select-Object -Skip 1 | ForEach-Object {
    $fields = Parse-CsvLine $_
    if ($fields.Count -ge 6) {
        $routeId = $fields[0]
        $routeType = 0
        
        if ([int]::TryParse($fields[5], [ref]$routeType)) {
            if ($routeType -eq 4) {  # 4 = Ferry
                $targetRoutes[$routeId] = @{name = $fields[3]; type = $routeType}
            }
        }
    }
}

Write-Host "Found $($targetRoutes.Count) ferry routes"

# Step 2: Get trips and shapes for each route
Write-Host "Step 2: Loading trips and shapes..." -ForegroundColor Yellow
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
Write-Host "Step 3: Loading stops..." -ForegroundColor Yellow
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
Write-Host "Step 4: Processing stop times..." -ForegroundColor Yellow
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
Write-Host "Step 5: Loading shapes..." -ForegroundColor Yellow
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
Write-Host "Step 6: Building final data structure..." -ForegroundColor Yellow
$finalData = @{}

foreach ($routeId in $routeStops.Keys) {
    $routeName = $targetRoutes[$routeId].name
    $routeStopsList = @()
    
    foreach ($stopId in $routeStops[$routeId].Keys) {
        if ($stops.ContainsKey($stopId)) {
            $stop = $stops[$stopId]
            
            $routeStopsList += @{
                name = $stop.name
                coords = @($stop.lat, $stop.lon)
                type = 'Ferry'
                stopId = $stopId
            }
        }
    }
    
    if ($routeStopsList.Count -gt 0) {
        $finalData[$routeId] = $routeStopsList
    }
}

# Step 7: Generate JavaScript
Write-Host "Step 7: Generating JavaScript..." -ForegroundColor Yellow
$jsContent = "// MBTA Ferry Routes Data - Extracted from GTFS Static Data`n"
$jsContent += "const mbtaFerryData = {`n"

foreach ($routeId in $finalData.Keys | Sort-Object) {
    $routeName = $targetRoutes[$routeId].name
    $jsContent += "    '$routeId': [`n"
    $stops = $finalData[$routeId] | Sort-Object -Property name
    foreach ($stop in $stops) {
        # Use double quotes for stop names to avoid escaping issues
        $jsContent += "        {name: `"$($stop.name)`", coords: [$($stop.coords[0]), $($stop.coords[1])], type: '$($stop.type)', stopId: '$($stop.stopId)'},`n"
    }
    $jsContent += "    ],`n`n"
}

$jsContent += "};`n`n"

# Add shapes data
$jsContent += "// Ferry route shapes for each route`n"
$jsContent += "const ferryRouteShapes = {`n"

foreach ($routeId in $targetRoutes.Keys) {
    $jsContent += "    '$routeId': [`n"
    
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

$jsContent += "};`n"

# Save to file
$jsContent | Out-File -FilePath "mbta-ferry-data.js" -Encoding UTF8

Write-Host "Generated mbta-ferry-data.js with ferry route data" -ForegroundColor Green
Write-Host "Routes found: $($finalData.Keys.Count)" -ForegroundColor Green
foreach ($routeId in $finalData.Keys | Sort-Object) {
    $stopCount = $finalData[$routeId].Count
    Write-Host "  Route $routeId`: $stopCount stops" -ForegroundColor Cyan
}
