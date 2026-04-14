import { api } from "../api.js";
import { renderTable, formatNumber } from "../components/table.js";
import { createMiniChart } from "../components/chart.js";

export async function renderDashboard(container) {
    container.innerHTML = `
        <h2 style="margin-bottom: 1rem;">Dashboard</h2>

        <div class="card mb-1">
            <div class="card-title">Data Sync</div>
            <div class="sync-form">
                <label>
                    Market
                    <select id="sync-market">
                        <option value="US">US</option>
                        <option value="JP">JP</option>
                    </select>
                </label>
                <label>
                    Symbol
                    <input id="sync-symbol" placeholder="AAPL, 7203..." size="10">
                </label>
                <label>
                    From
                    <input id="sync-from" type="date" value="2024-01-01">
                </label>
                <label>
                    To
                    <input id="sync-to" type="date">
                </label>
                <button id="sync-btn" class="btn-primary">Sync</button>
            </div>
            <div id="sync-message"></div>
        </div>

        <div class="card">
            <div class="card-title">Registered Stocks</div>
            <div id="stock-list"></div>
        </div>
    `;

    // Set default "to" date to today
    const toInput = document.getElementById("sync-to");
    toInput.value = new Date().toISOString().slice(0, 10);

    // Sync button handler
    document.getElementById("sync-btn").addEventListener("click", handleSync);

    // Load stock list
    await loadStockList();
}

async function handleSync() {
    const btn = document.getElementById("sync-btn");
    const msgEl = document.getElementById("sync-message");
    const market = document.getElementById("sync-market").value;
    const symbol = document.getElementById("sync-symbol").value.trim();
    const from = document.getElementById("sync-from").value;
    const to = document.getElementById("sync-to").value;

    if (!symbol) {
        msgEl.innerHTML = `<div class="message message-error">Symbol is required</div>`;
        return;
    }

    btn.disabled = true;
    btn.textContent = "Syncing...";
    msgEl.innerHTML = "";

    try {
        const result = await api.syncStock(symbol, market, from || null, to || null);
        msgEl.innerHTML = `<div class="message message-success">${result.message}</div>`;
        await loadStockList();
    } catch (e) {
        msgEl.innerHTML = `<div class="message message-error">${e.message}</div>`;
    } finally {
        btn.disabled = false;
        btn.textContent = "Sync";
    }
}

async function loadStockList() {
    const listEl = document.getElementById("stock-list");
    try {
        const data = await api.listStocks();
        if (data.stocks.length === 0) {
            listEl.innerHTML = `<div class="empty-state">No stocks registered yet. Use the sync form above to add stocks.</div>`;
            return;
        }

        renderTable(listEl, {
            columns: [
                {
                    key: "symbol",
                    label: "Symbol",
                    render: (row) =>
                        `<a href="#/stock/${row.market}/${row.symbol}" class="stock-link">${row.symbol}</a>`,
                },
                { key: "market", label: "Market" },
                { key: "name", label: "Name" },
                { key: "sector", label: "Sector" },
                { key: "currency", label: "Currency" },
            ],
            rows: data.stocks,
            onRowClick: (row) => {
                location.hash = `#/stock/${row.market}/${row.symbol}`;
            },
        });
    } catch (e) {
        listEl.innerHTML = `<div class="message message-error">${e.message}</div>`;
    }
}
