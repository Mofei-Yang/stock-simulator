/**
 * Market Simulator Frontend — Candlestick Edition
 * 
 * Connects via WebSocket to receive real-time price ticks.
 * Batches 60 raw prices into 1 candlestick (OHLCV).
 * Renders candlestick chart and order book depth chart on Canvas.
 */

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------
const PRICES_PER_CANDLE = 60;  // raw ticks merged into one candle

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
let rawPrices = [];              // accumulator for current incomplete candle
let candles = [];                // completed {open, high, low, close, volume}
let volumeAccum = 0;             // volume accumulator for current candle
let ws = null;
let lastPrice = null;
let targetPricesPerSec = 10;     // default speed

// ---------------------------------------------------------------------------
// Toast Notifications
// ---------------------------------------------------------------------------
function showToast(message) {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 2500);
}

// ---------------------------------------------------------------------------
// WebSocket Connection
// ---------------------------------------------------------------------------
function connect() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${protocol}//${window.location.host}/ws`);

    ws.onopen = () => {
        console.log('WebSocket connected');
        updateStatus('connected');
        ws.send(JSON.stringify({ command: 'get_history', limit: 2000 }));
    };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'tick') {
            addTick(data.price, data.volume);
            updatePriceDisplay(data.price);
            updateStats(data.step, data.volume);
        } else if (data.type === 'history') {
            // Convert raw price history into candles
            buildCandlesFromHistory(data.prices);
            drawCandleChart();
            if (rawPrices.length > 0) {
                lastPrice = rawPrices[rawPrices.length - 1];
                updatePriceDisplay(lastPrice);
            }
        } else if (data.type === 'orderbook') {
            drawOrderBook(data);
        }
    };

    ws.onclose = () => {
        console.log('WebSocket disconnected, reconnecting in 2s...');
        updateStatus('disconnected');
        setTimeout(connect, 2000);
    };

    ws.onerror = (err) => {
        console.error('WebSocket error:', err);
    };
}

// ---------------------------------------------------------------------------
// Tick → Candle batching
// ---------------------------------------------------------------------------
function addTick(price, volume) {
    rawPrices.push(price);
    volumeAccum += volume;
    lastPrice = price;

    if (rawPrices.length >= PRICES_PER_CANDLE) {
        // Form a completed candle
        const candle = formCandle(rawPrices, volumeAccum);
        candles.push(candle);
        rawPrices = [];
        volumeAccum = 0;
        drawCandleChart();
    }
}

function formCandle(prices, totalVolume) {
    if (prices.length === 0) return null;
    return {
        open: prices[0],
        high: Math.max(...prices),
        low: Math.min(...prices),
        close: prices[prices.length - 1],
        volume: totalVolume,
    };
}

function buildCandlesFromHistory(history) {
    candles = [];
    rawPrices = [];
    volumeAccum = 0;

    // Process history in chunks of PRICES_PER_CANDLE
    for (let i = 0; i < history.length; i += PRICES_PER_CANDLE) {
        const chunk = history.slice(i, i + PRICES_PER_CANDLE);
        if (chunk.length === PRICES_PER_CANDLE) {
            candles.push(formCandle(chunk, 0)); // volume unknown from history
        } else {
            // Incomplete chunk → current forming candle
            rawPrices = chunk;
        }
    }
}

// ---------------------------------------------------------------------------
// Status & UI Updates
// ---------------------------------------------------------------------------
function updateStatus(state) {
    const el = document.getElementById('status');
    if (state === 'connected') {
        el.textContent = 'Running';
        el.className = 'status status-running';
    } else {
        el.textContent = 'Disconnected';
        el.className = 'status status-stopped';
    }
}

function updatePriceDisplay(price) {
    const el = document.getElementById('priceDisplay');
    el.textContent = price.toFixed(2);
    if (lastPrice !== null) {
        const prevClose = candles.length > 0 ? candles[candles.length - 1].open : price;
        el.className = price >= prevClose ? 'price-display price-up' : 'price-display price-down';
    }
}

function updateStats(step, volume) {
    document.getElementById('statStep').textContent = step;
    document.getElementById('statVolume').textContent = volume.toFixed(2);
    document.getElementById('statPoints').textContent = candles.length;
    document.getElementById('statRawTicks').textContent = rawPrices.length;
}

// ---------------------------------------------------------------------------
// Control Functions
// ---------------------------------------------------------------------------
async function controlSim(action) {
    try {
        await fetch(`/api/control/${action}`, { method: 'POST' });
    } catch (e) {
        console.error(`Failed to ${action} simulation:`, e);
    }
}

async function manualTrade(type) {
    try {
        await fetch(`/api/control/${type}?quantity=10`, { method: 'POST' });
    } catch (e) {
        console.error(`Failed to ${type}:`, e);
    }
}

async function changeSpeed() {
    const input = document.getElementById('speedInput');
    const val = parseInt(input.value);
    if (isNaN(val) || val < 1) return;
    targetPricesPerSec = val;
    try {
        await fetch(`/api/control/speed?prices_per_second=${val}`, { method: 'POST' });
        showToast(`Velocity set to ${val} prices/s`);
    } catch (e) {
        console.error('Failed to change speed:', e);
    }
}

