// Dashboard metrics and updates

import * as state from './state.js';
import { leanToColor, renderLineChart } from './utils.js';
import { render } from './render.js';

// Setup click handler for restoring best state
export function setupScoreRestoreClick() {
    const scoreSubtitleEl = document.getElementById('scoreSubtitle');
    if (!scoreSubtitleEl) return;

    scoreSubtitleEl.addEventListener('click', () => {
        // Only restore if we have a best iteration
        if (state.bestIteration > 0) {
            state.socket.emit('restore_best');
        }
    });
}

// DOM elements
const swingStatesEl = document.getElementById('swingStates');
const swingCard = document.getElementById('swingCard');
const swingLine = document.getElementById('swingLine');
const swingArea = document.getElementById('swingArea');
const evMarginPctEl = document.getElementById('evMarginPct');
const fairnessScoreEl = document.getElementById('fairnessScore');
const fairnessCard = document.getElementById('fairnessCard');
const fairnessLine = document.getElementById('fairnessLine');
const fairnessArea = document.getElementById('fairnessArea');
const partisanHistogram = document.getElementById('partisanHistogram');
const safeSide2El = document.getElementById('safeSide2');
const leanSide2El = document.getElementById('leanSide2');
const tossupEl = document.getElementById('tossup');
const leanSide1El = document.getElementById('leanSide1');
const safeSide1El = document.getElementById('safeSide1');
const swingEVsEl = document.getElementById('swingEVs');
const currentScoreEl = document.getElementById('currentScore');
const scoreSubtitleEl = document.getElementById('scoreSubtitle');
const scoreLine = document.getElementById('scoreLine');
const scoreArea = document.getElementById('scoreArea');

// Vertical EV bar elements
const evSide2BarV = document.getElementById('evSide2BarV');
const evSide1BarV = document.getElementById('evSide1BarV');
const evSide2SwingBarV = document.getElementById('evSide2SwingBarV');
const evSide1SwingBarV = document.getElementById('evSide1SwingBarV');
const evSide2VEl = document.getElementById('evSide2V');
const evSide1VEl = document.getElementById('evSide1V');
const evSide2SwingVEl = document.getElementById('evSide2SwingV');
const evSide1SwingVEl = document.getElementById('evSide1SwingV');
const evTotalSide1El = document.getElementById('evTotalSide1');
const evTotalSide2El = document.getElementById('evTotalSide2');
const winnerVEl = document.getElementById('winnerV');
const evMarginVEl = document.getElementById('evMarginV');

// Tipping point elements
const tippingStateEl = document.getElementById('tippingState');
const tippingSubtitleEl = document.getElementById('tippingSubtitle');
const tippingHistogram = document.getElementById('tippingHistogram');
const tippingCard = document.getElementById('tippingCard');

