// Global application state

// Socket.io connection
export const socket = io();

// Canvas and context
export const canvas = document.getElementById('mapCanvas');
export const ctx = canvas.getContext('2d');

// Map data
export let geojson = null;
export let palette = [];
export let countyColors = {};
export let countyPaths = {};  // Pre-computed Path2D objects
export let countyEdges = {};  // geoid -> array of edges [{x1,y1,x2,y2}, ...]
export let neighbors = {};    // geoid -> [neighbor geoids]
export let sharedEdges = {};  // "geoid1-geoid2" -> Path2D of shared edge
export let partisanLean = {}; // geoid -> partisan lean value (-1 to 1)
export let population = {};   // geoid -> population
export let stateLeans = {};   // state -> avg partisan lean
export let countyToState = {}; // geoid -> state
export let colorMode = 'county-partisan'; // 'state', 'county-partisan', or 'state-partisan'
export let previousCountyToState = {}; // Previous state assignments for diff detection
export let countyChangeTime = {}; // geoid -> timestamp when county last changed (for fade animation)
export let rejectedCountyChangeTime = {}; // geoid -> timestamp when county was rejected (for black fade animation)
export let diffMode = false; // Whether diff highlighting is enabled
export let diffAnimationFrame = null; // Animation frame ID for diff fade effect
export const DIFF_FADE_DURATION = 500; // Fade duration in ms
export let election = { winner: '-', r_ev: 0, d_ev: 0 };
export let bounds = null;
export let transform = null;

// Tooltip data (computed once at init, updated on state changes)
export let stateNames = {};        // state abbrev -> full state name
export let stateCountyCounts = {}; // state abbrev -> number of counties
export let stateEVs = {};          // state abbrev -> electoral votes
export let statePopulations = {};  // state abbrev -> total population
export let hoveredState = null;    // Currently hovered state
export let hoveredEVState = null;  // State hovered in EV bar

// Track historical data for line charts
export let scoreHistory = []; // [{iter, score}, ...]
export let swingHistory = []; // [{iter, value}, ...]
export let fairnessHistory = []; // [{iter, value}, ...]
export let bestScore = -Infinity;
export let bestScoreInt = -Infinity; // Track best integer part for pulse
export let bestEvMarginInt = -1; // Track best EV margin integer for pulse
export let bestIteration = 0; // Iteration when best score was achieved

// Tipping point tracking
export let tippingPointCounts = {};  // state -> count of times as tipping point
export let currentTippingPoint = null;
export let lastTippingPoint = null;
export let isAlgorithmRunning = false;

// Win rate tracking
export let side1WinCount = 0;
export let side2WinCount = 0;

// Margin improvement tracking (when margin moves in your favor)
export let side1ImproveCount = 0;
export let side2ImproveCount = 0;
export let lastMargin = 0; // side1EV - side2EV


// Score tracking
export let currentScore = 0;

// K-way selector state
export let selectedTarget = 'Republican';
export let selectedMode = 'standard';

// Carousel reference
export let evCarousel = null;

// Side configuration (from server)
export let sideConfig = {
    side1: 'Republican',
    side1_color: 'red',
    side1_abbrev: 'GOP',
    side1_letter: 'R',
    side2: 'Democrat',
    side2_color: 'blue',
    side2_abbrev: 'DEM',
    side2_letter: 'D'
};

// Setters for mutable state
export function setGeojson(val) { geojson = val; }
export function setPalette(val) { palette = val; }
export function setCountyColors(val) { countyColors = val; }
export function setCountyPaths(val) { countyPaths = val; }
export function setCountyEdges(val) { countyEdges = val; }
export function setNeighbors(val) { neighbors = val; }
export function setSharedEdges(val) { sharedEdges = val; }
export function setPartisanLean(val) { partisanLean = val; }
export function setPopulation(val) { population = val; }
export function setStateLeans(val) { stateLeans = val; }
export function setCountyToState(val) { countyToState = val; }
export function setColorMode(val) { colorMode = val; }
export function setPreviousCountyToState(val) { previousCountyToState = val; }
export function setCountyChangeTime(val) { countyChangeTime = val; }
export function setRejectedCountyChangeTime(val) { rejectedCountyChangeTime = val; }
export function setDiffMode(val) { diffMode = val; }
export function setDiffAnimationFrame(val) { diffAnimationFrame = val; }
export function setElection(val) { election = val; }
export function setBounds(val) { bounds = val; }
export function setTransform(val) { transform = val; }
export function setStateNames(val) { stateNames = val; }
export function setStateCountyCounts(val) { stateCountyCounts = val; }
export function setStateEVs(val) { stateEVs = val; }
export function setStatePopulations(val) { statePopulations = val; }
export function setHoveredState(val) { hoveredState = val; }
export function setHoveredEVState(val) { hoveredEVState = val; }
export function setScoreHistory(val) { scoreHistory = val; }
export function setSwingHistory(val) { swingHistory = val; }
export function setFairnessHistory(val) { fairnessHistory = val; }
export function setBestScore(val) { bestScore = val; }
export function setBestScoreInt(val) { bestScoreInt = val; }
export function setBestEvMarginInt(val) { bestEvMarginInt = val; }
export function setBestIteration(val) { bestIteration = val; }
export function setTippingPointCounts(val) { tippingPointCounts = val; }
export function setCurrentTippingPoint(val) { currentTippingPoint = val; }
export function setLastTippingPoint(val) { lastTippingPoint = val; }
export function setIsAlgorithmRunning(val) { isAlgorithmRunning = val; }
export function setSide1WinCount(val) { side1WinCount = val; }
export function setSide2WinCount(val) { side2WinCount = val; }
export function incrementSide1WinCount() { side1WinCount++; }
export function incrementSide2WinCount() { side2WinCount++; }
export function setSide1ImproveCount(val) { side1ImproveCount = val; }
export function setSide2ImproveCount(val) { side2ImproveCount = val; }
export function incrementSide1ImproveCount() { side1ImproveCount++; }
export function incrementSide2ImproveCount() { side2ImproveCount++; }
export function setLastMargin(val) { lastMargin = val; }
export function setCurrentScore(val) { currentScore = val; }
export function setSelectedTarget(val) { selectedTarget = val; }
export function setSelectedMode(val) { selectedMode = val; }
export function setEvCarousel(val) { evCarousel = val; }
export function setSideConfig(val) { sideConfig = val; }

// Push to arrays
export function pushScoreHistory(val) { scoreHistory.push(val); }
export function pushSwingHistory(val) { swingHistory.push(val); }
export function pushFairnessHistory(val) { fairnessHistory.push(val); }

// Clear arrays
export function clearScoreHistory() { scoreHistory = []; }
export function clearSwingHistory() { swingHistory = []; }
export function clearFairnessHistory() { fairnessHistory = []; }
