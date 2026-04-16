import { api } from "../api.js";
import { formatNumber, colorBySign, formatPercent } from "../components/table.js";

export async function renderAutoTrade(container) {
    container.innerHTML = `
        <h2 style="margin-bottom: 1rem;">自動売買</h2>

        <div class="grid grid-2 mb-1">
            <div class="card">
                <div class="card-title">運用開始</div>
                <p style="font-size:0.85rem; color:var(--text-muted); margin-bottom:0.75rem;">
                    東証上場銘柄を自動選定し、テクニカル+ファンダメンタル統合スコアで売買を実行します。
                </p>
                <div class="sync-form">
                    <label>
                        銘柄数
                        <input id="auto-count" type="number" value="20" min="5" max="50" size="4">
                    </label>
                    <button id="start-btn" class="btn-primary">ワンクリック運用開始</button>
                </div>
                <div style="margin-top:0.5rem; display:flex; gap:0.5rem;">
                    <button id="run-btn" class="btn-primary" style="font-size:0.8rem; padding:0.3rem 0.6rem;">戦略のみ再実行</button>
                </div>
                <div id="action-message" style="margin-top:0.5rem;"></div>
            </div>
            <div class="card" id="summary-card">
                <div class="card-title">運用状況</div>
                <div id="summary-content">
                    <div class="text-muted" style="font-size:0.85rem;">まだ運用を開始していません。</div>
                </div>
            </div>
        </div>

        <div class="card mb-1">
            <div class="card-title">資産推移</div>
            <div class="chart-container" id="asset-chart" style="height:250px;"></div>
        </div>

        <div class="card mb-1" id="details-card" style="display:none;">
            <div class="card-title">戦略判断の詳細</div>
            <div id="run-details"></div>
        </div>

        <div class="card">
            <div class="card-title">銘柄別損益</div>
            <div id="results-table">
                <div class="empty-state">運用を開始すると結果が表示されます。</div>
            </div>
        </div>
    `;

    document.getElementById("start-btn").addEventListener("click", handleStart);
    document.getElementById("run-btn").addEventListener("click", handleRun);

    await loadResults();
}

async function handleStart() {
    const btn = document.getElementById("start-btn");
    const msgEl = document.getElementById("action-message");
    const count = parseInt(document.getElementById("auto-count").value, 10) || 20;

    btn.disabled = true;
    btn.textContent = "運用開始中...（銘柄登録に数分かかります）";
    msgEl.innerHTML = "";

    try {
        const result = await api.autoTradeStart(count);
        const s = result.setup || {};
        const r = result.run || {};
        if (s.message && s.errors > 0) {
            msgEl.innerHTML = `<div class="message message-error">${s.message}</div>`;
        } else {
            msgEl.innerHTML = `<div class="message message-success">
                ${s.registered || 0}銘柄登録 → 買い${r.buys || 0}件 / 売り${r.sells || 0}件 / 様子見${r.skipped || 0}件
            </div>`;
        }
        if (r.details) showDetails(r.details);
        await loadResults();
    } catch (e) {
        msgEl.innerHTML = `<div class="message message-error">${e.message}</div>`;
    } finally {
        btn.disabled = false;
        btn.textContent = "ワンクリック運用開始";
    }
}

async function handleRun() {
    const btn = document.getElementById("run-btn");
    const msgEl = document.getElementById("action-message");

    btn.disabled = true;
    btn.textContent = "実行中...";
    msgEl.innerHTML = "";

    try {
        const result = await api.autoTradeRun();
        msgEl.innerHTML = `<div class="message message-success">
            買い${result.buys}件 / 売り${result.sells}件 / 様子見${result.skipped}件
        </div>`;
        showDetails(result.details);
        await loadResults();
    } catch (e) {
        msgEl.innerHTML = `<div class="message message-error">${e.message}</div>`;
    } finally {
        btn.disabled = false;
        btn.textContent = "戦略のみ再実行";
    }
}

function showDetails(details) {
    const card = document.getElementById("details-card");
    const el = document.getElementById("run-details");
    if (!details || details.length === 0) {
        card.style.display = "none";
        return;
    }
    card.style.display = "block";

    let html = '<table style="font-size:0.8rem;">';
    html += "<tr><th>銘柄</th><th>判断</th><th>理由</th><th style='text-align:right;'>価格</th><th style='text-align:right;'>テクニカル</th><th style='text-align:right;'>ファンダ</th><th style='text-align:right;'>統合</th></tr>";
    for (const d of details) {
        const actionColor = d.action === "BUY" ? "text-green" : d.action === "SELL" ? "text-red" : "text-muted";
        const actionLabel = {BUY: "買い", SELL: "売り", HOLD: "様子見", SKIP: "スキップ", ERROR: "エラー"}[d.action] || d.action;
        html += `<tr>
            <td><a href="#/stock/JP/${d.symbol}" class="stock-link">${d.symbol}</a></td>
            <td class="${actionColor}">${actionLabel}</td>
            <td class="text-muted" style="max-width:200px;">${d.reason || ""}</td>
            <td style="text-align:right;">${d.price ? formatNumber(d.price, 1) : "-"}</td>
            <td style="text-align:right;">${d.tech_score != null ? colorBySign(d.tech_score, d.tech_score) : "-"}</td>
            <td style="text-align:right;">${d.fund_score != null ? colorBySign(d.fund_score, d.fund_score) : "-"}</td>
            <td style="text-align:right; font-weight:600;">${d.score != null ? colorBySign(d.score, d.score) : "-"}</td>
        </tr>`;
    }
    html += "</table>";
    el.innerHTML = html;
}

