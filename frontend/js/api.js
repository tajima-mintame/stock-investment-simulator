// Backend API client

const BASE = "/api";

async function request(path, options = {}) {
    const resp = await fetch(`${BASE}${path}`, {
        headers: { "Content-Type": "application/json", ...options.headers },
        ...options,
    });
    if (!resp.ok) {
        const body = await resp.json().catch(() => ({}));
        throw new Error(body.detail || `HTTP ${resp.status}`);
    }
    return resp.json();
}

export const api = {
    // Stocks
    listStocks(params = {}) {
        const qs = new URLSearchParams(params).toString();
        return request(`/stocks${qs ? "?" + qs : ""}`);
    },

    searchStocks(q, market = "US") {
        return request(`/stocks/search?q=${encodeURIComponent(q)}&market=${market}`);
    },

    getStockDetail(market, symbol) {
        return request(`/stocks/${market}/${symbol}`);
    },

    getPrices(market, symbol, from, to) {
        const params = new URLSearchParams();
        if (from) params.set("from", from);
        if (to) params.set("to", to);
        const qs = params.toString();
        return request(`/stocks/${market}/${symbol}/prices${qs ? "?" + qs : ""}`);
    },

    getIndicators(market, symbol, types = "ma,rsi,macd,bb", period = 20) {
        return request(
            `/stocks/${market}/${symbol}/indicators?type=${types}&period=${period}`
        );
    },

    syncStock(symbol, market, fromDate, toDate) {
        return request("/stocks/sync", {
            method: "POST",
            body: JSON.stringify({
                symbol,
                market,
                from_date: fromDate || null,
                to_date: toDate || null,
            }),
        });
    },

    // Account
    getAccount() {
        return request("/account");
    },

    // Trades
    executeTrade(trade) {
        return request("/trades", {
            method: "POST",
            body: JSON.stringify(trade),
        });
    },

    listTrades(params = {}) {
        const qs = new URLSearchParams(params).toString();
        return request(`/trades${qs ? "?" + qs : ""}`);
    },

    getTradeStats() {
        return request("/trades/stats");
    },

    // Portfolio
    getPortfolio() {
        return request("/portfolio");
    },

    getAllocation() {
        return request("/portfolio/allocation");
    },

    getCorrelation() {
        return request("/portfolio/correlation");
    },

    // Screening
    screening(params = {}) {
        const qs = new URLSearchParams(params).toString();
        return request(`/screening${qs ? "?" + qs : ""}`);
    },

    // Auto Trade
    autoTradeSetup(count = 20) {
        return request(`/auto-trade/setup?count=${count}`, { method: "POST" });
    },

    autoTradeRun() {
        return request("/auto-trade/run", { method: "POST" });
    },

    autoTradeStart(count = 20) {
        return request(`/auto-trade/start?count=${count}`, { method: "POST" });
    },

    autoTradeResults() {
        return request("/auto-trade/results");
    },

    // Collection
    getCollectionStatus(limit = 10) {
        return request(`/collection/status?limit=${limit}`);
    },

    runCollection() {
        return request("/collection/run", { method: "POST" });
    },

    toggleWatch(market, symbol) {
        return request(`/collection/watch/${market}/${symbol}`, { method: "POST" });
    },

    // Health
    health() {
        return request("/health");
    },
};