// Calculate dashboard metrics
export function calculateDashboardMetrics() {
    const states = Object.keys(state.stateLeans);
    let swingCount = 0;
    let swingEVs = 0;
    let safeSide2 = 0, leanSide2 = 0, tossup = 0, leanSide1 = 0, safeSide1 = 0;

    for (const stateAbbrev of states) {
        const lean = state.stateLeans[stateAbbrev] || 0;
        const absLean = Math.abs(lean);
        const ev = state.stateEVs[stateAbbrev] || 0;

        if (absLean <= 0.05) {
            swingCount++;
            swingEVs += ev;
            tossup++;
        } else if (lean < -0.15) {
            safeSide2++;
        } else if (lean < -0.05) {
            leanSide2++;
        } else if (lean > 0.15) {
            safeSide1++;
        } else if (lean > 0.05) {
            leanSide1++;
        }
    }

    // EV Margin: (winner EV %) - (winner popular vote %)
    // Popular vote is fixed based on county partisan lean * population
    let side2PopVote = 0, side1PopVote = 0;
    for (const [geoid, lean] of Object.entries(state.partisanLean)) {
        const pop = state.population[geoid] || 0;
        // lean > 0 means side1, lean < 0 means side2
        // Approximate: if lean is 0.1, then 55% voted side1, 45% voted side2
        const s1Pct = (1 + lean) / 2;
        const s2Pct = 1 - s1Pct;
        side1PopVote += pop * s1Pct;
        side2PopVote += pop * s2Pct;
    }
    const totalPopVote = side2PopVote + side1PopVote;
    const side2PopPct = totalPopVote > 0 ? (side2PopVote / totalPopVote) * 100 : 50;
    const side1PopPct = totalPopVote > 0 ? (side1PopVote / totalPopVote) * 100 : 50;

    // EV percentages from election object (side2_ev and side1_ev)
    const side2EV = state.election.side2_ev ?? state.election.d_ev ?? 0;
    const side1EV = state.election.side1_ev ?? state.election.r_ev ?? 0;
    const totalEV = side2EV + side1EV;
    const side2EVPct = totalEV > 0 ? (side2EV / totalEV) * 100 : 50;
    const side1EVPct = totalEV > 0 ? (side1EV / totalEV) * 100 : 50;

    // EV margin = winner's EV% - winner's pop%
    // Positive means EV overperformance, negative means underperformance
    const evWinner = side2EV > side1EV ? 'side2' : side1EV > side2EV ? 'side1' : 'tie';
    let evMarginValue = 0;
    if (evWinner === 'side2') {
        evMarginValue = side2EVPct - side2PopPct;
    } else if (evWinner === 'side1') {
        evMarginValue = side1EVPct - side1PopPct;
    }

    // Popular vote margin
    const popVoteMargin = Math.abs(side2PopPct - side1PopPct);
    const popVoteWinner = side2PopPct > side1PopPct ? 'side2' : side1PopPct > side2PopPct ? 'side1' : 'tie';

    return {
        swingCount,
        swingEVs,
        evMarginValue,
        evWinner,
        categories: { safeSide2, leanSide2, tossup, leanSide1, safeSide1 },
        stateCount: states.length,
        popVote: {
            side2Pct: side2PopPct,
            side1Pct: side1PopPct,
            margin: popVoteMargin,
            winner: popVoteWinner,
            total: totalPopVote
        }
    };
}

// Update partisan histogram with 20 non-uniform bins
export function updateHistogram() {
    if (!partisanHistogram) return;

    // Bin edges as percentages (will divide by 100 for lean values)
    const edges = [0, 0.5, 1, 2, 4, 6, 10, 15, 22, 30, 100];
    // 10 bins per side = 20 total
    const bins = new Array(20).fill(0);

    for (const stateAbbrev of Object.keys(state.stateLeans)) {
        const lean = (state.stateLeans[stateAbbrev] || 0) * 100; // Convert to percentage

        // Find which bin this lean falls into
        let binIdx;
        if (lean <= 0) {
            // D side (bins 0-9, where 9 is closest to center)
            const absLean = Math.abs(lean);
            for (let i = 0; i < 10; i++) {
                if (absLean >= edges[10 - i - 1] && absLean < edges[10 - i]) {
                    binIdx = i;
                    break;
                }
            }
            if (binIdx === undefined) binIdx = 0; // Safe D (>30%)
        } else {
            // R side (bins 10-19, where 10 is closest to center)
            for (let i = 0; i < 10; i++) {
                if (lean >= edges[i] && lean < edges[i + 1]) {
                    binIdx = 10 + i;
                    break;
                }
            }
            if (binIdx === undefined) binIdx = 19; // Safe R (>30%)
        }
        bins[binIdx]++;
    }

    const maxBin = Math.max(...bins, 1);

    // Get colors from CSS custom properties
    const root = document.documentElement;
    const s2Dark = getComputedStyle(root).getPropertyValue('--side2-dark').trim() || '#2563eb';
    const s2Main = getComputedStyle(root).getPropertyValue('--side2-color').trim() || '#3b82f6';
    const s2Light = getComputedStyle(root).getPropertyValue('--side2-light').trim() || '#60a5fa';
    const tieColor = getComputedStyle(root).getPropertyValue('--tie-color').trim() || '#a855f7';
    const s1Light = getComputedStyle(root).getPropertyValue('--side1-light').trim() || '#f87171';
    const s1Main = getComputedStyle(root).getPropertyValue('--side1-color').trim() || '#ef4444';
    const s1Dark = getComputedStyle(root).getPropertyValue('--side1-dark').trim() || '#dc2626';

    // Colors: bins 0-1 safe side2, 2-3 likely side2, 4-7 lean side2, 8-11 tossup, 12-15 lean side1, 16-17 likely side1, 18-19 safe side1
    const getColor = (i) => {
        if (i < 2) return s2Dark;      // Safe side2
        if (i < 4) return s2Main;      // Likely side2
        if (i < 8) return s2Light;     // Lean side2
        if (i < 12) return tieColor;   // Tossup
        if (i < 16) return s1Light;    // Lean side1
        if (i < 18) return s1Main;     // Likely side1
        return s1Dark;                  // Safe side1
    };

    // Flex widths proportional to bin range size
    const flexWidths = [5, 5, 4, 4, 3, 2, 2, 1, 1, 1, 1, 1, 1, 2, 2, 3, 4, 4, 5, 5];

    partisanHistogram.innerHTML = bins.map((count, i) => {
        const height = Math.max(2, (count / maxBin) * 90);
        const color = getColor(i);
        const flex = flexWidths[i];
        return `<div class="hist-bar" style="height: ${height}px; background: ${color}; flex: ${flex};"></div>`;
    }).join('');
}

