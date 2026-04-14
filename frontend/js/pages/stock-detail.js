import { api } from "../api.js";
import {
    createCandlestickChart,
    addMAOverlay,
    addBBOverlay,
    createRSIChart,
    createMACDChart,
} from "../components/chart.js";
import { formatNumber } from "../components/table.js";

export async function renderStockDetail(container, market, symbol) {
    container.innerHTML = `
        <div style="display:flex; align-items:center; gap:1rem; margin-bottom:1rem;">
            <a href="#/" style="color:var(--text-muted); text-decoration:none;">&larr; Back</a>
            <h2 id="stock-title">${market}:${symbol}</h2>
        </div>
        <div id="stock-info" class="card mb-1">
            <div class="loading">Loading stock info...</div>
        </div>
        <div id="trade-buttons" class="card mb-1" style="display:none;">
            <div style="display: flex; gap: 0.5rem;">
                <button id="btn-buy" class="btn-buy" style="flex:1;">Buy</button>
                <button id="btn-sell" class="btn-sell" style="flex:1;">Sell</button>
            </div>
        </div>
        <div class="card mb-1" id="indicator-toggles">
            <div class="card-title">Indicators</div>
            <div style="display:flex; gap:1rem; flex-wrap:wrap; font-size:0.875rem;">
                <label><input type="checkbox" id="chk-ma" checked> MA (5/25/75)</label>
                <label><input type="checkbox" id="chk-bb"> Bollinger Bands</label>
                <label><input type="checkbox" id="chk-rsi"> RSI</label>
                <label><input type="checkbox" id="chk-macd"> MACD</label>
            </div>
        </div>
        <div class="chart-container" id="price-chart"></div>
        <div id="rsi-chart" style="margin-top:0.25rem;"></div>
        <div id="macd-chart" style="margin-top:0.25rem;"></div>
    `;

    // Load stock info
    try {
        const detail = await api.getStockDetail(market, symbol);
        const info = detail.info;
        document.getElementById("stock-title").textContent =
            `${info.name || symbol} (${market}:${symbol})`;

        const infoEl = document.getElementById("stock-info");
        const lp = detail.latest_price;
        infoEl.innerHTML = `
            <div class="grid grid-3">
                <div>
                    <div class="card-title">Sector</div>
                    <div>${info.sector || "-"}</div>
                </div>
                <div>
                    <div class="card-title">Currency</div>
                    <div>${info.currency}</div>
                </div>
                <div>
                    <div class="card-title">Latest Close</div>
                    <div class="card-value">${lp ? formatNumber(lp.close, 2) : "-"}</div>
                </div>
            </div>
        `;

        // Trade buttons
        const tradeButtons = document.getElementById("trade-buttons");
        tradeButtons.style.display = "block";
        const latestPrice = lp ? lp.close : "";
        document.getElementById("btn-buy").addEventListener("click", () => {
            location.hash = `#/trading?symbol=${symbol}&price=${latestPrice}`;
        });
        document.getElementById("btn-sell").addEventListener("click", () => {
            location.hash = `#/trading?symbol=${symbol}&price=${latestPrice}`;
        });
    } catch (e) {
        document.getElementById("stock-info").innerHTML =
            `<div class="message message-error">${e.message}</div>`;
    }

    // Load chart + indicators
    try {
        const priceData = await api.getPrices(market, symbol);
        const chartEl = document.getElementById("price-chart");

        if (priceData.prices.length === 0) {
            chartEl.innerHTML = `<div class="empty-state">No price data available. Sync this stock first.</div>`;
            document.getElementById("indicator-toggles").style.display = "none";
            return;
        }

        const { chart } = createCandlestickChart(chartEl, priceData.prices);

        // Load indicators
        let indicators = null;
        try {
            indicators = await api.getIndicators(market, symbol, "ma,rsi,macd,bb");
        } catch (e) {
            // Indicators failed, chart still works
        }

        if (!indicators) return;

        // State for overlay series (to remove/add on toggle)
        let maSeries = null;
        let bbSeries = null;
        let rsiChart = null;
        let macdChart = null;

        function updateOverlays() {
            const showMA = document.getElementById("chk-ma").checked;
            const showBB = document.getElementById("chk-bb").checked;
            const showRSI = document.getElementById("chk-rsi").checked;
            const showMACD = document.getElementById("chk-macd").checked;

            // MA
            if (showMA && !maSeries && indicators.ma) {
                maSeries = addMAOverlay(chart, indicators.ma);
            } else if (!showMA && maSeries) {
                for (const s of Object.values(maSeries)) {
                    chart.removeSeries(s);
                }
                maSeries = null;
            }

            // Bollinger Bands
            if (showBB && !bbSeries && indicators.bollinger) {
                bbSeries = addBBOverlay(chart, indicators.bollinger);
            } else if (!showBB && bbSeries) {
                chart.removeSeries(bbSeries.upper);
                chart.removeSeries(bbSeries.middle);
                chart.removeSeries(bbSeries.lower);
                bbSeries = null;
            }

            // RSI
            const rsiEl = document.getElementById("rsi-chart");
            if (showRSI && !rsiChart && indicators.rsi) {
                rsiChart = createRSIChart(rsiEl, indicators.rsi);
            } else if (!showRSI && rsiChart) {
                rsiEl.innerHTML = "";
                rsiChart = null;
            }

            // MACD
            const macdEl = document.getElementById("macd-chart");
            if (showMACD && !macdChart && indicators.macd) {
                macdChart = createMACDChart(macdEl, indicators.macd);
            } else if (!showMACD && macdChart) {
                macdEl.innerHTML = "";
                macdChart = null;
            }
        }

        // Initial render
        updateOverlays();

        // Toggle listeners
        for (const id of ["chk-ma", "chk-bb", "chk-rsi", "chk-macd"]) {
            document.getElementById(id).addEventListener("change", updateOverlays);
        }
    } catch (e) {
        document.getElementById("price-chart").innerHTML =
            `<div class="message message-error">${e.message}</div>`;
    }
}
