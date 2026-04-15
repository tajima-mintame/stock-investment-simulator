import { renderDashboard } from "./pages/dashboard.js";
import { renderStockDetail } from "./pages/stock-detail.js";
import { renderTrading } from "./pages/trading.js";
import { renderPortfolio } from "./pages/portfolio.js";
import { renderScreening } from "./pages/screening.js";
import { renderHelp } from "./pages/help.js";

const appEl = document.getElementById("app");

function updateActiveNav(page) {
    document.querySelectorAll(".nav-link").forEach((link) => {
        link.classList.toggle("active", link.dataset.page === page);
    });
}

async function route() {
    const hash = location.hash || "#/";
    appEl.innerHTML = `<div class="loading">読み込み中...</div>`;

    try {
        // #/stock/{market}/{symbol}
        const stockMatch = hash.match(/^#\/stock\/([A-Z]+)\/(.+)$/);
        if (stockMatch) {
            updateActiveNav("");
            await renderStockDetail(appEl, stockMatch[1], stockMatch[2]);
            return;
        }

        switch (hash) {
            case "#/":
            case "#/dashboard":
                updateActiveNav("dashboard");
                await renderDashboard(appEl);
                break;
            case "#/trading":
                updateActiveNav("trading");
                await renderTrading(appEl);
                break;
            case "#/portfolio":
                updateActiveNav("portfolio");
                await renderPortfolio(appEl);
                break;
            case "#/screening":
                updateActiveNav("screening");
                await renderScreening(appEl);
                break;
            case "#/help":
                updateActiveNav("help");
                await renderHelp(appEl);
                break;
            default:
                updateActiveNav("dashboard");
                await renderDashboard(appEl);
        }
    } catch (e) {
        appEl.innerHTML = `<div class="message message-error">Error: ${e.message}</div>`;
    }
}

window.addEventListener("hashchange", route);
route();
