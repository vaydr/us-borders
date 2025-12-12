// Main entry point - initialization and button handlers

import * as state from './state.js';
import { computeBounds, precomputePaths } from './geo.js';
import { render } from './render.js';
import { updateDashboard, updateVerticalEVBar } from './dashboard.js';
import { buildStateData, setupTooltipHandlers } from './tooltip.js';
import { setupAllControls, StatCarousel } from './controls.js';
import { setupSocketHandlers } from './socket.js';

// DOM elements
const loadingState = document.getElementById('loadingState');
const floatingControls = document.getElementById('floatingControls');
const floatingEV = document.getElementById('floatingEV');
const dashboard = document.getElementById('dashboard');
const iterBox = document.getElementById('iterBox');
const startBtn = document.getElementById('startBtn');
const stopBtn = document.getElementById('stopBtn');
const resetBtn = document.getElementById('resetBtn');
const iterationsInput = document.getElementById('iterations');
const renderEveryInput = document.getElementById('renderEvery');

// Control getters (will be set after setup)
let controlGetters = {};

// Track if we have a paused run to resume
let isPaused = false;

// Initialize the application
async function init() {
    try {
        // Load GeoJSON and initial colors in parallel
        const [geoRes, initRes] = await Promise.all([
            fetch('/api/geojson'),
            fetch('/api/init')
        ]);

        state.setGeojson(await geoRes.json());
        const initData = await initRes.json();
        state.setPalette(initData.palette);
        state.setCountyColors(initData.colors);
        state.setNeighbors(initData.neighbors);
        state.setPartisanLean(initData.partisanLean || {});
        state.setPopulation(initData.population || {});
        state.setStateLeans(initData.stateLeans || {});
        state.setCountyToState(initData.countyToState || {});
        state.setPreviousCountyToState({ ...state.countyToState });
        state.setStateEVs(initData.stateEVs || {});
        state.setStatePopulations(initData.statePopulations || {});
        state.setElection(initData.election || { winner: '-', r_ev: 0, d_ev: 0 });

        console.log(`Loaded ${state.geojson.features.length} counties, ${state.palette.length} colors, ${Object.keys(state.neighbors).length} neighbor entries, ${Object.keys(state.partisanLean).length} partisan lean values, ${Object.keys(state.stateLeans).length} state leans`);

        // Setup canvas
        const width = 1100;
        const height = 500;
        state.canvas.width = width;
        state.canvas.height = height;

        // Compute transform
        state.setBounds(computeBounds(state.geojson));
        const geoWidth = state.bounds.maxX - state.bounds.minX;
        const geoHeight = state.bounds.maxY - state.bounds.minY;
        const scaleX = (width - 40) / geoWidth;
        const scaleY = (height - 40) / geoHeight;
        state.setTransform({
            scale: Math.min(scaleX, scaleY),
            offsetX: 20,
            offsetY: 20
        });

        // Pre-compute paths
        precomputePaths();

        // Build state data for tooltips
        buildStateData();

        // Setup tooltip event handlers
        setupTooltipHandlers();

        // Setup controls
        controlGetters = setupAllControls();

        // Setup socket handlers
        setupSocketHandlers();

        // Initial render
        render();

        // Show canvas and controls
        loadingState.style.display = 'none';
        state.canvas.style.display = 'block';
        if (floatingControls) floatingControls.style.display = 'flex';
        if (floatingEV) floatingEV.style.display = 'flex';
        if (dashboard) dashboard.style.display = 'grid';

        // Initialize carousels
        state.setEvCarousel(new StatCarousel('evCarousel', 4000));

        updateVerticalEVBar();
        updateDashboard();

    } catch (err) {
        console.error('Init error:', err);
        loadingState.innerHTML = '<p>Error loading map: ' + err.message + '</p>';
    }
}

// Setup button handlers
function setupButtonHandlers() {
    startBtn.onclick = () => {
        state.socket.emit('start_algorithm', {
            generations: parseInt(iterationsInput.value),
            render_every: parseInt(renderEveryInput.value),
            target: controlGetters.getTarget?.() || state.selectedTarget,
            mode: controlGetters.getMode?.() || state.selectedMode,
            resume: isPaused  // Resume if we were paused
        });
        startBtn.disabled = true;
        stopBtn.disabled = false;
        if (iterBox) iterBox.classList.add('running');
        if (iterBox) iterBox.classList.remove('paused');
        if (iterBox) iterBox.classList.remove('stopping');
        state.setIsAlgorithmRunning(true);
        isPaused = false;
    };

    stopBtn.onclick = () => {
        state.socket.emit('stop_algorithm');
        // Don't immediately update UI - wait for algorithm_paused event
        stopBtn.disabled = true;
    };

    resetBtn.onclick = () => {
        state.socket.emit('reset_algorithm');
        startBtn.disabled = false;
        stopBtn.disabled = true;
        if (iterBox) iterBox.classList.remove('running');
        if (iterBox) iterBox.classList.remove('paused');
        if (iterBox) iterBox.classList.remove('stopping');
        isPaused = false;
    };

    // Listen for paused event to update isPaused flag
    state.socket.on('algorithm_paused', () => {
        isPaused = true;
    });

    state.socket.on('algorithm_complete', () => {
        isPaused = false;
    });

    state.socket.on('reset_complete', () => {
        isPaused = false;
    });
}

// Initialize Lucide icons and start the app
lucide.createIcons();
setupButtonHandlers();
init();
