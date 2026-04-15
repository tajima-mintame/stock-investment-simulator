import { api } from "../api.js";
import { renderTable, formatNumber, formatPercent, colorBySign } from "../components/table.js";

export async function renderScreening(container) {
    container.innerHTML = `
        <h2 style="margin-bottom: 1rem;">スクリーニング</h2>

        <div class="card mb-1">
            <div class="card-title">フィルタ条件</div>
            <div class="sync-form">
                <label>
                    セクター
                    <input id="scr-sector" placeholder="輸送用機器..." size="12">
                </label>
                <label>
                    出来高（下限）
                    <input id="scr-min-vol" type="number" placeholder="100000" size="8">
                </label>
                <label>
                    出来高（上限）
                    <input id="scr-max-vol" type="number" placeholder="" size="8">
                </label>
                <label>
                    並び順
                    <select id="scr-sort">
                        <option value="volume">出来高</option>
                        <option value="volatility">ボラティリティ</option>
                        <option value="change_pct">変動率</option>
                    </select>
                </label>
                <button id="scr-btn" class="btn-primary">検索</button>
            </div>
        </div>

        <div class="card">
            <div class="card-title">検索結果</div>
            <div id="scr-results">
                <div class="empty-state">条件を設定して検索ボタンを押してください。</div>
            </div>
        </div>
    `;

    document.getElementById("scr-btn").addEventListener("click", handleSearch);
}

async function handleSearch() {
    const btn = document.getElementById("scr-btn");
    const resultsEl = document.getElementById("scr-results");

    const params = {};
    params.market = "JP";

    const sector = document.getElementById("scr-sector").value.trim();
    if (sector) params.sector = sector;

    const minVol = document.getElementById("scr-min-vol").value;
    if (minVol) params.min_volume = minVol;

    const maxVol = document.getElementById("scr-max-vol").value;
    if (maxVol) params.max_volume = maxVol;

    params.sort_by = document.getElementById("scr-sort").value;

    btn.disabled = true;
    btn.textContent = "検索中...";

    try {
        const results = await api.screening(params);

        if (results.length === 0) {
            resultsEl.innerHTML = `<div class="empty-state">条件に一致する銘柄がありません。</div>`;
            return;
        }

        renderTable(resultsEl, {
            columns: [
                {
                    key: "symbol",
                    label: "コード",
                    render: (r) =>
                        `<a href="#/stock/${r.market}/${r.symbol}" class="stock-link">${r.symbol}</a>`,
                },
                { key: "name", label: "銘柄名" },
                { key: "sector", label: "セクター" },
                {
                    key: "close",
                    label: "終値",
                    align: "right",
                    render: (r) => formatNumber(r.close, 1),
                },
                {
                    key: "avg_volume",
                    label: "平均出来高",
                    align: "right",
                    render: (r) => formatNumber(r.avg_volume),
                },
                {
                    key: "volatility",
                    label: "ボラティリティ",
                    align: "right",
                    render: (r) => (r.volatility * 100).toFixed(2) + "%",
                },
                {
                    key: "change_pct",
                    label: "変動率",
                    align: "right",
                    render: (r) => colorBySign(r.change_pct, formatPercent(r.change_pct)),
                },
            ],
            rows: results,
            onRowClick: (r) => {
                location.hash = `#/stock/${r.market}/${r.symbol}`;
            },
        });
    } catch (e) {
        resultsEl.innerHTML = `<div class="message message-error">${e.message}</div>`;
    } finally {
        btn.disabled = false;
        btn.textContent = "検索";
    }
}
