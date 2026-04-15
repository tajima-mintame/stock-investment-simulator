// Sortable table component

export function renderTable(container, { columns, rows, onRowClick }) {
    const table = document.createElement("table");
    const thead = document.createElement("thead");
    const headerRow = document.createElement("tr");

    columns.forEach((col) => {
        const th = document.createElement("th");
        th.textContent = col.label;
        if (col.align === "right") th.style.textAlign = "right";
        headerRow.appendChild(th);
    });
    thead.appendChild(headerRow);
    table.appendChild(thead);

    const tbody = document.createElement("tbody");
    rows.forEach((row) => {
        const tr = document.createElement("tr");
        if (onRowClick) {
            tr.style.cursor = "pointer";
            tr.addEventListener("click", () => onRowClick(row));
        }
        columns.forEach((col) => {
            const td = document.createElement("td");
            if (col.render) {
                const content = col.render(row);
                if (typeof content === "string") {
                    td.innerHTML = content;
                } else if (content instanceof HTMLElement) {
                    td.appendChild(content);
                }
            } else {
                td.textContent = row[col.key] ?? "-";
            }
            if (col.align === "right") td.style.textAlign = "right";
            tr.appendChild(td);
        });
        tbody.appendChild(tr);
    });
    table.appendChild(tbody);

    container.innerHTML = "";
    container.appendChild(table);
}

export function formatNumber(n, decimals = 0) {
    if (n == null) return "-";
    return Number(n).toLocaleString("ja-JP", {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
    });
}

export function formatPercent(n) {
    if (n == null) return "-";
    const sign = n >= 0 ? "+" : "";
    return `${sign}${(n * 100).toFixed(2)}%`;
}

export function colorBySign(value, text) {
    if (value == null) return `<span class="text-muted">${text || "-"}</span>`;
    const cls = value >= 0 ? "text-green" : "text-red";
    return `<span class="${cls}">${text}</span>`;
}