// Calculate tipping point state
export function calculateTippingPoint() {
    const side2EV = state.election.side2_ev ?? state.election.d_ev ?? 0;
    const side1EV = state.election.side1_ev ?? state.election.r_ev ?? 0;
    const winner = side2EV > side1EV ? 'side2' : side1EV > side2EV ? 'side1' : 'tie';
    if (winner === 'tie') return null;

    const states = Object.keys(state.stateLeans);

    // Build array of states with their EVs and margin for the winner
    const statesData = states.map(stateAbbrev => {
        const lean = state.stateLeans[stateAbbrev] || 0;
        const ev = state.stateEVs[stateAbbrev] || 0;
        // winnerMargin: positive = good for winner, negative = bad for winner
        // If side2 wins, negative lean is good (side2-leaning)
        // If side1 wins, positive lean is good (side1-leaning)
        const winnerMargin = winner === 'side2' ? -lean : lean;
        return { state: stateAbbrev, ev, lean, winnerMargin };
    });

    // Sort by winner's margin (safest states first)
    statesData.sort((a, b) => b.winnerMargin - a.winnerMargin);

    // Sum EVs until we hit 270
    let evSum = 0;
    for (const s of statesData) {
        evSum += s.ev;
        if (evSum >= 270) {
            return { state: s.state, lean: s.lean, margin: s.winnerMargin, ev: s.ev };
        }
    }
    return null;
}

