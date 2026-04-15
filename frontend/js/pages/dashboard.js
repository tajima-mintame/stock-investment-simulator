import { api } from "../api.js";
import { renderTable, formatNumber, colorBySign } from "../components/table.js";

export async function renderDashboard(container) {
    container.innerHTML = `
        <h2 style="margin-bottom: 1rem;">ダッシュボード</h2>

        <div class="grid grid-3 mb-1" id="account-summary">
            <div class="card">
                <div class="card-title">現金残高</div>
                <div class="card-value" id="dash-cash">-</div>
            </div>
            <div class="card">
                <div class="card-title">ポートフォリオ時価</div>
                <div class="card-value" id="dash-portfolio">-</div>
            </div>
            <div class="card">
                <div class="card-title">合計</div>
                <div class="card-value" id="dash-total">-</div>
            </div>
        </div>

        <div class="card mb-1">
            <div class="card-title" style="display:flex; justify-content:space-between; align-items:center;">
                <span>自動取引</span>
                <button id="auto-toggle" class="btn-sell" style="font-size:0.8rem; padding:0.3rem 1rem;">OFF</button>
            </div>
            <div id="auto-message" style="font-size:0.85rem; color:var(--text-muted); margin-top:0.5rem;"></div>
        </div>

        <div class="card mb-1">
            <div class="card-title" style="display:flex; justify-content:space-between; align-items:center;">
                <span>高評価銘柄ランキング</span>
                <div style="display:flex; gap:0.25rem;" id="ranking-tabs">
                    <button class="btn-primary ranking-tab active" data-sort="score" style="font-size:0.75rem; padding:0.25rem 0.5rem;">総合</button>
                    <button class="ranking-tab" data-sort="fund_score" style="font-size:0.75rem; padding:0.25rem 0.5rem; background:var(--bg-input); color:var(--text); border:none; border-radius:var(--radius); cursor:pointer;">ファンダ</button>
                    <button class="ranking-tab" data-sort="tech_score" style="font-size:0.75rem; padding:0.25rem 0.5rem; background:var(--bg-input); color:var(--text); border:none; border-radius:var(--radius); cursor:pointer;">テクニカル</button>
                </div>
            </div>
            <div id="ranking-table">
                <div class="empty-state" style="font-size:0.85rem;">銘柄が登録されていません。自動売買画面からセットアップしてください。</div>
            </div>
        </div>

        <div class="card mb-1">
            <div class="card-title">データ同期</div>
            <div class="sync-form">
                <input type="hidden" id="sync-market" value="JP">
                <label>
                    銘柄コード
                    <input id="sync-symbol" placeholder="7203, 9984..." size="10">
                </label>
                <label>
                    開始日
                    <input id="sync-from" type="date" value="2024-01-01">
                </label>
                <label>
                    終了日
                    <input id="sync-to" type="date">
                </label>
                <button id="sync-btn" class="btn-primary">同期</button>
            </div>
            <div id="sync-message"></div>
        </div>

        <div class="card mb-1">
            <div class="card-title" style="display:flex; justify-content:space-between; align-items:center;">
                <span>収集ステータス</span>
                <button id="collect-btn" class="btn-primary" style="font-size:0.75rem; padding:0.3rem 0.6rem;">今すぐ収集</button>
            </div>
            <div id="collection-status"></div>
        </div>

        <div class="card">
            <div class="card-title">登録銘柄</div>
            <div id="stock-list"></div>
        </div>
    `;

    const toInput = document.getElementById("sync-to");
    toInput.value = new Date().toISOString().slice(0, 10);

    document.getElementById("sync-btn").addEventListener("click", handleSync);
    document.getElementById("collect-btn").addEventListener("click", handleCollect);
    document.getElementById("auto-toggle").addEventListener("click", handleAutoToggle);

    // ランキングタブ
    document.querySelectorAll(".ranking-tab").forEach((tab) => {
        tab.addEventListener("click", (e) => {
            document.querySelectorAll(".ranking-tab").forEach((t) => {
                t.classList.remove("active", "btn-primary");
                t.style.background = "var(--bg-input)";
                t.style.color = "var(--text)";
            });
            e.target.classList.add("active", "btn-primary");
            e.target.style.background = "";
            e.target.style.color = "";
            loadRankings(e.target.dataset.sort);
        });
    });

    await Promise.all([loadAccountSummary(), loadRankings("score"), loadStockList(), loadCollectionStatus()]);
}

// === 自動取引トグル ===

let autoEnabled = false;

async function handleAutoToggle() {
    const btn = document.getElementById("auto-toggle");
    const msgEl = document.getElementById("auto-message");
    const newState = !autoEnabled;

    btn.disabled = true;
    btn.textContent = "処理中...";
    msgEl.innerHTML = "";

    try {
        const result = await api.autoTradeToggle(newState);
        autoEnabled = newState;
        updateToggleButton();
        msgEl.innerHTML = result.message;

        if (result.need_setup) {
            msgEl.innerHTML += ` <a href="#/auto-trade" class="stock-link">セットアップへ</a>`;
        }

        await Promise.all([loadAccountSummary(), loadRankings("score")]);
    } catch (e) {
        msgEl.innerHTML = `<span class="text-red">${e.message}</span>`;
    } finally {
        btn.disabled = false;
        updateToggleButton();
    }
}

function updateToggleButton() {
    const btn = document.getElementById("auto-toggle");
    if (autoEnabled) {
        btn.textContent = "ON";
        btn.className = "btn-buy";
        btn.style.fontSize = "0.8rem";
        btn.style.padding = "0.3rem 1rem";
    } else {
        btn.textContent = "OFF";
        btn.className = "btn-sell";
        btn.style.fontSize = "0.8rem";
        btn.style.padding = "0.3rem 1rem";
    }
}