async function loadResults() {
    const summaryEl = document.getElementById("summary-content");
    const tableEl = document.getElementById("results-table");
    const chartEl = document.getElementById("asset-chart");

    try {
        const data = await api.autoTradeResults();

        // サマリー
        const s = data.summary;
        if (s.total_stocks === 0) {
            summaryEl.innerHTML = `<div class="text-muted" style="font-size:0.85rem;">まだ運用を開始していません。</div>`;
        } else {
            const returnColor = s.return_pct >= 0 ? "text-green" : "text-red";
            summaryEl.innerHTML = `
                <div style="display:flex; flex-direction:column; gap:0.5rem;">
                    <div style="display:flex; justify-content:space-between;">
                        <span class="text-muted">現在の総資産</span>
                        <span class="card-value" style="font-size:1.3rem;">${formatNumber(s.current_total)}</span>
                    </div>
                    <div style="display:flex; justify-content:space-between;">
                        <span class="text-muted">初期資金</span>
                        <span>${formatNumber(s.initial_balance)}</span>
                    </div>
                    <div style="display:flex; justify-content:space-between;">
                        <span class="text-muted">リターン</span>
                        <span class="${returnColor}" style="font-weight:600;">${formatPercent(s.return_pct)}</span>
                    </div>
                    <div style="display:flex; justify-content:space-between;">
                        <span class="text-muted">勝敗</span>
                        <span><span class="text-green">${s.win_count}勝</span> / <span class="text-red">${s.lose_count}敗</span>
                            ${s.win_count + s.lose_count > 0 ? `（勝率${(s.win_rate * 100).toFixed(0)}%）` : ""}</span>
                    </div>
                    <div style="display:flex; justify-content:space-between;">
                        <span class="text-muted">実現損益</span>
                        <span>${colorBySign(s.total_pnl, formatNumber(s.total_pnl))}</span>
                    </div>
                </div>
            `;
        }

        // 資産推移チャート
        if (data.snapshots && data.snapshots.length > 0) {
            renderAssetChart(chartEl, data.snapshots, s.initial_balance);
        } else {
            chartEl.innerHTML = `<div class="empty-state" style="padding:2rem;">運用開始後に資産推移が表示されます。</div>`;
        }

        // 銘柄別結果
        if (!data.results || data.results.length === 0) {
            tableEl.innerHTML = `<div class="empty-state">取引データがありません。</div>`;
            return;
        }

        let html = '<table style="font-size:0.85rem;">';
        html += "<tr><th>銘柄</th><th style='text-align:right;'>買い</th><th style='text-align:right;'>売り</th><th style='text-align:right;'>実現損益</th><th>結果</th></tr>";
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

function renderAssetChart(container, snapshots, initialBalance) {
    container.innerHTML = "";

    const chart = LightweightCharts.createChart(container, {
        width: container.clientWidth,
        height: 250,
        layout: { background: { color: "#1a1d29" }, textColor: "#8b8fa3" },
        grid: { vertLines: { color: "#2a2d3a" }, horzLines: { color: "#2a2d3a" } },
        rightPriceScale: { borderColor: "#2a2d3a" },
        timeScale: { borderColor: "#2a2d3a" },
    });

    // 初期残高ライン
    const baselineSeries = chart.addLineSeries({
        color: "rgba(139,143,163,0.3)",
        lineWidth: 1,
        lineStyle: 2,
        priceLineVisible: false,
        lastValueVisible: false,
    });

    // 資産推移ライン
    const assetSeries = chart.addLineSeries({
        color: "#4a9eff",
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: true,
    });

    const data = snapshots.map((s) => ({
        time: s.timestamp.slice(0, 10),
        value: s.total,
    }));

    // 重複日付を除去（同じ日に複数スナップショットがある場合、最後のものを使う）
    const uniqueData = {};
    for (const d of data) {
        uniqueData[d.time] = d.value;
    }
    const chartData = Object.entries(uniqueData)
        .map(([time, value]) => ({ time, value }))
        .sort((a, b) => a.time.localeCompare(b.time));

    assetSeries.setData(chartData);

    // ベースライン
    if (chartData.length > 0) {
        baselineSeries.setData(
            chartData.map((d) => ({ time: d.time, value: initialBalance }))
        );
    }

    chart.timeScale().fitContent();

    const observer = new ResizeObserver(() => {
        chart.applyOptions({ width: container.clientWidth });
    });
    observer.observe(container);
}