// Update tipping point display
export function updateTippingPoint() {
    const tipping = calculateTippingPoint();

    if (!tipping) {
        if (tippingStateEl) tippingStateEl.textContent = '-';
        return;
    }

    state.setCurrentTippingPoint(tipping.state);

    // Increment count for this state (only when algorithm is running)
    if (state.isAlgorithmRunning) {
        state.tippingPointCounts[tipping.state] = (state.tippingPointCounts[tipping.state] || 0) + 1;
    }

    // Update display with full state name
    if (tippingStateEl) {
        const fullName = state.stateNames[tipping.state] || tipping.state;
        tippingStateEl.textContent = fullName;
        // Color based on lean - use CSS custom properties
        const root = document.documentElement;
        const lean = tipping.lean;
        if (Math.abs(lean) <= 0.05) {
            tippingStateEl.style.color = getComputedStyle(root).getPropertyValue('--tie-color').trim() || '#a855f7';
        } else if (lean < 0) {
            tippingStateEl.style.color = getComputedStyle(root).getPropertyValue('--side2-color').trim() || '#3b82f6';
        } else {
            tippingStateEl.style.color = getComputedStyle(root).getPropertyValue('--side1-color').trim() || '#ef4444';
        }
    }

    // Update subtitle with margin
    if (tippingSubtitleEl) {
        const marginPct = Math.abs(tipping.margin * 100).toFixed(1);
        const s1Letter = state.sideConfig.side1_letter || 'R';
        const s2Letter = state.sideConfig.side2_letter || 'D';
        const party = tipping.lean < 0 ? s2Letter : tipping.lean > 0 ? s1Letter : '';
        tippingSubtitleEl.textContent = `${tipping.ev} EVs • ${party}+${marginPct}%`;
    }

    // Pulse effect if tipping point changed
    if (state.lastTippingPoint !== state.currentTippingPoint && state.lastTippingPoint !== null) {
        if (tippingCard) {
            tippingCard.classList.add('pulse');
            setTimeout(() => tippingCard.classList.remove('pulse'), 500);
        }
    }
    state.setLastTippingPoint(state.currentTippingPoint);

    // Update histogram
    updateTippingHistogram();
}

// Update tipping point histogram (vertical bars)
export function updateTippingHistogram() {
    if (!tippingHistogram) return;

    // Get top 35 states by count
    const sorted = Object.entries(state.tippingPointCounts)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 35);

    if (sorted.length === 0) {
        tippingHistogram.innerHTML = '';
        return;
    }

    const maxCount = sorted[0][1];

    tippingHistogram.innerHTML = sorted.map(([stateAbbrev, count]) => {
        const height = Math.max(5, (count / maxCount) * 100);
        const lean = state.stateLeans[stateAbbrev] || 0;
        const color = leanToColor(lean * 25);
        const isCurrent = stateAbbrev === state.currentTippingPoint;

        return `
            <div class="tipping-col">
                <div class="tipping-bar${isCurrent ? ' current' : ''}" style="height: ${height}px; background: ${color};"></div>
                <span class="tipping-label">${stateAbbrev}</span>
                <span class="tipping-count">${count}</span>
            </div>
        `;
    }).join('');
}

// Build state segment HTML for EV bar
function buildStateSegmentHTML(states, segmentHeight) {
    if (states.length === 0 || segmentHeight <= 0) return '';

    const totalEV = states.reduce((sum, s) => sum + s.ev, 0);
    if (totalEV === 0) return '';

    return states.map((s, i) => {
        const heightPct = (s.ev / totalEV) * 100;
        return `<div class="ev-state-segment" data-state="${s.state}" style="height: ${heightPct}%;"></div>`;
    }).join('');
}

// Attach hover handlers to state segments
function attachEVBarHoverHandlers() {
    document.querySelectorAll('.ev-state-segment').forEach(el => {
        el.addEventListener('mouseenter', () => {
            state.setHoveredEVState(el.dataset.state);
            render();
        });
        el.addEventListener('mouseleave', () => {
            state.setHoveredEVState(null);
            render();
        });
    });
}

