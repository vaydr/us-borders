// Utility functions

// Convert partisan lean (-1 to 1) to color (blue to red)
export function leanToColor(lean) {
    // Clamp lean to -1 to 1 range
    lean = Math.max(-1, Math.min(1, lean));

    // Use a more perceptually uniform scale
    // At 0: purple/gray, negative: blue, positive: red
    if (lean < 0) {
        // Democrat (blue) - lean is negative
        // -1 = pure blue, 0 = light purple
        const t = Math.abs(lean); // 0 to 1
        const r = Math.round(200 - t * 180);  // 200 -> 20
        const g = Math.round(200 - t * 120);  // 200 -> 80
        const b = Math.round(210 + t * 35);   // 220 -> 255
        return `rgb(${r},${g},${b})`;
    } else {
        // Republican (red) - lean is positive
        // +1 = pure red, 0 = light purple
        const t = lean; // 0 to 1
        const r = Math.round(210 + t * 35);   // 220 -> 255
        const g = Math.round(200 - t * 180);  // 200 -> 20
        const b = Math.round(200 - t * 180);  // 200 -> 20
        return `rgb(${r},${g},${b})`;
    }
}

// Format partisan lean for display
export function formatLean(lean) {
    if (lean === undefined || lean === null) return 'N/A';
    const pct = Math.abs(lean * 100).toFixed(2);
    if (Math.abs(lean) < 0.000005) return 'EVEN';
    return lean > 0 ? 'R+' + pct : 'D+' + pct;
}

// Get CSS class for lean
export function getLeanClass(lean) {
    if (lean === undefined || lean === null || Math.abs(lean) < 0.000005) return 'lean-even';
    return lean > 0 ? 'lean-rep' : 'lean-dem';
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
