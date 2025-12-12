// Socket.io event handlers

import * as state from './state.js';
import { render, diffAnimationLoop } from './render.js';
import { updateDashboard, updateVerticalEVBar, resetDashboard } from './dashboard.js';
import { updateStateCountyCounts, updateTooltipContent } from './tooltip.js';

// DOM elements
const iterationEl = document.getElementById('iteration');
const stateTooltip = document.getElementById('stateTooltip');
const iterBox = document.getElementById('iterBox');
const startBtn = document.getElementById('startBtn');
const stopBtn = document.getElementById('stopBtn');
const thinkingSpinner = document.getElementById('thinkingSpinner');

// Show thinking spinner (single spin then fade)
function showThinkingSpinner() {
    if (!thinkingSpinner || !state.diffMode) return;

    // Remove and re-add class to restart animation
    thinkingSpinner.classList.remove('spin');
    // Force reflow to restart animation
    void thinkingSpinner.offsetWidth;
    thinkingSpinner.classList.add('spin');
}

// Setup socket event listeners
export function setupSocketHandlers() {
    // Handle thinking spinner (heap used for smart move selection)
    state.socket.on('thinking', () => {
        showThinkingSpinner();
    });

    state.socket.on('color_update', (data) => {
        // Track changed counties with timestamps for fade animation
        if (data.countyToState && state.diffMode) {
            const now = performance.now();
            for (const [geoid, newState] of Object.entries(data.countyToState)) {
                const oldState = state.previousCountyToState[geoid];
                if (oldState !== undefined && oldState !== newState) {
                    state.countyChangeTime[geoid] = now; // Reset/set timestamp
                }
            }
            // Start animation loop if not already running
            if (!state.diffAnimationFrame) {
                diffAnimationLoop();
            }
        }
        if (data.countyToState) {
            state.setPreviousCountyToState({ ...data.countyToState });
        }

        state.setCountyColors(data.colors);
        if (data.stateLeans) state.setStateLeans(data.stateLeans);
        if (data.countyToState) {
            state.setCountyToState(data.countyToState);
            updateStateCountyCounts();
        }
        if (data.election) {
            state.setElection(data.election);
        }
        if (data.score !== undefined) {
            state.setCurrentScore(data.score);
            // Track score with iteration for chart
            if (data.generation !== undefined) {
                state.pushScoreHistory({ iter: data.generation, score: state.currentScore });
            }
        }

        render();

        // Update brainrot dashboard
        updateDashboard();

        // Refresh tooltip if currently hovering over a state
        if (state.hoveredState && stateTooltip.style.display !== 'none') {
            updateTooltipContent(state.hoveredState);
        }

        if (iterationEl) iterationEl.textContent = data.generation.toLocaleString();
    });

    state.socket.on('algorithm_started', (data) => {
        state.setIsAlgorithmRunning(true);
    });

    state.socket.on('algorithm_complete', () => {
        startBtn.disabled = false;
        stopBtn.disabled = true;
        if (iterBox) iterBox.classList.remove('running');
        state.setIsAlgorithmRunning(false);
    });

    state.socket.on('error', (data) => {
        console.error('Error:', data.message);
        startBtn.disabled = false;
        stopBtn.disabled = true;
        if (iterBox) iterBox.classList.remove('running');
        state.setIsAlgorithmRunning(false);
    });

    state.socket.on('reset_complete', (data) => {
        state.setCountyColors(data.colors);
        if (data.countyToState) {
            state.setCountyToState(data.countyToState);
            state.setPreviousCountyToState({ ...state.countyToState });
            state.setCountyChangeTime({}); // Clear all fade animations
            if (state.diffAnimationFrame) {
                cancelAnimationFrame(state.diffAnimationFrame);
                state.setDiffAnimationFrame(null);
            }
            updateStateCountyCounts();
        }
        if (data.stateLeans) state.setStateLeans(data.stateLeans);
        if (data.election) state.setElection(data.election);

        // Reset dashboard
        resetDashboard();

        render();
        if (iterationEl) iterationEl.textContent = '0';
        updateVerticalEVBar();
        updateDashboard();
    });
}