async function changeTraders() {
    const input = document.getElementById('traderInput');
    const val = parseInt(input.value);
    if (isNaN(val) || val < 1) return;
    try {
        const resp = await fetch(`/api/control/traders?count=${val}`, { method: 'POST' });
        const data = await resp.json();
        showToast(`${data.trader_count} traders set`);
        document.getElementById('statTraders').textContent = data.trader_count;
    } catch (e) {
        console.error('Failed to change traders:', e);
    }
}

async function resetSim() {
    try {
        await fetch('/api/control/reset?initial_price=100.0', { method: 'POST' });
        rawPrices = [];
        candles = [];
        volumeAccum = 0;
        lastPrice = null;
        updatePriceDisplay(100.0);
        updateStats(0, 0);
        drawCandleChart();
        showToast('Simulation reset');
    } catch (e) {
        console.error('Failed to reset:', e);
    }
}

// ---------------------------------------------------------------------------
// Candlestick Chart (Canvas)
// ---------------------------------------------------------------------------
function drawCandleChart() {
    const canvas = document.getElementById('priceChart');
    const ctx = canvas.getContext('2d');
    
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * window.devicePixelRatio;
    canvas.height = rect.height * window.devicePixelRatio;
    ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
    
    const width = rect.width;
    const height = rect.height;
    const padding = { top: 20, right: 70, bottom: 30, left: 10 };

    // Clear
    ctx.fillStyle = '#0d1117';
    ctx.fillRect(0, 0, width, height);

    if (candles.length < 2) return;

    // Show last N candles
    const maxCandles = 100;
    const data = candles.slice(-maxCandles);
    
    // Include current forming candle's prices for range
    const allPrices = [...data.flatMap(c => [c.high, c.low]), ...rawPrices];
    const minPrice = Math.min(...allPrices);
    const maxPrice = Math.max(...allPrices);
    const priceRange = maxPrice - minPrice || 1;

    const yMin = minPrice - priceRange * 0.08;
    const yMax = maxPrice + priceRange * 0.08;
    const yRange = yMax - yMin;

    const chartWidth = width - padding.left - padding.right;
    const chartHeight = height - padding.top - padding.bottom;

    const candleWidth = chartWidth / data.length;
    const bodyWidth = Math.max(1, candleWidth * 0.7);
    const wickWidth = 1;

    const toY = (p) => padding.top + (1 - (p - yMin) / yRange) * chartHeight;

    // Grid lines
    ctx.strokeStyle = '#1a2332';
    ctx.lineWidth = 1;
    const gridLines = 6;
    for (let i = 0; i <= gridLines; i++) {
        const y = padding.top + (i / gridLines) * chartHeight;
        ctx.beginPath();
        ctx.moveTo(padding.left, y);
        ctx.lineTo(width - padding.right, y);
        ctx.stroke();

        const price = yMax - (i / gridLines) * yRange;
        ctx.fillStyle = '#4a5568';
        ctx.font = '11px monospace';
        ctx.textAlign = 'left';
        ctx.fillText(price.toFixed(2), width - padding.right + 5, y + 4);
    }

    // Draw candles
    data.forEach((c, i) => {
        const isGreen = c.close >= c.open;
        const color = isGreen ? '#22c55e' : '#ef4444';
        const x = padding.left + i * candleWidth + candleWidth / 2;

        // Wick (high-low line)
        ctx.strokeStyle = color;
        ctx.lineWidth = wickWidth;
        ctx.beginPath();
        ctx.moveTo(x, toY(c.high));
        ctx.lineTo(x, toY(c.low));
        ctx.stroke();

        // Body (open-close rectangle)
        const yOpen = toY(c.open);
        const yClose = toY(c.close);
        const bodyTop = Math.min(yOpen, yClose);
        const bodyHeight = Math.max(1, Math.abs(yOpen - yClose));

        ctx.fillStyle = color;
        ctx.fillRect(x - bodyWidth / 2, bodyTop, bodyWidth, bodyHeight);
    });

    // Current forming candle (partial)
    if (rawPrices.length > 0) {
        const open = rawPrices[0];
        const high = Math.max(...rawPrices);
        const low = Math.min(...rawPrices);
        const close = rawPrices[rawPrices.length - 1];
        const isGreen = close >= open;
        const color = isGreen ? 'rgba(34, 197, 94, 0.5)' : 'rgba(239, 68, 68, 0.5)';
        const x = padding.left + data.length * candleWidth + candleWidth / 2;

        ctx.strokeStyle = color;
        ctx.lineWidth = wickWidth;
        ctx.beginPath();
        ctx.moveTo(x, toY(high));
        ctx.lineTo(x, toY(low));
        ctx.stroke();

        const yOpen = toY(open);
        const yClose = toY(close);
        const bodyTop = Math.min(yOpen, yClose);
        const bodyHeight = Math.max(1, Math.abs(yOpen - yClose));
        ctx.fillStyle = color;
        ctx.fillRect(x - bodyWidth / 2, bodyTop, bodyWidth, bodyHeight);
    }

    // Price label for current price
    if (lastPrice !== null) {
        const cy = toY(lastPrice);
        const isGreen = rawPrices.length > 0 
            ? rawPrices[rawPrices.length - 1] >= rawPrices[0]
            : true;
        ctx.strokeStyle = isGreen ? '#22c55e' : '#ef4444';
        ctx.lineWidth = 1;
        ctx.setLineDash([3, 3]);
        ctx.beginPath();
        ctx.moveTo(padding.left, cy);
        ctx.lineTo(width - padding.right, cy);
        ctx.stroke();
        ctx.setLineDash([]);
    }
}

