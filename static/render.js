// Map rendering functions

import * as state from './state.js';
import { leanToColor } from './utils.js';

// Render the map
export function render() {
    const ctx = state.ctx;
    ctx.fillStyle = '#252542';
    ctx.fillRect(0, 0, state.canvas.width, state.canvas.height);

    const now = state.diffMode ? performance.now() : 0;
    const tippingPoint = state.currentTippingPoint;

    // Pass 1: Fill all counties
    for (const feature of state.geojson.features) {
        const geoid = feature.properties.GEOID;
        const path = state.countyPaths[geoid];
        const countyState = state.countyToState[geoid];
        let color;

        if (state.colorMode === 'county-partisan') {
            const lean = state.partisanLean[geoid];
            color = lean !== undefined ? leanToColor(lean * 2) : '#cccccc';
        } else if (state.colorMode === 'state-partisan') {
            const lean = countyState ? state.stateLeans[countyState] : undefined;
            color = lean !== undefined ? leanToColor(lean * 2) : '#cccccc';
        } else if (state.colorMode === 'state-winner') {
            const lean = countyState ? state.stateLeans[countyState] : undefined;
            if (lean === undefined) {
                color = '#cccccc';
            } else if (lean > 0) {
                // Side1 color from CSS
                color = getComputedStyle(document.documentElement).getPropertyValue('--side1-color').trim() || '#ef4444';
            } else if (lean < 0) {
                // Side2 color from CSS
                color = getComputedStyle(document.documentElement).getPropertyValue('--side2-color').trim() || '#3b82f6';
            } else {
                // Tie color from CSS
                color = getComputedStyle(document.documentElement).getPropertyValue('--tie-color').trim() || '#a855f7';
            }
        } else {
            color = state.palette[state.countyColors[geoid]] || '#cccccc';
        }

        ctx.fillStyle = color;
        ctx.fill(path);

        // Tipping point overlay (always, 30% black)
        if (tippingPoint && countyState === tippingPoint) {
            ctx.fillStyle = 'rgba(0, 0, 0, 0.3)';
            ctx.fill(path);
        }

        // EV bar hover overlay
        if (state.hoveredEVState && countyState === state.hoveredEVState) {
            ctx.fillStyle = 'rgba(255, 155, 255, 0.5)';
            ctx.fill(path);
        }

        // White fade for diff mode county changes (accepted)
        if (now && state.countyChangeTime[geoid]) {
            const elapsed = now - state.countyChangeTime[geoid];
            if (elapsed < state.DIFF_FADE_DURATION) {
                ctx.fillStyle = `rgba(255, 255, 255, ${1 - elapsed / state.DIFF_FADE_DURATION})`;
                ctx.fill(path);
            }
        }

        // Black fade for diff mode county rejections
        if (now && state.rejectedCountyChangeTime[geoid]) {
            const elapsed = now - state.rejectedCountyChangeTime[geoid];
            if (elapsed < state.DIFF_FADE_DURATION) {
                ctx.fillStyle = `rgba(120, 120, 120, ${0.5*(1 - elapsed / state.DIFF_FADE_DURATION)})`;
                ctx.fill(path);
            }
        }
    }

    // Pass 2: Thin county borders
    ctx.strokeStyle = '#00000022';
    ctx.lineWidth = 0.25;
    for (const feature of state.geojson.features) {
        ctx.stroke(state.countyPaths[feature.properties.GEOID]);
    }

    // Pass 3: Thick state borders
    ctx.strokeStyle = '#000000';
    ctx.lineWidth = 2;
    ctx.lineCap = 'round';
    for (const pairKey in state.sharedEdges) {
        const [g1, g2] = pairKey.split('-');
        if (state.countyColors[g1] !== state.countyColors[g2]) {
            ctx.stroke(state.sharedEdges[pairKey]);
        }
    }
}

// Animation loop for diff fade effect
export function diffAnimationLoop() {
    const now = performance.now();
    let hasActiveAnimations = false;

    // Check accepted county animations (white flash)
    for (const geoid in state.countyChangeTime) {
        if (now - state.countyChangeTime[geoid] < state.DIFF_FADE_DURATION) {
            hasActiveAnimations = true;
        } else {
            delete state.countyChangeTime[geoid];
        }
    }

    // Check rejected county animations (black flash)
    for (const geoid in state.rejectedCountyChangeTime) {
        if (now - state.rejectedCountyChangeTime[geoid] < state.DIFF_FADE_DURATION) {
            hasActiveAnimations = true;
        } else {
            delete state.rejectedCountyChangeTime[geoid];
        }
    }

    if (state.diffMode && hasActiveAnimations) {
        render();
        state.setDiffAnimationFrame(requestAnimationFrame(diffAnimationLoop));
    } else {
        state.setDiffAnimationFrame(null);
    }
}
