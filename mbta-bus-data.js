// MBTA Bus Routes Data
const mbtaBusData = {
    // Route 71 - Watertown Square to Harvard Station
    '71': [
        {name: 'Watertown Square', coords: [42.3650, -71.1820], type: 'Bus'},
        {name: 'Arsenal Street', coords: [42.3650, -71.1680], type: 'Bus'},
        {name: 'Brighton Center', coords: [42.3650, -71.1610], type: 'Bus'},
        {name: 'Packards Corner', coords: [42.3650, -71.1540], type: 'Bus'},
        {name: 'Babcock Street', coords: [42.3490, -71.1147], type: 'Bus'},
        {name: 'Harvard Station', coords: [42.3734, -71.1189], type: 'Bus'}
    ],
    
    // Route 73 - Waverley Square to Harvard Station
    '73': [
        {name: 'Waverley Square', coords: [42.3950, -71.1300], type: 'Bus'},
        {name: 'Belmont Center', coords: [42.3950, -71.1250], type: 'Bus'},
        {name: 'Fresh Pond', coords: [42.3950, -71.1200], type: 'Bus'},
        {name: 'Porter Square', coords: [42.3884, -71.1191], type: 'Bus'},
        {name: 'Harvard Station', coords: [42.3734, -71.1189], type: 'Bus'}
    ]
};

// Bus route shapes (more realistic paths following roads)
const busRouteShapes = {
    '71': [
        {coords: [
            [42.3650, -71.1820], // Watertown Square
            [42.3650, -71.1750], // Arsenal Street area
            [42.3650, -71.1680], // Arsenal Street
            [42.3650, -71.1610], // Brighton Center
            [42.3650, -71.1540], // Packards Corner
            [42.3490, -71.1147], // Babcock Street
            [42.3734, -71.1189]  // Harvard Station
        ]}
    ],
    '73': [
        {coords: [
            [42.3950, -71.1300], // Waverley Square
            [42.3950, -71.1250], // Belmont Center
            [42.3950, -71.1200], // Fresh Pond
            [42.3884, -71.1191], // Porter Square
            [42.3734, -71.1189]  // Harvard Station
        ]}
    ]
};