// === ランキング ===

async function loadRankings(sortBy) {
    const el = document.getElementById("ranking-table");
    try {
        const rankings = await api.autoTradeRankings(sortBy, 10);

        if (rankings.length === 0) {
            el.innerHTML = `<div class="empty-state" style="font-size:0.85rem;">銘柄が登録されていません。自動売買画面からセットアップしてください。</div>`;
            return;
        }

        renderTable(el, {
            columns: [
                {
                    key: "symbol",
                    label: "コード",
                    render: (r) => `<a href="#/stock/JP/${r.symbol}" class="stock-link">${r.symbol}</a>`,
                },
                { key: "name", label: "銘柄名" },
                {
                    key: "score",
                    label: "総合",
                    align: "right",
                    render: (r) => r.score != null ? colorBySign(r.score, r.score.toFixed(0)) : "-",
                },
                {
                    key: "tech_score",
                    label: "テクニカル",
                    align: "right",
                    render: (r) => r.tech_score != null ? colorBySign(r.tech_score, r.tech_score.toFixed(0)) : "-",
                },
                {
                    key: "fund_score",
                    label: "ファンダ",
                    align: "right",
                    render: (r) => r.fund_score != null ? colorBySign(r.fund_score, r.fund_score.toFixed(0)) : "-",
                },
                {
                    key: "price",
                    label: "株価",
                    align: "right",
                    render: (r) => r.price ? formatNumber(r.price, 1) : "-",
                },
                {
                    key: "action",
                    label: "判断",
                    render: (r) => {
                        const cls = r.action === "BUY" ? "text-green" : r.action === "SELL" ? "text-red" : "text-muted";
                        const label = {BUY: "買い", SELL: "売り", HOLD: "様子見", SKIP: "-"}[r.action] || r.action;
                        return `<span class="${cls}">${label}</span>`;
                    },
                },
            ],
            rows: rankings,
            onRowClick: (r) => { location.hash = `#/stock/JP/${r.symbol}`; },
        });
    } catch (e) {
        el.innerHTML = `<div class="text-muted" style="font-size:0.85rem;">ランキングを読み込めませんでした</div>`;
    }
}

// === 既存機能 ===

async function handleSync() {
    const btn = document.getElementById("sync-btn");
    const msgEl = document.getElementById("sync-message");
    const market = document.getElementById("sync-market").value;
    const symbol = document.getElementById("sync-symbol").value.trim();
    const from = document.getElementById("sync-from").value;
    const to = document.getElementById("sync-to").value;

    if (!symbol) {
        msgEl.innerHTML = `<div class="message message-error">銘柄コードを入力してください</div>`;
        return;
    }

    btn.disabled = true;
    btn.textContent = "同期中...";
    msgEl.innerHTML = "";

    try {
        const result = await api.syncStock(symbol, market, from || null, to || null);
        msgEl.innerHTML = `<div class="message message-success">${result.message}</div>`;
        await loadStockList();
    } catch (e) {
        msgEl.innerHTML = `<div class="message message-error">${e.message}</div>`;
    } finally {
        btn.disabled = false;
        btn.textContent = "同期";
    }
}

async function handleCollect() {
    const btn = document.getElementById("collect-btn");
    btn.disabled = true;
    btn.textContent = "収集中...";
    try {
        const result = await api.runCollection();
        await loadCollectionStatus();
        const msg = `収集: ${result.collected}件, エラー: ${result.errors}件`;
        document.getElementById("sync-message").innerHTML =
            `<div class="message ${result.errors ? "message-error" : "message-success"}">${msg}</div>`;
    } catch (e) {
        document.getElementById("sync-message").innerHTML =
            `<div class="message message-error">${e.message}</div>`;
    } finally {
        btn.disabled = false;
        btn.textContent = "今すぐ収集";
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
            el.innerHTML = `<div class="text-muted" style="font-size:0.85rem;">収集ログはまだありません。</div>`;
            return;
        }
        let html = '<table style="font-size:0.85rem;">';
        html += "<tr><th>日時</th><th>銘柄</th><th>結果</th><th>詳細</th></tr>";
        for (const log of logs) {
            const statusCls = log.status === "OK" ? "text-green" : "text-red";
            html += `<tr>
                <td>${log.fetched_at.slice(0, 16).replace("T", " ")}</td>
                <td>${log.symbol || "全銘柄"}</td>
                <td class="${statusCls}">${log.status === "OK" ? "成功" : "失敗"}</td>
                <td class="text-muted">${log.message || ""}</td>
            </tr>`;
        }
        html += "</table>";
        el.innerHTML = html;
    } catch (e) {
        el.innerHTML = `<div class="text-muted">ステータスの読み込みに失敗しました</div>`;
    }
}

async function loadStockList() {
    const listEl = document.getElementById("stock-list");
    try {
        const data = await api.listStocks();
        if (data.stocks.length === 0) {
            listEl.innerHTML = `<div class="empty-state">銘柄が登録されていません。上のフォームから銘柄を同期してください。</div>`;
            return;
        }

        renderTable(listEl, {
            columns: [
                {
                    key: "symbol",
                    label: "コード",
                    render: (row) =>
                        `<a href="#/stock/${row.market}/${row.symbol}" class="stock-link">${row.symbol}</a>`,
                },
                { key: "name", label: "銘柄名" },
                { key: "sector", label: "セクター" },
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
