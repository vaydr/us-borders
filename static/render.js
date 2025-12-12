// Map rendering functions

import * as state from './state.js';
import { leanToColor } from './utils.js';

// Render the map
export function render() {
    const t0 = performance.now();

    state.ctx.fillStyle = '#252542';
    state.ctx.fillRect(0, 0, state.canvas.width, state.canvas.height);

    // Pass 1: Fill all counties
    const now = performance.now();

    // Calculate tipping point pulse alpha (smooth sine wave, 0 to 0.5)
    const tippingPulseAlpha = state.diffMode && state.currentTippingPoint
        ? 0.25 * (1 + Math.sin((now / state.TIPPING_PULSE_PERIOD) * Math.PI * 2))
        : 0;

    for (const feature of state.geojson.features) {
        const geoid = feature.properties.GEOID;
        const path = state.countyPaths[geoid];
        let color;

        if (state.colorMode === 'county-partisan') {
            // Each county colored by its own partisan lean
            const lean = state.partisanLean[geoid];
            color = lean !== undefined ? leanToColor(lean * 2) : '#cccccc';
        } else if (state.colorMode === 'state-partisan') {
            // Each county colored by its state's average partisan lean
            const stateAbbrev = state.countyToState[geoid];
            const lean = stateAbbrev ? state.stateLeans[stateAbbrev] : undefined;
            color = lean !== undefined ? leanToColor(lean * 2) : '#cccccc';
        } else {
            // Unique state colors
            const colorIdx = state.countyColors[geoid];
            color = state.palette[colorIdx] || '#cccccc';
        }

        state.ctx.fillStyle = color;
        state.ctx.fill(path);

        // Overlay yellow fade for diff mode (county changes)
        if (state.diffMode && state.countyChangeTime[geoid]) {
            const elapsed = now - state.countyChangeTime[geoid];
            if (elapsed < state.DIFF_FADE_DURATION) {
                const alpha = 1 - (elapsed / state.DIFF_FADE_DURATION);
                state.ctx.fillStyle = `rgba(255, 204, 0, ${alpha})`;
                state.ctx.fill(path);
            }
        }

        // Overlay white pulse for tipping point state counties
        if (tippingPulseAlpha > 0 && state.countyToState[geoid] === state.currentTippingPoint) {
            state.ctx.fillStyle = `rgba(100, 50, 100, ${tippingPulseAlpha})`;
            state.ctx.fill(path);
        }
    }

    // Pass 2: Draw thin county borders
    state.ctx.strokeStyle = '#00000022';
    state.ctx.lineWidth = 0.25;
    for (const feature of state.geojson.features) {
        const geoid = feature.properties.GEOID;
        state.ctx.stroke(state.countyPaths[geoid]);
    }

    // Pass 3: Draw thick state borders using pre-computed shared edges
    state.ctx.strokeStyle = '#000000';
    state.ctx.lineWidth = 2;
    state.ctx.lineCap = 'round';

    for (const [pairKey, path] of Object.entries(state.sharedEdges)) {
        const [geoid1, geoid2] = pairKey.split('-');
        const color1 = state.countyColors[geoid1];
        const color2 = state.countyColors[geoid2];

        // Only draw if counties belong to different states
        if (color1 !== color2) {
            state.ctx.stroke(path);
        }
    }
}

// Animation loop for diff fade effect and tipping point pulse
export function diffAnimationLoop() {
    const now = performance.now();
    let hasYellowFadeAnimations = false;

    // Check if any yellow fade animations are still active and clean up expired ones
    for (const geoid of Object.keys(state.countyChangeTime)) {
        const elapsed = now - state.countyChangeTime[geoid];
        if (elapsed < state.DIFF_FADE_DURATION) {
            hasYellowFadeAnimations = true;
        } else {
            delete state.countyChangeTime[geoid]; // Clean up expired
        }
    }

    // Keep animating if diff mode is on and there's a tipping point (for pulse)
    // or if there are active yellow fade animations
    const needsAnimation = state.diffMode && (hasYellowFadeAnimations || state.currentTippingPoint);

    if (needsAnimation) {
        render();
        state.setDiffAnimationFrame(requestAnimationFrame(diffAnimationLoop));
    } else {
        state.setDiffAnimationFrame(null);
    }
}

// Start the animation loop if needed (call when diff mode or tipping point changes)
export function ensureDiffAnimationRunning() {
    if (state.diffMode && state.currentTippingPoint && !state.diffAnimationFrame) {
        diffAnimationLoop();
    }
}
