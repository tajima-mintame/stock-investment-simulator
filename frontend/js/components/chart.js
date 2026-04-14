// Lightweight Charts wrapper

export function createCandlestickChart(container, prices) {
    container.innerHTML = "";

    const chart = LightweightCharts.createChart(container, {
        width: container.clientWidth,
        height: container.clientHeight || 400,
        layout: {
            background: { color: "#1a1d29" },
            textColor: "#8b8fa3",
        },
        grid: {
            vertLines: { color: "#2a2d3a" },
            horzLines: { color: "#2a2d3a" },
        },
        crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
        timeScale: {
            borderColor: "#2a2d3a",
            timeVisible: false,
        },
        rightPriceScale: {
            borderColor: "#2a2d3a",
        },
    });

    // ローソク足
    const candleSeries = chart.addCandlestickSeries({
        upColor: "#22c55e",
        downColor: "#ef4444",
        borderUpColor: "#22c55e",
        borderDownColor: "#ef4444",
        wickUpColor: "#22c55e",
        wickDownColor: "#ef4444",
    });

    const candleData = prices.map((p) => ({
        time: p.date,
        open: p.open,
        high: p.high,
        low: p.low,
        close: p.close,
    }));
    candleSeries.setData(candleData);

    // 出来高
    const volumeSeries = chart.addHistogramSeries({
        color: "#4a9eff",
        priceFormat: { type: "volume" },
        priceScaleId: "volume",
    });
    chart.priceScale("volume").applyOptions({
        scaleMargins: { top: 0.8, bottom: 0 },
    });

    const volumeData = prices.map((p) => ({
        time: p.date,
        value: p.volume,
        color: p.close >= p.open ? "rgba(34,197,94,0.3)" : "rgba(239,68,68,0.3)",
    }));
    volumeSeries.setData(volumeData);

    chart.timeScale().fitContent();

    // リサイズ対応
    const observer = new ResizeObserver(() => {
        chart.applyOptions({ width: container.clientWidth });
    });
    observer.observe(container);

    return { chart, candleSeries, volumeSeries, observer };
}

const MA_COLORS = { "5": "#f59e0b", "25": "#3b82f6", "75": "#a855f7" };

export function addMAOverlay(chart, maData) {
    // maData: { "5": [{date, value}], "25": [...], "75": [...] }
    const series = {};
    for (const [period, values] of Object.entries(maData)) {
        const s = chart.addLineSeries({
            color: MA_COLORS[period] || "#888",
            lineWidth: 1,
            priceLineVisible: false,
            lastValueVisible: false,
        });
        s.setData(
            values.filter((v) => v.value != null).map((v) => ({ time: v.date, value: v.value }))
        );
        series[period] = s;
    }
    return series;
}

export function addBBOverlay(chart, bbData) {
    // bbData: [{date, upper, middle, lower}]
    const filtered = bbData.filter((v) => v.upper != null);

    const upper = chart.addLineSeries({
        color: "rgba(139,143,163,0.5)",
        lineWidth: 1,
        lineStyle: 2,
        priceLineVisible: false,
        lastValueVisible: false,
    });
    upper.setData(filtered.map((v) => ({ time: v.date, value: v.upper })));

    const middle = chart.addLineSeries({
        color: "rgba(139,143,163,0.8)",
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
    });
    middle.setData(filtered.map((v) => ({ time: v.date, value: v.middle })));

    const lower = chart.addLineSeries({
        color: "rgba(139,143,163,0.5)",
        lineWidth: 1,
        lineStyle: 2,
        priceLineVisible: false,
        lastValueVisible: false,
    });
    lower.setData(filtered.map((v) => ({ time: v.date, value: v.lower })));

    return { upper, middle, lower };
}

export function createRSIChart(container, rsiData) {
    container.innerHTML = "";

    const chart = LightweightCharts.createChart(container, {
        width: container.clientWidth,
        height: 150,
        layout: {
            background: { color: "#1a1d29" },
            textColor: "#8b8fa3",
        },
        grid: {
            vertLines: { color: "#2a2d3a" },
            horzLines: { color: "#2a2d3a" },
        },
        timeScale: { visible: false },
        rightPriceScale: { borderColor: "#2a2d3a" },
    });

    const series = chart.addLineSeries({
        color: "#f59e0b",
        lineWidth: 1.5,
        priceLineVisible: false,
        lastValueVisible: false,
    });

    series.setData(
        rsiData.filter((v) => v.value != null).map((v) => ({ time: v.date, value: v.value }))
    );

    // 70/30ライン
    chart.priceScale("right").applyOptions({ autoScale: false, scaleMargins: { top: 0.05, bottom: 0.05 } });

    chart.timeScale().fitContent();

    const observer = new ResizeObserver(() => {
        chart.applyOptions({ width: container.clientWidth });
    });
    observer.observe(container);

    return chart;
}

export function createMACDChart(container, macdData) {
    container.innerHTML = "";

    const chart = LightweightCharts.createChart(container, {
        width: container.clientWidth,
        height: 150,
        layout: {
            background: { color: "#1a1d29" },
            textColor: "#8b8fa3",
        },
        grid: {
            vertLines: { color: "#2a2d3a" },
            horzLines: { color: "#2a2d3a" },
        },
        timeScale: { visible: false },
        rightPriceScale: { borderColor: "#2a2d3a" },
    });

    const filtered = macdData.filter((v) => v.macd != null);

    // MACD line
    const macdSeries = chart.addLineSeries({
        color: "#3b82f6",
        lineWidth: 1.5,
        priceLineVisible: false,
        lastValueVisible: false,
    });
    macdSeries.setData(filtered.map((v) => ({ time: v.date, value: v.macd })));

    // Signal line
    const signalFiltered = macdData.filter((v) => v.signal != null);
    const signalSeries = chart.addLineSeries({
        color: "#f59e0b",
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
    });
    signalSeries.setData(signalFiltered.map((v) => ({ time: v.date, value: v.signal })));

    // Histogram
    const histFiltered = macdData.filter((v) => v.histogram != null);
    const histSeries = chart.addHistogramSeries({
        priceLineVisible: false,
        lastValueVisible: false,
    });
    histSeries.setData(
        histFiltered.map((v) => ({
            time: v.date,
            value: v.histogram,
            color: v.histogram >= 0 ? "rgba(34,197,94,0.5)" : "rgba(239,68,68,0.5)",
        }))
    );

    chart.timeScale().fitContent();

    const observer = new ResizeObserver(() => {
        chart.applyOptions({ width: container.clientWidth });
    });
    observer.observe(container);

    return chart;
}

export function createMiniChart(container, prices) {
    container.innerHTML = "";

    const chart = LightweightCharts.createChart(container, {
        width: container.clientWidth,
        height: 60,
        layout: {
            background: { color: "transparent" },
            textColor: "transparent",
        },
        grid: {
            vertLines: { visible: false },
            horzLines: { visible: false },
        },
        rightPriceScale: { visible: false },
        timeScale: { visible: false },
        crosshair: { mode: LightweightCharts.CrosshairMode.Hidden },
        handleScroll: false,
        handleScale: false,
    });

    const last = prices[prices.length - 1];
    const first = prices[0];
    const isUp = last && first && last.close >= first.close;

    const series = chart.addLineSeries({
        color: isUp ? "#22c55e" : "#ef4444",
        lineWidth: 1.5,
        priceLineVisible: false,
        lastValueVisible: false,
    });

    series.setData(
        prices.map((p) => ({ time: p.date, value: p.close }))
    );

    chart.timeScale().fitContent();
    return chart;
}
