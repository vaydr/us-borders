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
const safeBlueEl = document.getElementById('safeBlue');
const leanBlueEl = document.getElementById('leanBlue');
const tossupEl = document.getElementById('tossup');
const leanRedEl = document.getElementById('leanRed');
const safeRedEl = document.getElementById('safeRed');
const swingEVsEl = document.getElementById('swingEVs');
const currentScoreEl = document.getElementById('currentScore');
const scoreSubtitleEl = document.getElementById('scoreSubtitle');
const scoreLine = document.getElementById('scoreLine');
const scoreArea = document.getElementById('scoreArea');

// Vertical EV bar elements
const evDemBarV = document.getElementById('evDemBarV');
const evRepBarV = document.getElementById('evRepBarV');
const evDemSwingBarV = document.getElementById('evDemSwingBarV');
const evRepSwingBarV = document.getElementById('evRepSwingBarV');
const evDemVEl = document.getElementById('evDemV');
const evRepVEl = document.getElementById('evRepV');
const evDemSwingVEl = document.getElementById('evDemSwingV');
const evRepSwingVEl = document.getElementById('evRepSwingV');
const evTotalRepEl = document.getElementById('evTotalRep');
const evTotalDemEl = document.getElementById('evTotalDem');
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
    let safeD = 0, leanD = 0, tossup = 0, leanR = 0, safeR = 0;

    for (const stateAbbrev of states) {
        const lean = state.stateLeans[stateAbbrev] || 0;
        const absLean = Math.abs(lean);
        const ev = state.stateEVs[stateAbbrev] || 0;

        if (absLean <= 0.05) {
            swingCount++;
            swingEVs += ev;
            tossup++;
        } else if (lean < -0.15) {
            safeD++;
        } else if (lean < -0.05) {
            leanD++;
        } else if (lean > 0.15) {
            safeR++;
        } else if (lean > 0.05) {
            leanR++;
        }
    }

    // EV Margin: (winner EV %) - (winner popular vote %)
    // Popular vote is fixed based on county partisan lean * population
    let demPopVote = 0, repPopVote = 0;
    for (const [geoid, lean] of Object.entries(state.partisanLean)) {
        const pop = state.population[geoid] || 0;
        // lean > 0 means R, lean < 0 means D
        // Approximate: if lean is 0.1, then 55% voted R, 45% voted D
        const rPct = (1 + lean) / 2;
        const dPct = 1 - rPct;
        repPopVote += pop * rPct;
        demPopVote += pop * dPct;
    }
    const totalPopVote = demPopVote + repPopVote;
    const demPopPct = totalPopVote > 0 ? (demPopVote / totalPopVote) * 100 : 50;
    const repPopPct = totalPopVote > 0 ? (repPopVote / totalPopVote) * 100 : 50;

    // EV percentages from election object
    const totalEV = state.election.d_ev + state.election.r_ev;
    const demEVPct = totalEV > 0 ? (state.election.d_ev / totalEV) * 100 : 50;
    const repEVPct = totalEV > 0 ? (state.election.r_ev / totalEV) * 100 : 50;

    // EV margin = winner's EV% - winner's pop%
    // Positive means EV overperformance, negative means underperformance
    const evWinner = state.election.d_ev > state.election.r_ev ? 'dem' : state.election.r_ev > state.election.d_ev ? 'rep' : 'tie';
    let evMarginValue = 0;
    if (evWinner === 'dem') {
        evMarginValue = demEVPct - demPopPct;
    } else if (evWinner === 'rep') {
        evMarginValue = repEVPct - repPopPct;
    }

    // Popular vote margin
    const popVoteMargin = Math.abs(demPopPct - repPopPct);
    const popVoteWinner = demPopPct > repPopPct ? 'dem' : repPopPct > demPopPct ? 'rep' : 'tie';

    return {
        swingCount,
        swingEVs,
        evMarginValue,
        evWinner,
        categories: { safeD, leanD, tossup, leanR, safeR },
        stateCount: states.length,
        popVote: {
            demPct: demPopPct,
            repPct: repPopPct,
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

    // Colors: bins 0-1 safe D, 2-3 likely D, 4-7 lean D, 8-11 tossup, 12-15 lean R, 16-17 likely R, 18-19 safe R
    const getColor = (i) => {
        if (i < 2) return '#2563eb';      // Safe D
        if (i < 4) return '#3b82f6';      // Likely D (between safe and lean)
        if (i < 8) return '#60a5fa';      // Lean D
        if (i < 12) return '#a855f7';     // Tossup
        if (i < 16) return '#f87171';     // Lean R
        if (i < 18) return '#ef4444';     // Likely R (between lean and safe)
        return '#dc2626';                  // Safe R
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
    const winner = state.election.d_ev > state.election.r_ev ? 'dem' : state.election.r_ev > state.election.d_ev ? 'rep' : 'tie';
    if (winner === 'tie') return null;

    const states = Object.keys(state.stateLeans);

    // Build array of states with their EVs and margin for the winner
    const statesData = states.map(stateAbbrev => {
        const lean = state.stateLeans[stateAbbrev] || 0;
        const ev = state.stateEVs[stateAbbrev] || 0;
        // winnerMargin: positive = good for winner, negative = bad for winner
        // If dem wins, negative lean is good (dem-leaning)
        // If rep wins, positive lean is good (rep-leaning)
        const winnerMargin = winner === 'dem' ? -lean : lean;
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
        // Color based on lean
        const lean = tipping.lean;
        if (Math.abs(lean) <= 0.05) {
            tippingStateEl.style.color = '#a855f7';
        } else if (lean < 0) {
            tippingStateEl.style.color = '#3b82f6';
        } else {
            tippingStateEl.style.color = '#ef4444';
        }
    }

    // Update subtitle with margin
    if (tippingSubtitleEl) {
        const marginPct = Math.abs(tipping.margin * 100).toFixed(1);
        const party = tipping.lean < 0 ? 'D' : tipping.lean > 0 ? 'R' : '';
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
    const repSafeStates = [];
    const repSwingStates = [];
    const demSwingStates = [];
    const demSafeStates = [];

    for (const [stateAbbrev, lean] of Object.entries(state.stateLeans)) {
        const ev = state.stateEVs[stateAbbrev] || 0;
        if (ev === 0) continue;

        const isSwing = Math.abs(lean) <= 0.05;
        const stateData = { state: stateAbbrev, ev, lean };

        if (lean < 0) {
            if (isSwing) {
                demSwingStates.push(stateData);
            } else {
                demSafeStates.push(stateData);
            }
        } else if (lean > 0) {
            if (isSwing) {
                repSwingStates.push(stateData);
            } else {
                repSafeStates.push(stateData);
            }
        } else {
            // Exactly 0 - put in swing (could go either way)
            demSwingStates.push({ ...stateData, ev: ev / 2 });
            repSwingStates.push({ ...stateData, ev: ev / 2 });
        }
    }

    // Sort by lean: most partisan at edges, swing-adjacent near middle
    // Rep segments: highest lean first (top of bar, most R)
    // Dem segments: lowest lean first (bottom of bar, most D)
    repSafeStates.sort((a, b) => b.lean - a.lean);
    repSwingStates.sort((a, b) => b.lean - a.lean);
    demSwingStates.sort((a, b) => b.lean - a.lean);  // Least negative (closest to 0) first
    demSafeStates.sort((a, b) => b.lean - a.lean);   // Least negative first, most D at bottom

    // Calculate totals
    const repSafeEV = repSafeStates.reduce((sum, s) => sum + s.ev, 0);
    const repSwingEV = repSwingStates.reduce((sum, s) => sum + s.ev, 0);
    const demSwingEV = demSwingStates.reduce((sum, s) => sum + s.ev, 0);
    const demSafeEV = demSafeStates.reduce((sum, s) => sum + s.ev, 0);

    const totalEV = repSafeEV + repSwingEV + demSwingEV + demSafeEV;
    const repSafePct = totalEV > 0 ? (repSafeEV / totalEV) * 100 : 25;
    const repSwingPct = totalEV > 0 ? (repSwingEV / totalEV) * 100 : 25;
    const demSwingPct = totalEV > 0 ? (demSwingEV / totalEV) * 100 : 25;
    const demSafePct = totalEV > 0 ? (demSafeEV / totalEV) * 100 : 25;

    // Set segment heights and generate state segment HTML
    if (evRepBarV) {
        evRepBarV.style.height = repSafePct + '%';
        const labelHTML = `<span id="evRepV">${Math.round(repSafeEV)}</span>`;
        evRepBarV.innerHTML = buildStateSegmentHTML(repSafeStates, repSafePct) + labelHTML;
    }
    if (evRepSwingBarV) {
        evRepSwingBarV.style.height = repSwingPct + '%';
        const labelHTML = `<span id="evRepSwingV">${repSwingEV > 0 ? Math.round(repSwingEV) : ''}</span>`;
        evRepSwingBarV.innerHTML = buildStateSegmentHTML(repSwingStates, repSwingPct) + labelHTML;
    }
    if (evDemSwingBarV) {
        evDemSwingBarV.style.height = demSwingPct + '%';
        const labelHTML = `<span id="evDemSwingV">${demSwingEV > 0 ? Math.round(demSwingEV) : ''}</span>`;
        evDemSwingBarV.innerHTML = buildStateSegmentHTML(demSwingStates, demSwingPct) + labelHTML;
    }
    if (evDemBarV) {
        evDemBarV.style.height = demSafePct + '%';
        const labelHTML = `<span id="evDemV">${Math.round(demSafeEV)}</span>`;
        evDemBarV.innerHTML = buildStateSegmentHTML(demSafeStates, demSafePct) + labelHTML;
    }

    // Attach hover handlers to newly created segments
    attachEVBarHoverHandlers();

    // Update winner (based on total EVs)
    const totalDem = demSafeEV + demSwingEV;
    const totalRep = repSafeEV + repSwingEV;
    const winner = totalDem > totalRep ? 'DEM' : totalRep > totalDem ? 'GOP' : 'TIE';

    // Update total labels on the left side
    if (evTotalRepEl) {
        evTotalRepEl.textContent = Math.round(totalRep);
        evTotalRepEl.className = 'ev-total-label rep' + (winner === 'GOP' ? ' winner' : '');
    }
    if (evTotalDemEl) {
        evTotalDemEl.textContent = Math.round(totalDem);
        evTotalDemEl.className = 'ev-total-label dem' + (winner === 'DEM' ? ' winner' : '');
    }

    // Calculate signed margin for coloring: positive = R, negative = D
    const signedMarginPct = (totalRep - totalDem) / 538;

    if (winnerVEl) {
        winnerVEl.textContent = winner;
        winnerVEl.className = 'stat-value';
        winnerVEl.style.color = leanToColor(signedMarginPct * 3);
    }

    // Update EV margin
    const margin = Math.abs(totalDem - totalRep);
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
    if (safeBlueEl) safeBlueEl.textContent = metrics.categories.safeD;
    if (leanBlueEl) leanBlueEl.textContent = metrics.categories.leanD;
    if (tossupEl) tossupEl.textContent = metrics.categories.tossup;
    if (leanRedEl) leanRedEl.textContent = metrics.categories.leanR;
    if (safeRedEl) safeRedEl.textContent = metrics.categories.safeR;

    // Update swing EVs
    if (swingEVsEl) swingEVsEl.textContent = metrics.swingEVs;

    // Update tipping point
    updateTippingPoint();

    // Update vertical EV bar
    updateVerticalEVBar();

    // Update EV carousel
    if (state.evCarousel) {
        const pv = metrics.popVote;
        state.evCarousel.updateItem('demshare2', pv.demPct.toFixed(1) + '%', '#3b82f6');
        state.evCarousel.updateItem('repshare2', pv.repPct.toFixed(1) + '%', '#ef4444');
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