// Update vertical EV bar
export function updateVerticalEVBar() {
    // Build arrays of states per segment
    const side1SafeStates = [];
    const side1SwingStates = [];
    const side2SwingStates = [];
    const side2SafeStates = [];

    for (const [stateAbbrev, lean] of Object.entries(state.stateLeans)) {
        const ev = state.stateEVs[stateAbbrev] || 0;
        if (ev === 0) continue;

        const isSwing = Math.abs(lean) <= 0.05;
        const stateData = { state: stateAbbrev, ev, lean };

        if (lean < 0) {
            if (isSwing) {
                side2SwingStates.push(stateData);
            } else {
                side2SafeStates.push(stateData);
            }
        } else if (lean > 0) {
            if (isSwing) {
                side1SwingStates.push(stateData);
            } else {
                side1SafeStates.push(stateData);
            }
        } else {
            // Exactly 0 - put in swing (could go either way)
            side2SwingStates.push({ ...stateData, ev: ev / 2 });
            side1SwingStates.push({ ...stateData, ev: ev / 2 });
        }
    }

    // Sort by lean: most partisan at edges, swing-adjacent near middle
    // Side1 segments: highest lean first (top of bar, most side1)
    // Side2 segments: lowest lean first (bottom of bar, most side2)
    side1SafeStates.sort((a, b) => b.lean - a.lean);
    side1SwingStates.sort((a, b) => b.lean - a.lean);
    side2SwingStates.sort((a, b) => b.lean - a.lean);  // Least negative (closest to 0) first
    side2SafeStates.sort((a, b) => b.lean - a.lean);   // Least negative first, most side2 at bottom

    // Calculate totals
    const side1SafeEV = side1SafeStates.reduce((sum, s) => sum + s.ev, 0);
    const side1SwingEV = side1SwingStates.reduce((sum, s) => sum + s.ev, 0);
    const side2SwingEV = side2SwingStates.reduce((sum, s) => sum + s.ev, 0);
    const side2SafeEV = side2SafeStates.reduce((sum, s) => sum + s.ev, 0);

    const totalEV = side1SafeEV + side1SwingEV + side2SwingEV + side2SafeEV;
    const side1SafePct = totalEV > 0 ? (side1SafeEV / totalEV) * 100 : 25;
    const side1SwingPct = totalEV > 0 ? (side1SwingEV / totalEV) * 100 : 25;
    const side2SwingPct = totalEV > 0 ? (side2SwingEV / totalEV) * 100 : 25;
    const side2SafePct = totalEV > 0 ? (side2SafeEV / totalEV) * 100 : 25;

    // Set segment heights and generate state segment HTML
    if (evSide1BarV) {
        evSide1BarV.style.height = side1SafePct + '%';
        const labelHTML = `<span id="evSide1V">${Math.round(side1SafeEV)}</span>`;
        evSide1BarV.innerHTML = buildStateSegmentHTML(side1SafeStates, side1SafePct) + labelHTML;
    }
    if (evSide1SwingBarV) {
        evSide1SwingBarV.style.height = side1SwingPct + '%';
        const labelHTML = `<span id="evSide1SwingV">${side1SwingEV > 0 ? Math.round(side1SwingEV) : ''}</span>`;
        evSide1SwingBarV.innerHTML = buildStateSegmentHTML(side1SwingStates, side1SwingPct) + labelHTML;
    }
    if (evSide2SwingBarV) {
        evSide2SwingBarV.style.height = side2SwingPct + '%';
        const labelHTML = `<span id="evSide2SwingV">${side2SwingEV > 0 ? Math.round(side2SwingEV) : ''}</span>`;
        evSide2SwingBarV.innerHTML = buildStateSegmentHTML(side2SwingStates, side2SwingPct) + labelHTML;
    }
    if (evSide2BarV) {
        evSide2BarV.style.height = side2SafePct + '%';
        const labelHTML = `<span id="evSide2V">${Math.round(side2SafeEV)}</span>`;
        evSide2BarV.innerHTML = buildStateSegmentHTML(side2SafeStates, side2SafePct) + labelHTML;
    }

    // Attach hover handlers to newly created segments
    attachEVBarHoverHandlers();

    // Update winner (based on total EVs)
    const totalSide2 = side2SafeEV + side2SwingEV;
    const totalSide1 = side1SafeEV + side1SwingEV;
    const s1Abbr = state.sideConfig.side1_abbrev || 'S1';
    const s2Abbr = state.sideConfig.side2_abbrev || 'S2';
    const winner = totalSide2 > totalSide1 ? s2Abbr : totalSide1 > totalSide2 ? s1Abbr : 'TIE';
    const winnerSide = totalSide2 > totalSide1 ? 'side2' : totalSide1 > totalSide2 ? 'side1' : 'tie';

    // Update total labels on the right side
    if (evTotalSide1El) {
        evTotalSide1El.textContent = Math.round(totalSide1);
        evTotalSide1El.className = 'ev-total-label side1' + (winnerSide === 'side1' ? ' winner' : '');
    }
    if (evTotalSide2El) {
        evTotalSide2El.textContent = Math.round(totalSide2);
        evTotalSide2El.className = 'ev-total-label side2' + (winnerSide === 'side2' ? ' winner' : '');
    }

    // Calculate signed margin for coloring: positive = side1, negative = side2
    const signedMarginPct = (totalSide1 - totalSide2) / 538;

    if (winnerVEl) {
        winnerVEl.textContent = winner;
        winnerVEl.className = 'stat-value';
        winnerVEl.style.color = leanToColor(signedMarginPct * 3);
    }

    // Update EV margin
    const margin = Math.abs(totalSide2 - totalSide1);
    if (evMarginVEl) {
        evMarginVEl.textContent = Math.round(margin);
        evMarginVEl.className = 'stat-value';
        evMarginVEl.style.color = leanToColor(signedMarginPct * 3);
    }
}

