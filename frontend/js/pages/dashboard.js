import { api } from "../api.js";
import { renderTable, formatNumber } from "../components/table.js";

export async function renderDashboard(container) {
    container.innerHTML = `
        <h2 style="margin-bottom: 1rem;">Dashboard</h2>

        <div class="grid grid-3 mb-1" id="account-summary">
            <div class="card">
                <div class="card-title">Cash</div>
                <div class="card-value" id="dash-cash">-</div>
            </div>
            <div class="card">
                <div class="card-title">Portfolio</div>
                <div class="card-value" id="dash-portfolio">-</div>
            </div>
            <div class="card">
                <div class="card-title">Total</div>
                <div class="card-value" id="dash-total">-</div>
            </div>
        </div>

        <div class="card mb-1">
            <div class="card-title">Data Sync</div>
            <div class="sync-form">
                <input type="hidden" id="sync-market" value="JP">
                <label>
                    銘柄コード
                    <input id="sync-symbol" placeholder="7203, 9984..." size="10">
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

        <div class="card mb-1">
            <div class="card-title" style="display:flex; justify-content:space-between; align-items:center;">
                <span>Collection Status</span>
                <button id="collect-btn" class="btn-primary" style="font-size:0.75rem; padding:0.3rem 0.6rem;">Run Now</button>
            </div>
            <div id="collection-status"></div>
        </div>

        <div class="card">
            <div class="card-title">Registered Stocks</div>
            <div id="stock-list"></div>
        </div>
    `;

    const toInput = document.getElementById("sync-to");
    toInput.value = new Date().toISOString().slice(0, 10);

    document.getElementById("sync-btn").addEventListener("click", handleSync);
    document.getElementById("collect-btn").addEventListener("click", handleCollect);

    await Promise.all([loadAccountSummary(), loadStockList(), loadCollectionStatus()]);
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

async function handleCollect() {
    const btn = document.getElementById("collect-btn");
    btn.disabled = true;
    btn.textContent = "Collecting...";
    try {
        const result = await api.runCollection();
        await loadCollectionStatus();
        const msg = `Collected: ${result.collected}, Errors: ${result.errors}`;
        document.getElementById("sync-message").innerHTML =
            `<div class="message ${result.errors ? "message-error" : "message-success"}">${msg}</div>`;
    } catch (e) {
        document.getElementById("sync-message").innerHTML =
            `<div class="message message-error">${e.message}</div>`;
    } finally {
        btn.disabled = false;
        btn.textContent = "Run Now";
    }
}

async function loadAccountSummary() {
    try {
        const info = await api.getAccount();
        document.getElementById("dash-cash").textContent = formatNumber(info.cash_balance);
        document.getElementById("dash-portfolio").textContent = formatNumber(info.portfolio_value);
        document.getElementById("dash-total").textContent = formatNumber(info.total_value);
    } catch (e) {
        // leave defaults
    }
}

async function loadCollectionStatus() {
    const el = document.getElementById("collection-status");
    try {
        const logs = await api.getCollectionStatus(5);
        if (logs.length === 0) {
            el.innerHTML = `<div class="text-muted" style="font-size:0.85rem;">No collection logs yet. Add stocks and set them as watched.</div>`;
            return;
        }
        let html = '<table style="font-size:0.85rem;">';
        html += "<tr><th>Time</th><th>Symbol</th><th>Status</th><th>Message</th></tr>";
        for (const log of logs) {
            const statusCls = log.status === "OK" ? "text-green" : "text-red";
            html += `<tr>
                <td>${log.fetched_at.slice(0, 16).replace("T", " ")}</td>
                <td>${log.symbol || "ALL"}</td>
                <td class="${statusCls}">${log.status}</td>
                <td class="text-muted">${log.message || ""}</td>
            </tr>`;
        }
        html += "</table>";
        el.innerHTML = html;
    } catch (e) {
        el.innerHTML = `<div class="text-muted">Failed to load status</div>`;
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
                { key: "name", label: "Name" },
                { key: "sector", label: "Sector" },
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
