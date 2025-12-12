// Geographic and projection functions

import * as state from './state.js';
import { edgeKey } from './utils.js';

// Compute bounding box of GeoJSON
export function computeBounds(geojson) {
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    for (const feature of geojson.features) {
        const coords = feature.geometry.coordinates;
        processCoords(coords, (x, y) => {
            if (x < minX) minX = x;
            if (x > maxX) maxX = x;
            if (y < minY) minY = y;
            if (y > maxY) maxY = y;
        });
    }
    return { minX, minY, maxX, maxY };
}

export function processCoords(coords, fn) {
    if (typeof coords[0] === 'number') {
        fn(coords[0], coords[1]);
    } else {
        for (const c of coords) processCoords(c, fn);
    }
}

// Project longitude/latitude to canvas coordinates
export function project(lon, lat) {
    const x = (lon - state.bounds.minX) * state.transform.scale + state.transform.offsetX;
    const y = (state.bounds.maxY - lat) * state.transform.scale + state.transform.offsetY;
    return [x, y];
}

// Build Path2D for a geometry
export function buildPath(geometry) {
    const path = new Path2D();
    const type = geometry.type;
    const coords = geometry.coordinates;

    if (type === 'Polygon') {
        drawPolygon(path, coords);
    } else if (type === 'MultiPolygon') {
        for (const poly of coords) {
            drawPolygon(path, poly);
        }
    }
    return path;
}

function drawPolygon(path, rings) {
    for (const ring of rings) {
        let first = true;
        for (const [x, y] of ring) {
            const [px, py] = project(x, y);
            if (first) {
                path.moveTo(px, py);
                first = false;
            } else {
                path.lineTo(px, py);
            }
        }
        path.closePath();
    }
}

// Extract all edges from a geometry as line segments
export function extractEdges(geometry) {
    const edges = [];
    const type = geometry.type;
    const coords = geometry.coordinates;

    if (type === 'Polygon') {
        extractPolygonEdges(coords, edges);
    } else if (type === 'MultiPolygon') {
        for (const poly of coords) {
            extractPolygonEdges(poly, edges);
        }
    }
    return edges;
}

function extractPolygonEdges(rings, edges) {
    for (const ring of rings) {
        for (let i = 0; i < ring.length - 1; i++) {
            const [x1, y1] = project(ring[i][0], ring[i][1]);
            const [x2, y2] = project(ring[i + 1][0], ring[i + 1][1]);
            // Store edge with normalized key for comparison
            edges.push({ x1, y1, x2, y2 });
        }
    }
}

// Pre-compute all county paths and edges
export function precomputePaths() {
    const countyPaths = {};
    const countyEdges = {};

    for (const feature of state.geojson.features) {
        const geoid = feature.properties.GEOID;
        countyPaths[geoid] = buildPath(feature.geometry);
        countyEdges[geoid] = extractEdges(feature.geometry);
    }

    state.setCountyPaths(countyPaths);
    state.setCountyEdges(countyEdges);

    // Pre-compute shared edges between neighbors
    precomputeSharedEdges();
}

// Pre-compute shared edges between neighboring counties
function precomputeSharedEdges() {
    const sharedEdges = {};
    const processed = new Set();

    for (const geoid of Object.keys(state.countyEdges)) {
        const myNeighbors = state.neighbors[geoid] || [];
        const myEdgeSet = new Set(state.countyEdges[geoid].map(e => edgeKey(e.x1, e.y1, e.x2, e.y2)));

        for (const neighborId of myNeighbors) {
            const pairKey = geoid < neighborId ? `${geoid}-${neighborId}` : `${neighborId}-${geoid}`;
            if (processed.has(pairKey)) continue;
            processed.add(pairKey);

            if (!state.countyEdges[neighborId]) continue;

            // Find shared edges
            const path = new Path2D();
            let hasShared = false;

            for (const edge of state.countyEdges[neighborId]) {
                const key = edgeKey(edge.x1, edge.y1, edge.x2, edge.y2);
                if (myEdgeSet.has(key)) {
                    path.moveTo(edge.x1, edge.y1);
                    path.lineTo(edge.x2, edge.y2);
                    hasShared = true;
                }
            }

            if (hasShared) {
                sharedEdges[pairKey] = path;
            }
        }
    }

    state.setSharedEdges(sharedEdges);
    console.log(`Pre-computed ${Object.keys(sharedEdges).length} shared edges`);
}