// Update entire dashboard
export function updateDashboard() {
    const metrics = calculateDashboardMetrics();
    const currentIter = state.scoreHistory.length > 0 ? state.scoreHistory[state.scoreHistory.length - 1].iter : state.swingHistory.length;

    // Update swing states
    if (swingStatesEl) swingStatesEl.textContent = metrics.swingCount;
    state.pushSwingHistory({ iter: currentIter, value: metrics.swingCount });
    renderLineChart(swingLine, swingArea, state.swingHistory);

    // Pulse effect
    if (swingCard && state.swingHistory.length > 1 && state.swingHistory[state.swingHistory.length - 1].value !== state.swingHistory[state.swingHistory.length - 2].value) {
        swingCard.classList.add('pulse');
        setTimeout(() => swingCard.classList.remove('pulse'), 500);
    }

    // Update EV Margin (winner EV% - loser EV%)
    const totalEV = state.election.d_ev + state.election.r_ev;
    const demEVPct = totalEV > 0 ? (state.election.d_ev / totalEV) * 100 : 50;
    const repEVPct = totalEV > 0 ? (state.election.r_ev / totalEV) * 100 : 50;
    const evMarginPctValue = Math.abs(demEVPct - repEVPct);
    // Signed margin: positive = R winning, negative = D winning
    const evMarginSigned = (repEVPct - demEVPct) / 100;
    if (evMarginPctEl) {
        evMarginPctEl.textContent = evMarginPctValue.toFixed(1) + '%';
        evMarginPctEl.style.color = leanToColor(evMarginSigned * 3);

        // Pulse on new whole percent milestone
        const evMarginInt = Math.floor(evMarginPctValue);
        if (evMarginInt > state.bestEvMarginInt) {
            state.setBestEvMarginInt(evMarginInt);
            if (fairnessCard) {
                fairnessCard.classList.add('pulse');
                setTimeout(() => fairnessCard.classList.remove('pulse'), 500);
            }
        }
    }

    // Update Electoral Efficiency (EV% - PopVote%)
    // Signed: positive = winner overperforming, need to map to R/D
    const efficiencySigned = metrics.evWinner === 'rep' ? metrics.evMarginValue / 100 :
                             metrics.evWinner === 'dem' ? -metrics.evMarginValue / 100 : 0;
    if (fairnessScoreEl) {
        const sign = metrics.evMarginValue >= 0 ? '+' : '';
        fairnessScoreEl.textContent = sign + metrics.evMarginValue.toFixed(1) + '%';
        fairnessScoreEl.style.color = leanToColor(efficiencySigned * 3);
    }
    state.pushFairnessHistory({ iter: currentIter, value: Math.abs(metrics.evMarginValue) });
    renderLineChart(fairnessLine, fairnessArea, state.fairnessHistory);

    // Update histogram
    updateHistogram();

    // Update category counts
    if (safeSide2El) safeSide2El.textContent = metrics.categories.safeSide2;
    if (leanSide2El) leanSide2El.textContent = metrics.categories.leanSide2;
    if (tossupEl) tossupEl.textContent = metrics.categories.tossup;
    if (leanSide1El) leanSide1El.textContent = metrics.categories.leanSide1;
    if (safeSide1El) safeSide1El.textContent = metrics.categories.safeSide1;

    // Update swing EVs
    if (swingEVsEl) swingEVsEl.textContent = metrics.swingEVs;

    // Update tipping point
    updateTippingPoint();

    // Update vertical EV bar
    updateVerticalEVBar();

    // Update EV carousel
    if (state.evCarousel) {
        const pv = metrics.popVote;
        // Get colors from CSS custom properties
        const side2Color = getComputedStyle(document.documentElement).getPropertyValue('--side2-color').trim() || '#3b82f6';
        const side1Color = getComputedStyle(document.documentElement).getPropertyValue('--side1-color').trim() || '#ef4444';
        state.evCarousel.updateItem('side2share', pv.side2Pct.toFixed(1) + '%', side2Color);
        state.evCarousel.updateItem('side1share', pv.side1Pct.toFixed(1) + '%', side1Color);

        // Update margin: {winner_letter}+{margin%}
        const marginPct = Math.abs(pv.side1Pct - pv.side2Pct).toFixed(1);
        const winnerLetter = pv.side1Pct > pv.side2Pct
            ? (state.sideConfig.side1_letter || 'R')
            : (state.sideConfig.side2_letter || 'D');
        const marginColor = pv.side1Pct > pv.side2Pct ? side1Color : side2Color;
        state.evCarousel.updateItem('margin', `${winnerLetter}+${marginPct}%`, marginColor);
    }

    // Update score display and line chart
    if (currentScoreEl) {
        currentScoreEl.textContent = state.currentScore.toFixed(2);

        // Pulse on new best score integer milestone (server provides bestScore)
        const scoreInt = Math.floor(state.bestScore);
        if (scoreInt > state.bestScoreInt) {
            state.setBestScoreInt(scoreInt);
            const scoreCard = document.getElementById('scoreCard');
            if (scoreCard) {
                scoreCard.classList.add('pulse');
                setTimeout(() => scoreCard.classList.remove('pulse'), 500);
            }
        }
    }
    if (scoreSubtitleEl) {
        if (state.bestIteration > 0) {
            scoreSubtitleEl.textContent = `best: ${state.bestScore.toFixed(2)} @ ${state.bestIteration.toLocaleString()}`;
            scoreSubtitleEl.classList.add('clickable');
        } else {
            scoreSubtitleEl.textContent = 'higher is better';
            scoreSubtitleEl.classList.remove('clickable');
        }
    }

    // Draw score line chart
    const scoreChartData = state.scoreHistory.map(d => ({ iter: d.iter, value: d.score }));
    renderLineChart(scoreLine, scoreArea, scoreChartData);
}

// Reset dashboard state
export function resetDashboard() {
    state.setCurrentScore(0);
    state.setBestScore(-Infinity);
    state.setBestScoreInt(-Infinity);
    state.setBestEvMarginInt(-1);
    state.setBestIteration(0);
    state.clearScoreHistory();
    state.clearSwingHistory();
    state.clearFairnessHistory();

    if (currentScoreEl) currentScoreEl.textContent = '0.00';
    if (scoreSubtitleEl) scoreSubtitleEl.textContent = 'higher is better';
    if (scoreLine) scoreLine.setAttribute('d', '');
    if (scoreArea) scoreArea.setAttribute('d', '');
    if (swingLine) swingLine.setAttribute('d', '');
    if (swingArea) swingArea.setAttribute('d', '');
    if (fairnessLine) fairnessLine.setAttribute('d', '');
    if (fairnessArea) fairnessArea.setAttribute('d', '');

    // Reset tipping point tracking
    state.setTippingPointCounts({});
    state.setCurrentTippingPoint(null);
    state.setLastTippingPoint(null);
    state.setIsAlgorithmRunning(false);
    if (tippingHistogram) tippingHistogram.innerHTML = '';
}
