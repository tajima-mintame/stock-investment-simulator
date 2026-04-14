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

    return { chart, candleSeries, volumeSeries };
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
