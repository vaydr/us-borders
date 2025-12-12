// UI controls - K-way selectors and carousel

import * as state from './state.js';
import { render } from './render.js';

// K-way selector helper
export function setupKwaySelector(containerId, onChange) {
    const container = document.getElementById(containerId);
    if (!container) return () => null;
    const options = container.querySelectorAll('.kway-option');
    options.forEach(opt => {
        opt.addEventListener('click', () => {
            options.forEach(o => o.classList.remove('active'));
            opt.classList.add('active');
            const value = opt.dataset.value;
            if (onChange) onChange(value);
        });
    });
    // Return getter for current value
    return () => container.querySelector('.kway-option.active')?.dataset.value;
}

// StatCarousel - Reusable carousel component
export class StatCarousel {
    constructor(containerId, period = 5000) {
        this.container = document.getElementById(containerId);
        if (!this.container) return;

        this.items = this.container.querySelectorAll('.carousel-item');
        this.dotsContainer = this.container.querySelector('.carousel-dots');
        this.currentIndex = 0;
        this.period = period;
        this.intervalId = null;

        this.init();
    }

    init() {
        if (this.items.length <= 1) return;

        // Create dots
        this.items.forEach((_, i) => {
            const dot = document.createElement('div');
            dot.className = 'carousel-dot' + (i === 0 ? ' active' : '');
            dot.onclick = () => this.goTo(i);
            this.dotsContainer.appendChild(dot);
        });

        this.dots = this.dotsContainer.querySelectorAll('.carousel-dot');
        this.start();
    }

    start() {
        if (this.intervalId) clearInterval(this.intervalId);
        this.intervalId = setInterval(() => this.next(), this.period);
    }

    stop() {
        if (this.intervalId) {
            clearInterval(this.intervalId);
            this.intervalId = null;
        }
    }

    next() {
        this.goTo((this.currentIndex + 1) % this.items.length);
    }

    goTo(index) {
        if (index === this.currentIndex) return;

        // Exit current
        this.items[this.currentIndex].classList.remove('active');
        this.items[this.currentIndex].classList.add('exit');
        this.dots[this.currentIndex].classList.remove('active');

        // After transition, remove exit class
        setTimeout(() => {
            this.items[this.currentIndex].classList.remove('exit');
            this.currentIndex = index;

            // Enter new
            this.items[this.currentIndex].classList.add('active');
            this.dots[this.currentIndex].classList.add('active');
        }, 50);

        // Reset timer on manual navigation
        this.start();
    }

    // Add a new item dynamically
    addItem(key, valueHtml, label) {
        const item = document.createElement('div');
        item.className = 'carousel-item';
        item.dataset.key = key;
        item.innerHTML = `
            <div class="mini-stat-value" id="${key}Value">${valueHtml}</div>
            <div class="mini-stat-label">${label}</div>
        `;
        this.container.querySelector('.carousel-items').appendChild(item);

        const dot = document.createElement('div');
        dot.className = 'carousel-dot';
        dot.onclick = () => this.goTo(this.items.length);
        this.dotsContainer.appendChild(dot);

        // Refresh items and dots
        this.items = this.container.querySelectorAll('.carousel-item');
        this.dots = this.dotsContainer.querySelectorAll('.carousel-dot');
    }

    // Update value by key
    updateItem(key, valueHtml, color = null) {
        // Try both mini-stat-value and stat-value classes
        let item = this.container.querySelector(`[data-key="${key}"] .mini-stat-value`);
        if (!item) item = this.container.querySelector(`[data-key="${key}"] .stat-value`);
        if (item) {
            item.innerHTML = valueHtml;
            if (color) item.style.color = color;
        }
    }
}

// Setup all k-way selectors
export function setupAllControls() {
    const getColorMode = setupKwaySelector('colorModeKway', (value) => {
        state.setColorMode(value);
        render();
    });

    const getTarget = setupKwaySelector('targetKway', (value) => {
        state.setSelectedTarget(value);
    });

    const getMode = setupKwaySelector('modeKway', (value) => {
        state.setSelectedMode(value);
    });

    const getDiffMode = setupKwaySelector('diffKway', (value) => {
        state.setDiffMode(value === 'on');
        if (!state.diffMode) {
            state.setCountyChangeTime({});
            state.setRejectedCountyChangeTime({});
            if (state.diffAnimationFrame) {
                cancelAnimationFrame(state.diffAnimationFrame);
                state.setDiffAnimationFrame(null);
            }
        }
        render();
    });

    return { getColorMode, getTarget, getMode, getDiffMode };
}
