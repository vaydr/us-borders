// Utility functions

import * as state from './state.js';

// Parse hex color to RGB
function hexToRgb(hex) {
    // Remove # if present
    hex = hex.replace(/^#/, '');
    // Handle shorthand (e.g., #fff)
    if (hex.length === 3) {
        hex = hex[0] + hex[0] + hex[1] + hex[1] + hex[2] + hex[2];
    }
    const num = parseInt(hex, 16);
    return {
        r: (num >> 16) & 255,
        g: (num >> 8) & 255,
        b: num & 255
    };
}

// Cache for parsed colors to avoid repeated DOM queries
let colorCache = null;

// Get or refresh the color cache from CSS variables
function getColorCache() {
    if (!colorCache) {
        const root = document.documentElement;
        const style = getComputedStyle(root);

        const side1Hex = style.getPropertyValue('--side1-color').trim() || '#ef4444';
        const side2Hex = style.getPropertyValue('--side2-color').trim() || '#3b82f6';
        const tieHex = style.getPropertyValue('--tie-color').trim() || '#a855f7';

        colorCache = {
            side1: hexToRgb(side1Hex),
            side2: hexToRgb(side2Hex),
            tie: hexToRgb(tieHex)
        };
    }
    return colorCache;
}

// Call this when side config changes to refresh the cache
export function refreshColorCache() {
    colorCache = null;
}

// Convert partisan lean (-1 to 1) to color (side2 to side1)
// Interpolates between side colors through a neutral middle
export function leanToColor(lean) {
    // Clamp lean to -1 to 1 range
    lean = Math.max(-1, Math.min(1, lean));

    const colors = getColorCache();

    // Neutral color (light purple/gray) for the middle
    const neutral = { r: 200, g: 200, b: 210 };

    if (lean < 0) {
        // Side2 - lean is negative
        // -1 = pure side2 color, 0 = neutral
        const t = Math.abs(lean); // 0 to 1
        const r = Math.round(neutral.r + t * (colors.side2.r - neutral.r));
        const g = Math.round(neutral.g + t * (colors.side2.g - neutral.g));
        const b = Math.round(neutral.b + t * (colors.side2.b - neutral.b));
        return `rgb(${r},${g},${b})`;
    } else {
        // Side1 - lean is positive
        // +1 = pure side1 color, 0 = neutral
        const t = lean; // 0 to 1
        const r = Math.round(neutral.r + t * (colors.side1.r - neutral.r));
        const g = Math.round(neutral.g + t * (colors.side1.g - neutral.g));
        const b = Math.round(neutral.b + t * (colors.side1.b - neutral.b));
        return `rgb(${r},${g},${b})`;
    }
}

// Format partisan lean for display
export function formatLean(lean) {
    if (lean === undefined || lean === null) return 'N/A';
    const pct = Math.abs(lean * 100).toFixed(2);
    if (Math.abs(lean) < 0.000005) return 'EVEN';
    // Use single-letter abbreviations from sideConfig
    const s1Letter = state.sideConfig.side1_letter || 'R';
    const s2Letter = state.sideConfig.side2_letter || 'D';
    return lean > 0 ? `${s1Letter}+${pct}` : `${s2Letter}+${pct}`;
}

// Get CSS class for lean
export function getLeanClass(lean) {
    if (lean === undefined || lean === null || Math.abs(lean) < 0.000005) return 'lean-even';
    return lean > 0 ? 'lean-side1' : 'lean-side2';
}

// Create a normalized key for an edge (so A->B and B->A match)
export function edgeKey(x1, y1, x2, y2) {
    // Round to avoid floating point issues
    const r = (v) => Math.round(v * 100) / 100;
    const p1 = `${r(x1)},${r(y1)}`;
    const p2 = `${r(x2)},${r(y2)}`;
    return p1 < p2 ? `${p1}-${p2}` : `${p2}-${p1}`;
}

// Efficient line chart renderer - reuses path strings
export function renderLineChart(lineEl, areaEl, history, width = 200, height = 30, padding = 2) {
    if (!lineEl || !areaEl || history.length < 2) return;

    const values = history.map(d => d.value);
    const minVal = Math.min(...values);
    const maxVal = Math.max(...values);
    const range = maxVal - minVal || 1;
    const maxIter = history[history.length - 1].iter || history.length;

    // Build path string efficiently
    let linePath = '';
    for (let i = 0; i < history.length; i++) {
        const d = history[i];
        const x = (d.iter / maxIter) * width;
        const y = height - padding - ((d.value - minVal) / range) * (height - padding * 2);
        linePath += (i === 0 ? 'M' : 'L') + x.toFixed(1) + ',' + y.toFixed(1);
    }

    lineEl.setAttribute('d', linePath);

    // Area path
    const lastX = ((history[history.length - 1].iter / maxIter) * width).toFixed(1);
    const firstX = ((history[0].iter / maxIter) * width).toFixed(1);
    areaEl.setAttribute('d', linePath + `L${lastX},${height}L${firstX},${height}Z`);
}

// Segmented line chart - each segment colored by sign of value
// Positive = side1, Negative = side2, Zero = tie
// Area fills toward zero line (positive fills down, negative fills up)
export function renderSegmentedLineChart(lineGroup, areaGroup, history, width = 200, height = 30, padding = 2) {
    if (!lineGroup || !areaGroup || history.length < 2) return;

    const values = history.map(d => d.value);
    const minVal = Math.min(...values, 0); // Include 0 in range
    const maxVal = Math.max(...values, 0); // Include 0 in range
    const range = maxVal - minVal || 1;
    const maxIter = history[history.length - 1].iter || history.length;

    // Calculate zero line Y position
    const zeroY = height - padding - ((0 - minVal) / range) * (height - padding * 2);

    // Get colors from CSS
    const root = document.documentElement;
    const side1Color = getComputedStyle(root).getPropertyValue('--side1-color').trim() || '#ef4444';
    const side2Color = getComputedStyle(root).getPropertyValue('--side2-color').trim() || '#3b82f6';
    const tieColor = '#a855f7';

    // Determine winner from sign of value
    const getWinner = (val) => val > 0 ? 'side1' : val < 0 ? 'side2' : 'tie';
    const getColor = (winner) => winner === 'side1' ? side1Color : winner === 'side2' ? side2Color : tieColor;

    // Calculate all points
    const points = history.map((d, i) => ({
        x: (d.iter / maxIter) * width,
        y: height - padding - ((d.value - minVal) / range) * (height - padding * 2),
        winner: getWinner(d.value)
    }));

    // Build segments by winner
    const segments = [];
    let currentSegment = { winner: points[0].winner, points: [points[0]] };

    for (let i = 1; i < points.length; i++) {
        if (points[i].winner === currentSegment.winner) {
            currentSegment.points.push(points[i]);
        } else {
            // End current segment at this point (for continuity)
            currentSegment.points.push(points[i]);
            segments.push(currentSegment);
            // Start new segment from this point
            currentSegment = { winner: points[i].winner, points: [points[i]] };
        }
    }
    segments.push(currentSegment);

    // Clear existing content
    lineGroup.innerHTML = '';
    areaGroup.innerHTML = '';

    // Render each segment
    for (const seg of segments) {
        if (seg.points.length < 2) continue;

        const color = getColor(seg.winner);

        // Build line path
        let linePath = '';
        for (let i = 0; i < seg.points.length; i++) {
            const p = seg.points[i];
            linePath += (i === 0 ? 'M' : 'L') + p.x.toFixed(1) + ',' + p.y.toFixed(1);
        }

        // Create line path element
        const lineEl = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        lineEl.setAttribute('d', linePath);
        lineEl.setAttribute('fill', 'none');
        lineEl.setAttribute('stroke', color);
        lineEl.setAttribute('stroke-width', '1.5');
        lineEl.setAttribute('stroke-linecap', 'round');
        lineEl.setAttribute('stroke-linejoin', 'round');
        lineEl.style.filter = `drop-shadow(0 0 3px ${color}) drop-shadow(0 0 6px ${color})`;
        lineGroup.appendChild(lineEl);

        // Build area path - fill toward zero line
        const firstX = seg.points[0].x.toFixed(1);
        const lastX = seg.points[seg.points.length - 1].x.toFixed(1);
        const baseY = zeroY.toFixed(1);
        const areaPath = linePath + `L${lastX},${baseY}L${firstX},${baseY}Z`;

        // Create area path element
        const areaEl = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        areaEl.setAttribute('d', areaPath);
        areaEl.setAttribute('fill', color);
        areaEl.setAttribute('opacity', '0.3');
        areaGroup.appendChild(areaEl);
    }
}
