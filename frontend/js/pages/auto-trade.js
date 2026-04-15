import { api } from "../api.js";
import { formatNumber, colorBySign, formatPercent } from "../components/table.js";

export async function renderAutoTrade(container) {
    container.innerHTML = `
        <h2 style="margin-bottom: 1rem;">自動売買</h2>

        <div class="card mb-1">
            <div class="card-title">セットアップ</div>
            <p style="font-size:0.85rem; color:var(--text-muted); margin-bottom:0.75rem;">
                東証上場銘柄から出来高上位を自動選定し、直近90日分の株価データを同期します。
            </p>
            <div class="sync-form">
                <label>
                    登録銘柄数
                    <input id="auto-count" type="number" value="20" min="5" max="50" size="4">
                </label>
                <button id="setup-btn" class="btn-primary">銘柄を自動登録</button>
            </div>
            <div id="setup-message" style="margin-top:0.5rem;"></div>
        </div>

        <div class="card mb-1">
            <div class="card-title">戦略実行</div>
            <p style="font-size:0.85rem; color:var(--text-muted); margin-bottom:0.75rem;">
                MA(5/25)のゴールデンクロス/デッドクロスとRSIフィルタで自動売買を実行します。
            </p>
            <div style="display:flex; gap:0.5rem;">
                <button id="run-btn" class="btn-primary">自動売買を実行</button>
            </div>
            <div id="run-message" style="margin-top:0.5rem;"></div>
            <div id="run-details" style="margin-top:0.5rem;"></div>
        </div>

        <div class="card mb-1" id="summary-card" style="display:none;">
            <div class="card-title">全体サマリー</div>
            <div id="summary-content"></div>
        </div>

        <div class="card">
            <div class="card-title">銘柄別結果</div>
            <div id="results-table">
                <div class="empty-state">セットアップと戦略実行を行ってください。</div>
            </div>
        </div>
    `;

    document.getElementById("setup-btn").addEventListener("click", handleSetup);
    document.getElementById("run-btn").addEventListener("click", handleRun);

    await loadResults();
}

async function handleSetup() {
    const btn = document.getElementById("setup-btn");
    const msgEl = document.getElementById("setup-message");
    const count = parseInt(document.getElementById("auto-count").value, 10) || 20;

    btn.disabled = true;
    btn.textContent = "登録中...（数分かかります）";
    msgEl.innerHTML = "";

    try {
        const result = await api.autoTradeSetup(count);
        msgEl.innerHTML = `<div class="message message-success">
            ${result.registered}銘柄を登録しました（エラー: ${result.errors}件）
        </div>`;
    } catch (e) {
        msgEl.innerHTML = `<div class="message message-error">${e.message}</div>`;
    } finally {
        btn.disabled = false;
        btn.textContent = "銘柄を自動登録";
    }
}

async function handleRun() {
    const btn = document.getElementById("run-btn");
    const msgEl = document.getElementById("run-message");
    const detailsEl = document.getElementById("run-details");

    btn.disabled = true;
    btn.textContent = "実行中...";
    msgEl.innerHTML = "";
    detailsEl.innerHTML = "";

    try {
        const result = await api.autoTradeRun();
        msgEl.innerHTML = `<div class="message message-success">
            実行完了 — 買い: ${result.buys}件, 売り: ${result.sells}件, スキップ: ${result.skipped}件
        </div>`;

        // 判断詳細を表示
        if (result.details && result.details.length > 0) {
            let html = '<table style="font-size:0.8rem; margin-top:0.5rem;">';
            html += "<tr><th>銘柄</th><th>判断</th><th>理由</th><th>価格</th><th>MA5</th><th>MA25</th><th>RSI</th></tr>";
            for (const d of result.details) {
                const actionColor = d.action === "BUY" ? "text-green" : d.action === "SELL" ? "text-red" : "text-muted";
                const actionLabel = {BUY: "買い", SELL: "売り", HOLD: "様子見", SKIP: "スキップ", ERROR: "エラー"}[d.action] || d.action;
                html += `<tr>
                    <td><a href="#/stock/JP/${d.symbol}" class="stock-link">${d.symbol}</a></td>
                    <td class="${actionColor}">${actionLabel}</td>
                    <td class="text-muted">${d.reason || ""}</td>
                    <td style="text-align:right;">${d.price ? formatNumber(d.price, 1) : "-"}</td>
                    <td style="text-align:right;">${d.ma5 || "-"}</td>
                    <td style="text-align:right;">${d.ma25 || "-"}</td>
                    <td style="text-align:right;">${d.rsi || "-"}</td>
                </tr>`;
            }
            html += "</table>";
            detailsEl.innerHTML = html;
        }

        await loadResults();
    } catch (e) {
        msgEl.innerHTML = `<div class="message message-error">${e.message}</div>`;
    } finally {
        btn.disabled = false;
        btn.textContent = "自動売買を実行";
    }
}

async function loadResults() {
    const summaryCard = document.getElementById("summary-card");
    const summaryEl = document.getElementById("summary-content");
    const tableEl = document.getElementById("results-table");

    try {
        const data = await api.autoTradeResults();

        if (!data.results || data.results.length === 0) {
            summaryCard.style.display = "none";
            tableEl.innerHTML = `<div class="empty-state">まだ取引がありません。セットアップと戦略実行を行ってください。</div>`;
            return;
        }

        // サマリー
        const s = data.summary;
        summaryCard.style.display = "block";
        summaryEl.innerHTML = `
            <div class="grid grid-3" style="gap:0.5rem;">
                <div>
                    <div class="card-title">総損益</div>
                    <div class="card-value">${colorBySign(s.total_pnl, formatNumber(s.total_pnl))}</div>
                </div>
                <div>
                    <div class="card-title">勝率</div>
                    <div class="card-value">${s.win_count + s.lose_count > 0 ? (s.win_rate * 100).toFixed(1) + "%" : "-"}</div>
                </div>
                <div>
                    <div class="card-title">勝敗</div>
                    <div class="card-value">
                        <span class="text-green">${s.win_count}勝</span> /
                        <span class="text-red">${s.lose_count}敗</span>
                    </div>
                </div>
            </div>
        `;

        // 結果テーブル
        let html = '<table style="font-size:0.85rem;">';
        html += "<tr><th>銘柄</th><th style='text-align:right;'>買い回数</th><th style='text-align:right;'>売り回数</th><th style='text-align:right;'>実現損益</th><th>結果</th></tr>";
        for (const r of data.results) {
            const statusCls = r.status === "利益" ? "text-green" : r.status === "損失" ? "text-red" : "text-muted";
            html += `<tr>
                <td><a href="#/stock/JP/${r.symbol}" class="stock-link">${r.symbol}</a></td>
                <td style="text-align:right;">${r.buy_count}</td>
                <td style="text-align:right;">${r.sell_count}</td>
                <td style="text-align:right;">${colorBySign(r.realized_pnl, formatNumber(r.realized_pnl))}</td>
                <td class="${statusCls}">${r.status}</td>
            </tr>`;
        }
        html += "</table>";
        tableEl.innerHTML = html;
    } catch (e) {
        tableEl.innerHTML = `<div class="message message-error">${e.message}</div>`;
    }
}
