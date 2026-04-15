import { api } from "../api.js";
import { renderTable, formatNumber, colorBySign } from "../components/table.js";

export async function renderTrading(container) {
    container.innerHTML = `
        <h2 style="margin-bottom: 1rem;">取引</h2>

        <div class="grid grid-2 mb-1">
            <div class="card" id="account-card">
                <div class="card-title">口座情報</div>
                <div class="loading">読み込み中...</div>
            </div>
            <div class="card">
                <div class="card-title">新規注文</div>
                <div class="sync-form" style="flex-direction: column; align-items: stretch;">
                    <div style="display: flex; gap: 0.5rem; flex-wrap: wrap;">
                        <label>
                            銘柄コード
                            <input id="trade-symbol" placeholder="7203" size="8">
                        </label>
                        <label>
                            数量
                            <input id="trade-quantity" type="number" placeholder="100" size="6" min="1">
                        </label>
                        <label>
                            価格
                            <input id="trade-price" type="number" placeholder="2850" step="0.01" size="8">
                        </label>
                    </div>
                    <div style="display: flex; gap: 0.5rem; margin-top: 0.5rem;">
                        <button id="buy-btn" class="btn-buy" style="flex:1;">買い</button>
                        <button id="sell-btn" class="btn-sell" style="flex:1;">売り</button>
                    </div>
                </div>
                <div id="trade-message" style="margin-top: 0.5rem;"></div>
            </div>
        </div>

        <div class="grid grid-3 mb-1" id="stats-cards">
            <div class="card"><div class="card-title">実現損益</div><div class="card-value" id="stat-pnl">-</div></div>
            <div class="card"><div class="card-title">勝率</div><div class="card-value" id="stat-winrate">-</div></div>
            <div class="card"><div class="card-title">取引回数</div><div class="card-value" id="stat-trades">-</div></div>
        </div>

        <div class="card">
            <div class="card-title">取引履歴</div>
            <div id="trade-history"></div>
        </div>
    `;

    // URLパラメータからプリセット
    const urlParams = new URLSearchParams(location.hash.split("?")[1] || "");
    if (urlParams.get("symbol")) {
        document.getElementById("trade-symbol").value = urlParams.get("symbol");
    }
    if (urlParams.get("price")) {
        document.getElementById("trade-price").value = urlParams.get("price");
    }

    document.getElementById("buy-btn").addEventListener("click", () => handleTrade("BUY"));
    document.getElementById("sell-btn").addEventListener("click", () => handleTrade("SELL"));

    await Promise.all([loadAccount(), loadStats(), loadHistory()]);
}

async function handleTrade(side) {
    const symbol = document.getElementById("trade-symbol").value.trim();
    const quantity = parseInt(document.getElementById("trade-quantity").value, 10);
    const price = parseFloat(document.getElementById("trade-price").value);
    const msgEl = document.getElementById("trade-message");

    if (!symbol || !quantity || !price) {
        msgEl.innerHTML = `<div class="message message-error">全項目を入力してください</div>`;
        return;
    }

    const buyBtn = document.getElementById("buy-btn");
    const sellBtn = document.getElementById("sell-btn");
    buyBtn.disabled = true;
    sellBtn.disabled = true;
    msgEl.innerHTML = "";

    try {
        await api.executeTrade({
            symbol,
            market: "JP",
            side,
            quantity,
            price,
        });
        const action = side === "BUY" ? "買い" : "売り";
        msgEl.innerHTML = `<div class="message message-success">${action} ${quantity}株 x ${symbol} @ ${formatNumber(price, 1)}</div>`;
        await Promise.all([loadAccount(), loadStats(), loadHistory()]);
    } catch (e) {
        msgEl.innerHTML = `<div class="message message-error">${e.message}</div>`;
    } finally {
        buyBtn.disabled = false;
        sellBtn.disabled = false;
    }
}

async function loadAccount() {
    const el = document.getElementById("account-card");
    try {
        const info = await api.getAccount();
        el.innerHTML = `
            <div class="card-title">口座情報</div>
            <div style="display: flex; justify-content: space-between; margin-bottom: 0.5rem;">
                <span class="text-muted">現金残高</span>
                <span>${formatNumber(info.cash_balance)}</span>
            </div>
            <div style="display: flex; justify-content: space-between; margin-bottom: 0.5rem;">
                <span class="text-muted">ポートフォリオ</span>
                <span>${formatNumber(info.portfolio_value)}</span>
            </div>
            <div style="display: flex; justify-content: space-between; border-top: 1px solid var(--border); padding-top: 0.5rem;">
                <span>合計</span>
                <span class="card-value" style="font-size: 1.2rem;">${formatNumber(info.total_value)}</span>
            </div>
        `;
    } catch (e) {
        el.innerHTML = `<div class="card-title">口座情報</div><div class="text-muted">${e.message}</div>`;
    }
}

async function loadStats() {
    try {
        const stats = await api.getTradeStats();
        const pnlEl = document.getElementById("stat-pnl");
        pnlEl.innerHTML = colorBySign(
            stats.total_realized_pnl,
            formatNumber(stats.total_realized_pnl)
        );
        document.getElementById("stat-winrate").textContent =
            stats.win_count + stats.lose_count > 0
                ? `${(stats.win_rate * 100).toFixed(1)}%`
                : "-";
        document.getElementById("stat-trades").textContent = stats.total_trades;
    } catch (e) {
        // ignore
    }
}

async function loadHistory() {
    const el = document.getElementById("trade-history");
    try {
        const trades = await api.listTrades();
        if (trades.length === 0) {
            el.innerHTML = `<div class="empty-state">取引履歴はまだありません。</div>`;
            return;
        }

        renderTable(el, {
            columns: [
                {
                    key: "executed_at",
                    label: "日付",
                    render: (r) => r.executed_at.slice(0, 10),
                },
                {
                    key: "symbol",
                    label: "銘柄",
                    render: (r) =>
                        `<a href="#/stock/${r.market}/${r.symbol}" class="stock-link">${r.symbol}</a>`,
                },
                {
                    key: "side",
                    label: "売買",
                    render: (r) =>
                        `<span class="${r.side === "BUY" ? "text-green" : "text-red"}">${r.side === "BUY" ? "買い" : "売り"}</span>`,
                },
                { key: "quantity", label: "数量", align: "right" },
                {
                    key: "price",
                    label: "価格",
                    align: "right",
                    render: (r) => formatNumber(r.price, 1),
                },
                {
                    key: "total",
                    label: "合計",
                    align: "right",
                    render: (r) => formatNumber(r.price * r.quantity),
                },
            ],
            rows: trades,
        });
    } catch (e) {
        el.innerHTML = `<div class="message message-error">${e.message}</div>`;
    }
}
