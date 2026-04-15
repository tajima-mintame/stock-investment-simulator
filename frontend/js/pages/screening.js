import { api } from "../api.js";
import { renderTable, formatNumber, formatPercent, colorBySign } from "../components/table.js";

export async function renderScreening(container) {
    container.innerHTML = `
        <h2 style="margin-bottom: 1rem;">Screening</h2>

        <div class="card mb-1">
            <div class="card-title">Filter</div>
            <div class="sync-form">
                <label>
                    Sector
                    <input id="scr-sector" placeholder="輸送用機器..." size="12">
                </label>
                <label>
                    Min Volume
                    <input id="scr-min-vol" type="number" placeholder="100000" size="8">
                </label>
                <label>
                    Max Volume
                    <input id="scr-max-vol" type="number" placeholder="" size="8">
                </label>
                <label>
                    Sort by
                    <select id="scr-sort">
                        <option value="volume">Volume</option>
                        <option value="volatility">Volatility</option>
                        <option value="change_pct">Change %</option>
                    </select>
                </label>
                <button id="scr-btn" class="btn-primary">Search</button>
            </div>
        </div>

        <div class="card">
            <div class="card-title">Results</div>
            <div id="scr-results">
                <div class="empty-state">Set filters and click Search.</div>
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
    btn.textContent = "Searching...";

    try {
        const results = await api.screening(params);

        if (results.length === 0) {
            resultsEl.innerHTML = `<div class="empty-state">No stocks match the criteria.</div>`;
            return;
        }

        renderTable(resultsEl, {
            columns: [
                {
                    key: "symbol",
                    label: "Symbol",
                    render: (r) =>
                        `<a href="#/stock/${r.market}/${r.symbol}" class="stock-link">${r.symbol}</a>`,
                },
                { key: "name", label: "Name" },
                { key: "sector", label: "Sector" },
                {
                    key: "close",
                    label: "Close",
                    align: "right",
                    render: (r) => formatNumber(r.close, 1),
                },
                {
                    key: "avg_volume",
                    label: "Avg Volume",
                    align: "right",
                    render: (r) => formatNumber(r.avg_volume),
                },
                {
                    key: "volatility",
                    label: "Volatility",
                    align: "right",
                    render: (r) => (r.volatility * 100).toFixed(2) + "%",
                },
                {
                    key: "change_pct",
                    label: "Change",
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
        btn.textContent = "Search";
    }
}
