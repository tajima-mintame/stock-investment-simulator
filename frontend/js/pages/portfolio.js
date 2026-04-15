import { api } from "../api.js";
import { renderTable, formatNumber, colorBySign } from "../components/table.js";

export async function renderPortfolio(container) {
    container.innerHTML = `
        <h2 style="margin-bottom: 1rem;">ポートフォリオ</h2>

        <div class="card mb-1">
            <div class="card-title">保有銘柄</div>
            <div id="port-holdings">
                <div class="loading">読み込み中...</div>
            </div>
        </div>

        <div class="grid grid-2 mb-1">
            <div class="card">
                <div class="card-title">セクター配分</div>
                <div id="port-sector"></div>
            </div>
            <div class="card">
                <div class="card-title">市場配分</div>
                <div id="port-market"></div>
            </div>
        </div>

        <div class="card">
            <div class="card-title">相関行列</div>
            <div id="port-correlation"></div>
        </div>
    `;

    await Promise.all([loadHoldings(), loadAllocation(), loadCorrelation()]);
}

async function loadHoldings() {
    const el = document.getElementById("port-holdings");
    try {
        const data = await api.getPortfolio();

        if (data.holdings.length === 0) {
            el.innerHTML = `<div class="empty-state">保有銘柄がありません。取引画面から購入してください。</div>`;
            return;
        }

        renderTable(el, {
            columns: [
                {
                    key: "symbol",
                    label: "コード",
                    render: (r) =>
                        `<a href="#/stock/${r.market}/${r.symbol}" class="stock-link">${r.symbol}</a>`,
                },
                { key: "name", label: "銘柄名" },
                { key: "quantity", label: "数量", align: "right" },
                {
                    key: "avg_cost",
                    label: "平均取得単価",
                    align: "right",
                    render: (r) => formatNumber(r.avg_cost, 1),
                },
                {
                    key: "current_price",
                    label: "現在価格",
                    align: "right",
                    render: (r) => r.current_price != null ? formatNumber(r.current_price, 1) : "-",
                },
                {
                    key: "unrealized_pnl",
                    label: "含み損益",
                    align: "right",
                    render: (r) =>
                        r.unrealized_pnl != null
                            ? colorBySign(r.unrealized_pnl, formatNumber(r.unrealized_pnl))
                            : "-",
                },
            ],
            rows: data.holdings,
        });

        const totalEl = document.createElement("div");
        totalEl.style.cssText = "text-align:right; padding:0.5rem 0.75rem; font-weight:600;";
        totalEl.innerHTML = `含み損益合計: ${colorBySign(
            data.total_unrealized_pnl,
            formatNumber(data.total_unrealized_pnl)
        )}`;
        el.appendChild(totalEl);
    } catch (e) {
        el.innerHTML = `<div class="message message-error">${e.message}</div>`;
    }
}

async function loadAllocation() {
    const sectorEl = document.getElementById("port-sector");
    const marketEl = document.getElementById("port-market");
    try {
        const data = await api.getAllocation();
        renderAllocationBars(sectorEl, data.by_sector);
        renderAllocationBars(marketEl, data.by_market);
    } catch (e) {
        sectorEl.innerHTML = `<div class="text-muted">データなし</div>`;
        marketEl.innerHTML = `<div class="text-muted">データなし</div>`;
    }
}

function renderAllocationBars(container, items) {
    if (!items || items.length === 0) {
        container.innerHTML = `<div class="empty-state">保有銘柄なし</div>`;
        return;
    }

    const colors = ["#4a9eff", "#22c55e", "#f59e0b", "#a855f7", "#ef4444", "#8b8fa3"];
    let html = "";
    items.forEach((item, i) => {
        const color = colors[i % colors.length];
        const pct = (item.percentage * 100).toFixed(1);
        html += `
            <div style="margin-bottom:0.5rem;">
                <div style="display:flex; justify-content:space-between; font-size:0.8rem; margin-bottom:0.2rem;">
                    <span>${item.label}</span>
                    <span>${formatNumber(item.value)} (${pct}%)</span>
                </div>
                <div style="background:var(--bg-input); border-radius:4px; height:8px; overflow:hidden;">
                    <div style="background:${color}; height:100%; width:${pct}%; border-radius:4px;"></div>
                </div>
            </div>
        `;
    });
    container.innerHTML = html;
}

async function loadCorrelation() {
    const el = document.getElementById("port-correlation");
    try {
        const data = await api.getCorrelation();

        if (!data.matrix || data.matrix.length === 0) {
            el.innerHTML = `<div class="empty-state">相関分析には2銘柄以上の保有が必要です。</div>`;
            return;
        }

        let html = '<table style="text-align:center;">';
        html += "<tr><th></th>";
        data.symbols.forEach((s) => {
            html += `<th style="padding:0.4rem;">${s}</th>`;
        });
        html += "</tr>";

        data.matrix.forEach((row, i) => {
            html += `<tr><th style="padding:0.4rem;">${data.symbols[i]}</th>`;
            row.forEach((val) => {
                if (val === null) {
                    html += '<td style="padding:0.4rem;">-</td>';
                } else {
                    const bg = correlationColor(val);
                    html += `<td style="padding:0.4rem; background:${bg}; border-radius:4px;">${val.toFixed(2)}</td>`;
                }
            });
            html += "</tr>";
        });

        html += "</table>";
        el.innerHTML = html;
    } catch (e) {
        el.innerHTML = `<div class="text-muted">データなし</div>`;
    }
}

function correlationColor(val) {
    if (val >= 0) {
        const intensity = Math.min(val, 1) * 0.4;
        return `rgba(34, 197, 94, ${intensity})`;
    } else {
        const intensity = Math.min(-val, 1) * 0.4;
        return `rgba(239, 68, 68, ${intensity})`;
    }
}
