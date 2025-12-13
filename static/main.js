// Main entry point - initialization and button handlers

import * as state from './state.js';
import { computeBounds, precomputePaths } from './geo.js';
import { render } from './render.js';
import { updateDashboard, updateVerticalEVBar, setupScoreRestoreClick } from './dashboard.js';
import { buildStateData, setupTooltipHandlers } from './tooltip.js';
import { setupAllControls, StatCarousel, CyclingBarPair } from './controls.js';
import { setupSocketHandlers } from './socket.js';
import { refreshColorCache } from './utils.js';

// Color palette mapping from color names to CSS color values
const COLOR_PALETTES = {
    red: {
        main: '#ef4444',
        dark: '#dc2626',
        light: '#f87171',
        lighter: '#fca5a5',
        textDark: '#7f1d1d'
    },
    blue: {
        main: '#3b82f6',
        dark: '#2563eb',
        light: '#60a5fa',
        lighter: '#93c5fd',
        textDark: '#1e3a8a'
    },
    green: {
        main: '#22c55e',
        dark: '#16a34a',
        light: '#4ade80',
        lighter: '#86efac',
        textDark: '#14532d'
    },
    orange: {
        main: '#f97316',
        dark: '#ea580c',
        light: '#fb923c',
        lighter: '#fdba74',
        textDark: '#7c2d12'
    },
    purple: {
        main: '#a855f7',
        dark: '#9333ea',
        light: '#c084fc',
        lighter: '#d8b4fe',
        textDark: '#581c87'
    },
    yellow: {
        main: '#eab308',
        dark: '#ca8a04',
        light: '#facc15',
        lighter: '#fde047',
        textDark: '#713f12'
    },
    teal: {
        main: '#14b8a6',
        dark: '#0d9488',
        light: '#2dd4bf',
        lighter: '#5eead4',
        textDark: '#134e4a'
    },
    pink: {
        main: '#ec4899',
        dark: '#db2777',
        light: '#f472b6',
        lighter: '#f9a8d4',
        textDark: '#831843'
    }
};

// Initialize side configuration from server data
function initSideConfig(sideConfig) {
    state.setSideConfig(sideConfig);

    // Get color palettes
    const side1Palette = COLOR_PALETTES[sideConfig.side1_color] || COLOR_PALETTES.red;
    const side2Palette = COLOR_PALETTES[sideConfig.side2_color] || COLOR_PALETTES.blue;

    // Set CSS custom properties
    const root = document.documentElement;
    root.style.setProperty('--side1-color', side1Palette.main);
    root.style.setProperty('--side1-dark', side1Palette.dark);
    root.style.setProperty('--side1-light', side1Palette.light);
    root.style.setProperty('--side1-lighter', side1Palette.lighter);
    root.style.setProperty('--side1-text-dark', side1Palette.textDark);

    root.style.setProperty('--side2-color', side2Palette.main);
    root.style.setProperty('--side2-dark', side2Palette.dark);
    root.style.setProperty('--side2-light', side2Palette.light);
    root.style.setProperty('--side2-lighter', side2Palette.lighter);
    root.style.setProperty('--side2-text-dark', side2Palette.textDark);

    // Refresh the leanToColor cache with new colors
    refreshColorCache();

    // Update target selector
    const targetSide1 = document.getElementById('targetSide1');
    const targetSide2 = document.getElementById('targetSide2');
    const targetSide1Icon = document.getElementById('targetSide1Icon');
    const targetSide2Icon = document.getElementById('targetSide2Icon');

    if (targetSide1) {
        targetSide1.dataset.value = sideConfig.side1;
        targetSide1.title = `${sideConfig.side1} Victory`;
    }
    if (targetSide2) {
        targetSide2.dataset.value = sideConfig.side2;
        targetSide2.title = `${sideConfig.side2} Victory`;
    }
    if (targetSide1Icon) targetSide1Icon.textContent = sideConfig.side1_letter || sideConfig.side1_abbrev.charAt(0);
    if (targetSide2Icon) targetSide2Icon.textContent = sideConfig.side2_letter || sideConfig.side2_abbrev.charAt(0);

    // Update vote share labels
    const side1VoteLabel = document.getElementById('side1VoteLabel');
    const side2VoteLabel = document.getElementById('side2VoteLabel');
    if (side1VoteLabel) side1VoteLabel.textContent = `${sideConfig.side1_abbrev} Vote`;
    if (side2VoteLabel) side2VoteLabel.textContent = `${sideConfig.side2_abbrev} Vote`;

    // Update partisan distribution labels
    const safeSide1Label = document.getElementById('safeSide1Label');
    const leanSide1Label = document.getElementById('leanSide1Label');
    const safeSide2Label = document.getElementById('safeSide2Label');
    const leanSide2Label = document.getElementById('leanSide2Label');

    const s1Letter = sideConfig.side1_letter || sideConfig.side1_abbrev.charAt(0);
    const s2Letter = sideConfig.side2_letter || sideConfig.side2_abbrev.charAt(0);

    if (safeSide1Label) safeSide1Label.textContent = `Safe ${s1Letter}`;
    if (leanSide1Label) leanSide1Label.textContent = `Likely ${s1Letter}`;
    if (safeSide2Label) safeSide2Label.textContent = `Safe ${s2Letter}`;
    if (leanSide2Label) leanSide2Label.textContent = `Likely ${s2Letter}`;

    // Set default target to side1
    state.setSelectedTarget(sideConfig.side1);

    console.log(`Side config initialized: ${sideConfig.side1} (${sideConfig.side1_color}) vs ${sideConfig.side2} (${sideConfig.side2_color})`);
}

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

        // Initialize side configuration (colors, labels, etc.)
        if (initData.sideConfig) {
            initSideConfig(initData.sideConfig);
        }

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

        // Setup score restore click handler
        setupScoreRestoreClick();

        // Initial render
        render();

        // Show canvas and controls
        loadingState.style.display = 'none';
        state.canvas.style.display = 'block';
        if (floatingControls) floatingControls.style.display = 'flex';
        if (floatingEV) floatingEV.style.display = 'flex';
        if (dashboard) dashboard.style.display = 'grid';

        // Initialize carousels
        state.setEvCarousel(new StatCarousel('evCarousel', 2500));

        // Initialize cycling bar pairs for win rate histogram
        state.setSide1BarPair(new CyclingBarPair('side1ImproveBar', 'side1WinBar', 1500));
        state.setSide2BarPair(new CyclingBarPair('side2ImproveBar', 'side2WinBar', 1500));

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

    state.socket.on('best_restored', () => {
        isPaused = true;  // Can resume from best state
    });
}

// Initialize Lucide icons and start the app
lucide.createIcons();
setupButtonHandlers();
init();
