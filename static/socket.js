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
        const { colors, stateLeans, countyToState, election, score, generation } = data;

        // Update colors directly (no copy needed)
        state.setCountyColors(colors);

        // Handle county-to-state updates
        if (countyToState) {
            // Diff tracking only when diffMode is on
            if (state.diffMode) {
                const now = performance.now();
                const prev = state.previousCountyToState;
                for (const geoid in countyToState) {
                    if (prev[geoid] !== undefined && prev[geoid] !== countyToState[geoid]) {
                        state.countyChangeTime[geoid] = now;
                    }
                }
                if (!state.diffAnimationFrame) {
                    diffAnimationLoop();
                }
                // Need a copy for next comparison when diffMode is on
                state.setPreviousCountyToState(Object.assign({}, countyToState));
            } else {
                // No copy needed when diffMode is off
                state.setPreviousCountyToState(countyToState);
            }
            state.setCountyToState(countyToState);
            updateStateCountyCounts();
        }

        if (stateLeans) state.setStateLeans(stateLeans);
        if (election) state.setElection(election);
        if (score !== undefined) {
            state.setCurrentScore(score);
            if (generation !== undefined) {
                state.pushScoreHistory({ iter: generation, score });
            }
        }

        render();
        updateDashboard();

        // Tooltip refresh only if visible
        if (state.hoveredState && stateTooltip.style.display !== 'none') {
            updateTooltipContent(state.hoveredState);
        }

        if (iterationEl) iterationEl.textContent = generation.toLocaleString();
    });

    state.socket.on('algorithm_started', (data) => {
        state.setIsAlgorithmRunning(true);
    });

    state.socket.on('algorithm_complete', () => {
        startBtn.disabled = false;
        stopBtn.disabled = true;
        if (iterBox) iterBox.classList.remove('running');
        if (iterBox) iterBox.classList.remove('paused');
        state.setIsAlgorithmRunning(false);
    });

    state.socket.on('algorithm_paused', (data) => {
        startBtn.disabled = false;
        stopBtn.disabled = true;
        if (iterBox) iterBox.classList.remove('running');
        if (iterBox) iterBox.classList.add('paused');
        state.setIsAlgorithmRunning(false);
        console.log(`Paused at iteration ${data.generation}/${data.total}`);
    });

    state.socket.on('algorithm_stopping', () => {
        // Algorithm is stopping, wait for paused event
        if (iterBox) iterBox.classList.add('stopping');
    });

    state.socket.on('error', (data) => {
        console.error('Error:', data.message);
        startBtn.disabled = false;
        stopBtn.disabled = true;
        if (iterBox) iterBox.classList.remove('running');
        if (iterBox) iterBox.classList.remove('paused');
        state.setIsAlgorithmRunning(false);
    });

    state.socket.on('reset_complete', (data) => {
        const { colors, countyToState, stateLeans, election } = data;

        state.setCountyColors(colors);
        if (countyToState) {
            state.setCountyToState(countyToState);
            state.setPreviousCountyToState(countyToState);
            state.setCountyChangeTime({});
            if (state.diffAnimationFrame) {
                cancelAnimationFrame(state.diffAnimationFrame);
                state.setDiffAnimationFrame(null);
            }
            updateStateCountyCounts();
        }
        if (stateLeans) state.setStateLeans(stateLeans);
        if (election) state.setElection(election);

        // Clear UI state
        if (iterBox) {
            iterBox.classList.remove('paused', 'stopping');
        }

        resetDashboard();
        render();
        updateVerticalEVBar();
        updateDashboard();
        if (iterationEl) iterationEl.textContent = '0';
    });
}