// ---------------------------------------------------------------------------
// Order Book Depth Chart (Canvas)
// ---------------------------------------------------------------------------
function drawOrderBook(data) {
    const canvas = document.getElementById('orderBookChart');
    const ctx = canvas.getContext('2d');
    
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * window.devicePixelRatio;
    canvas.height = rect.height * window.devicePixelRatio;
    ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
    
    const width = rect.width;
    const height = rect.height;
    const padding = { top: 20, right: 60, bottom: 30, left: 10 };

    ctx.fillStyle = '#0d1117';
    ctx.fillRect(0, 0, width, height);

    const bids = data.bids || {};
    const asks = data.asks || {};
    const lastPrice = data.last_price;

    const bidLevels = Object.entries(bids)
        .map(([p, q]) => ({ price: parseFloat(p), quantity: q }))
        .sort((a, b) => b.price - a.price);

    const askLevels = Object.entries(asks)
        .map(([p, q]) => ({ price: parseFloat(p), quantity: q }))
        .sort((a, b) => a.price - b.price);

    const allLevels = [...bidLevels, ...askLevels];
    if (allLevels.length === 0) return;

    const priceWindow = lastPrice * 0.02;
    const filtered = allLevels.filter(
        l => l.price >= lastPrice - priceWindow && l.price <= lastPrice + priceWindow
    );

    if (filtered.length === 0) return;

    const minP = Math.min(...filtered.map(l => l.price));
    const maxP = Math.max(...filtered.map(l => l.price));
    const maxQ = Math.max(...filtered.map(l => l.quantity));
    const pRange = maxP - minP || 1;
    const qRange = maxQ || 1;

    const chartWidth = width - padding.left - padding.right;
    const chartHeight = height - padding.top - padding.bottom;

    const toX = (p) => padding.left + ((p - minP) / pRange) * chartWidth;
    const barWidth = Math.max(2, chartWidth / (filtered.length * 1.5));

    // Bid bars (green)
    filtered.filter(l => l.price <= lastPrice).forEach(level => {
        const x = toX(level.price);
        const barHeight = (level.quantity / qRange) * chartHeight;
        const alpha = Math.min(1, level.quantity / qRange);
        ctx.fillStyle = `rgba(34, 197, 94, ${alpha * 0.7})`;
        ctx.fillRect(x - barWidth / 2, height - padding.bottom - barHeight, barWidth, barHeight);
    });

    // Ask bars (red)
    filtered.filter(l => l.price >= lastPrice).forEach(level => {
        const x = toX(level.price);
        const barHeight = (level.quantity / qRange) * chartHeight;
        const alpha = Math.min(1, level.quantity / qRange);
        ctx.fillStyle = `rgba(239, 68, 68, ${alpha * 0.7})`;
        ctx.fillRect(x - barWidth / 2, height - padding.bottom - barHeight, barWidth, barHeight);
    });

    // Last price line
    const priceX = toX(lastPrice);
    ctx.strokeStyle = '#f7fafc';
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(priceX, padding.top);
    ctx.lineTo(priceX, height - padding.bottom);
    ctx.stroke();
    ctx.setLineDash([]);

    ctx.fillStyle = '#f7fafc';
    ctx.font = '11px monospace';
    ctx.textAlign = 'center';
    ctx.fillText(lastPrice.toFixed(2), priceX, padding.top - 5);

    // Price axis
    ctx.fillStyle = '#4a5568';
    ctx.font = '10px monospace';
    ctx.textAlign = 'left';
    for (let i = 0; i <= 4; i++) {
        const p = minP + (i / 4) * pRange;
        ctx.fillText(p.toFixed(2), toX(p), height - padding.bottom + 15);
    }
}

// ---------------------------------------------------------------------------
// Periodic order book refresh
// ---------------------------------------------------------------------------
function requestOrderBook() {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ command: 'get_book' }));
    }
}
setInterval(requestOrderBook, 1500);

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------
window.addEventListener('DOMContentLoaded', () => {
    connect();
    setTimeout(drawCandleChart, 500);
    // Set default speed input
    document.getElementById('speedInput').value = targetPricesPerSec;
});

window.addEventListener('resize', () => {
    drawCandleChart();
});
