import { api } from "../api.js";
import { createCandlestickChart } from "../components/chart.js";
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
        <div class="chart-container" id="price-chart"></div>
        <div class="mt-1" id="price-table-container"></div>
    `;

    // Load stock info
    try {
        const detail = await api.getStockDetail(market, symbol);
        const info = detail.info;
        const titleEl = document.getElementById("stock-title");
        titleEl.textContent = `${info.name || symbol} (${market}:${symbol})`;

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
    } catch (e) {
        document.getElementById("stock-info").innerHTML =
            `<div class="message message-error">${e.message}</div>`;
    }

    // Load chart
    try {
        const priceData = await api.getPrices(market, symbol);
        const chartEl = document.getElementById("price-chart");

        if (priceData.prices.length === 0) {
            chartEl.innerHTML = `<div class="empty-state">No price data available. Sync this stock first.</div>`;
            return;
        }

        createCandlestickChart(chartEl, priceData.prices);
    } catch (e) {
        document.getElementById("price-chart").innerHTML =
            `<div class="message message-error">${e.message}</div>`;
    }
}
