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
