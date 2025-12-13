// Tooltip handling functions

import * as state from './state.js';
import { formatLean, getLeanClass } from './utils.js';

// DOM elements
const stateTooltip = document.getElementById('stateTooltip');
const tooltipStateName = document.getElementById('tooltipStateName');
const tooltipCountyCount = document.getElementById('tooltipCountyCount');
const tooltipPopulation = document.getElementById('tooltipPopulation');
const tooltipEV = document.getElementById('tooltipEV');
const tooltipLean = document.getElementById('tooltipLean');

// Build state names and county counts from geojson
export function buildStateData() {
    const stateNames = {};

    // Extract from geojson properties
    for (const feature of state.geojson.features) {
        const props = feature.properties;
        const stateAbbrev = props.STUSPS;
        const stateName = props.STATE_NAME;

        if (stateAbbrev && stateName) {
            stateNames[stateAbbrev] = stateName;
        }
    }

    state.setStateNames(stateNames);

    // Count counties per state from countyToState
    updateStateCountyCounts();
}

// Update county counts and populations when state assignments change
// Note: EVs are now provided by the server (authoritative source)
export function updateStateCountyCounts() {
    const stateCountyCounts = {};
    const statePopulations = {};

    for (const [geoid, stateAbbrev] of Object.entries(state.countyToState)) {
        stateCountyCounts[stateAbbrev] = (stateCountyCounts[stateAbbrev] || 0) + 1;
        statePopulations[stateAbbrev] = (statePopulations[stateAbbrev] || 0) + (state.population[geoid] || 0);
    }

    state.setStateCountyCounts(stateCountyCounts);
    state.setStatePopulations(statePopulations);
}

// Find which county (and thus state) is under the mouse
export function findStateAtPoint(x, y) {
    for (const [geoid, path] of Object.entries(state.countyPaths)) {
        if (state.ctx.isPointInPath(path, x, y)) {
            return state.countyToState[geoid];
        }
    }
    return null;
}

// Update tooltip content without repositioning (for live updates during animation)
export function updateTooltipContent(stateAbbrev) {
    if (!stateAbbrev) return;

    const stateName = state.stateNames[stateAbbrev] || stateAbbrev;
    const countyCount = state.stateCountyCounts[stateAbbrev] || 0;
    const pop = state.statePopulations[stateAbbrev] || 0;
    const ev = state.stateEVs[stateAbbrev] || 0;
    const lean = state.stateLeans[stateAbbrev];

    tooltipStateName.textContent = stateName;
    tooltipCountyCount.textContent = countyCount;
    tooltipPopulation.textContent = pop.toLocaleString();
    tooltipEV.textContent = ev;
    tooltipLean.textContent = formatLean(lean);
    tooltipLean.className = getLeanClass(lean);
}

// Show tooltip for a state
export function showTooltip(stateAbbrev, mouseX, mouseY) {
    if (!stateAbbrev) {
        stateTooltip.style.display = 'none';
        return;
    }

    updateTooltipContent(stateAbbrev);

    // Position tooltip near mouse, offset to avoid cursor
    const offsetX = 15;
    const offsetY = 15;
    let left = mouseX + offsetX;
    let top = mouseY + offsetY;

    // Show briefly to measure
    stateTooltip.style.display = 'block';
    const tooltipWidth = stateTooltip.offsetWidth;
    const tooltipHeight = stateTooltip.offsetHeight;

    // Keep tooltip on screen
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;

    if (left + tooltipWidth > viewportWidth - 10) {
        left = mouseX - tooltipWidth - offsetX;
    }
    if (top + tooltipHeight > viewportHeight - 10) {
        top = mouseY - tooltipHeight - offsetY;
    }

    stateTooltip.style.left = left + 'px';
    stateTooltip.style.top = top + 'px';
}

// Canvas mouse event handlers
export function setupTooltipHandlers() {
    state.canvas.addEventListener('mousemove', (e) => {
        const rect = state.canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;

        const stateAbbrev = findStateAtPoint(x, y);
        state.setHoveredState(stateAbbrev);
        showTooltip(stateAbbrev, e.clientX, e.clientY);
    });

    state.canvas.addEventListener('mouseleave', () => {
        state.setHoveredState(null);
        stateTooltip.style.display = 'none';
    });
}
