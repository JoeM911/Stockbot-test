import { useEffect, useRef } from 'react';
import { createChart, CrosshairMode } from 'lightweight-charts';

const TIMEFRAMES = ['1m', '5m', '15m', '30m', '1H', '4H', '1D', '1W'];

const CHART_OPTS = {
  layout: { background: { color: '#04060e' }, textColor: '#506080' },
  grid:   { vertLines: { color: '#0d1428' }, horzLines: { color: '#0d1428' } },
  crosshair: { mode: CrosshairMode.Normal },
  rightPriceScale: { borderColor: '#172038' },
  timeScale: { borderColor: '#172038', timeVisible: true, secondsVisible: false },
};

function fmt(n, d = 2) {
  return n != null ? Number(n).toFixed(d) : '--';
}

export default function Chart({ symbol, data, indicators, timeframe, onTimeframeChange, currentQuote }) {
  const mainRef    = useRef();
  const rsiRef     = useRef();
  const macdRef    = useRef();
  const chartObjs  = useRef({});

  // Build charts on mount
  useEffect(() => {
    if (!mainRef.current) return;

    // ---- Main chart ----
    const main = createChart(mainRef.current, {
      ...CHART_OPTS,
      width: mainRef.current.clientWidth,
      height: mainRef.current.clientHeight,
    });

    const candles = main.addCandlestickSeries({
      upColor: '#00e676', downColor: '#ff1744',
      borderVisible: false,
      wickUpColor: '#00e676', wickDownColor: '#ff1744',
    });

    const volume = main.addHistogramSeries({
      priceFormat: { type: 'volume' },
      priceScaleId: 'vol',
    });
    main.priceScale('vol').applyOptions({ scaleMargins: { top: 0.84, bottom: 0 } });

    const ema9Line  = main.addLineSeries({ color: '#ff9800', lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
    const ema21Line = main.addLineSeries({ color: '#00bcd4', lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
    const ema50Line = main.addLineSeries({ color: '#9c27b0', lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
    const bbUpper   = main.addLineSeries({ color: '#5c6bc030', lineWidth: 1, priceLineVisible: false, lastValueVisible: false, lineStyle: 2 });
    const bbLower   = main.addLineSeries({ color: '#5c6bc030', lineWidth: 1, priceLineVisible: false, lastValueVisible: false, lineStyle: 2 });
    const vwapLine  = main.addLineSeries({ color: '#ffeb3b60', lineWidth: 1, priceLineVisible: false, lastValueVisible: false, lineStyle: 2 });

    // ---- RSI pane ----
    const rsiChart = createChart(rsiRef.current, {
      ...CHART_OPTS,
      width: rsiRef.current.clientWidth,
      height: rsiRef.current.clientHeight,
      timeScale: { ...CHART_OPTS.timeScale, visible: false },
    });
    const rsiLine    = rsiChart.addLineSeries({ color: '#e040fb', lineWidth: 1, priceLineVisible: false });
    const rsiOB      = rsiChart.addLineSeries({ color: '#ff174440', lineWidth: 1, lineStyle: 2, priceLineVisible: false });
    const rsiOS      = rsiChart.addLineSeries({ color: '#00e67640', lineWidth: 1, lineStyle: 2, priceLineVisible: false });

    // ---- MACD pane ----
    const macdChart  = createChart(macdRef.current, {
      ...CHART_OPTS,
      width: macdRef.current.clientWidth,
      height: macdRef.current.clientHeight,
      timeScale: { ...CHART_OPTS.timeScale, visible: false },
    });
    const macdLine   = macdChart.addLineSeries({ color: '#00bcd4', lineWidth: 1, priceLineVisible: false });
    const signalLine = macdChart.addLineSeries({ color: '#ff9800', lineWidth: 1, priceLineVisible: false });
    const histSeries = macdChart.addHistogramSeries({ priceLineVisible: false });

    chartObjs.current = { main, candles, volume, ema9Line, ema21Line, ema50Line, bbUpper, bbLower, vwapLine, rsiChart, rsiLine, rsiOB, rsiOS, macdChart, macdLine, signalLine, histSeries };

    // Sync time scales between panes
    main.timeScale().subscribeVisibleLogicalRangeChange((range) => {
      if (range) {
        rsiChart.timeScale().setVisibleLogicalRange(range);
        macdChart.timeScale().setVisibleLogicalRange(range);
      }
    });

    // Resize observer
    const ro = new ResizeObserver(() => {
      if (mainRef.current)  main.applyOptions({ width: mainRef.current.clientWidth });
      if (rsiRef.current)   rsiChart.applyOptions({ width: rsiRef.current.clientWidth });
      if (macdRef.current)  macdChart.applyOptions({ width: macdRef.current.clientWidth });
    });
    if (mainRef.current)  ro.observe(mainRef.current);

    return () => {
      ro.disconnect();
      main.remove();
      rsiChart.remove();
      macdChart.remove();
    };
  }, []);

  // Update data
  useEffect(() => {
    const { candles, volume, ema9Line, ema21Line, ema50Line, bbUpper, bbLower, vwapLine, rsiLine, rsiOB, rsiOS, macdLine, signalLine, histSeries } = chartObjs.current;
    if (!candles || !data.length) return;

    candles.setData(data);
    volume.setData(
      data.map(b => ({
        time: b.time,
        value: b.volume,
        color: b.close >= b.open ? '#00e67625' : '#ff174425',
      }))
    );

    const set = (series, arr) => { if (series && arr?.length) series.setData(arr); };

    set(ema9Line,  indicators.ema9);
    set(ema21Line, indicators.ema21);
    set(ema50Line, indicators.ema50);
    set(bbUpper,   indicators.bb_upper);
    set(bbLower,   indicators.bb_lower);
    set(vwapLine,  indicators.vwap);
    set(rsiLine,   indicators.rsi);

    if (indicators.rsi?.length) {
      const refData = indicators.rsi;
      rsiOB.setData(refData.map(d => ({ time: d.time, value: 70 })));
      rsiOS.setData(refData.map(d => ({ time: d.time, value: 30 })));
    }

    set(macdLine,   indicators.macd);
    set(signalLine, indicators.macd_signal);

    if (indicators.macd_hist?.length) {
      histSeries.setData(
        indicators.macd_hist.map(d => ({
          time: d.time,
          value: d.value,
          color: d.value >= 0 ? '#00e67640' : '#ff174440',
        }))
      );
    }

    chartObjs.current.main?.timeScale().fitContent();
  }, [data, indicators]);

  const cur = indicators?.current || {};
  const price = currentQuote?.price;
  const prevClose = data.length >= 2 ? data[data.length - 2]?.close : null;
  const priceChange = price && prevClose ? price - prevClose : null;
  const priceChangePct = priceChange && prevClose ? (priceChange / prevClose) * 100 : null;

  return (
    <div className="chart-panel">
      {/* Top bar */}
      <div className="chart-top-bar">
        <span className="chart-symbol">{symbol}</span>
        {price != null && (
          <>
            <span className="chart-price">${fmt(price)}</span>
            {priceChange != null && (
              <span className={`chart-change ${priceChange >= 0 ? 'green' : 'red'}`}>
                {priceChange >= 0 ? '+' : ''}{fmt(priceChange)} ({priceChange >= 0 ? '+' : ''}{fmt(priceChangePct)}%)
              </span>
            )}
          </>
        )}

        <div className="tf-group" style={{ marginLeft: 'auto' }}>
          {TIMEFRAMES.map(tf => (
            <button
              key={tf}
              className={`tf-btn ${timeframe === tf ? 'active' : ''}`}
              onClick={() => onTimeframeChange(tf)}
            >
              {tf}
            </button>
          ))}
        </div>
      </div>

      {/* Indicator badges */}
      <div className="indicator-bar">
        <span className="dim" style={{ fontSize: 8, alignSelf: 'center' }}>INDICATORS</span>
        {cur.rsi != null && (
          <span className={`ind-badge ${cur.rsi > 70 ? 'bear' : cur.rsi < 30 ? 'bull' : 'neu'}`}>
            RSI {cur.rsi}
          </span>
        )}
        {cur.macd != null && (
          <span className={`ind-badge ${cur.macd >= 0 ? 'bull' : 'bear'}`}>
            MACD {cur.macd >= 0 ? '+' : ''}{cur.macd}
          </span>
        )}
        {cur.ema9 != null && cur.ema21 != null && (
          <span className={`ind-badge ${cur.ema9 >= cur.ema21 ? 'bull' : 'bear'}`}>
            EMA {cur.ema9 >= cur.ema21 ? '9>21 BULL' : '9<21 BEAR'}
          </span>
        )}
        {cur.atr != null && (
          <span className="ind-badge gold">ATR {cur.atr}</span>
        )}
        {cur.vwap != null && (
          <span className="ind-badge neu">VWAP ${fmt(cur.vwap)}</span>
        )}
        {cur.bb_upper && cur.bb_lower && (
          <span className="ind-badge neu">BB ${fmt(cur.bb_lower)}–${fmt(cur.bb_upper)}</span>
        )}
        <span className="dim" style={{ marginLeft: 'auto', fontSize: 8, alignSelf: 'center' }}>
          <span style={{ color: '#ff9800' }}>— EMA9</span>&nbsp;
          <span style={{ color: '#00bcd4' }}>— EMA21</span>&nbsp;
          <span style={{ color: '#9c27b0' }}>— EMA50</span>&nbsp;
          <span style={{ color: '#ffeb3b' }}>— VWAP</span>
        </span>
      </div>

      {/* Main chart */}
      <div className="chart-main">
        <div ref={mainRef} className="chart-container" />
      </div>

      {/* RSI sub-pane */}
      <div className="sub-pane" style={{ height: 70 }}>
        <span className="sub-pane-label">RSI(14)</span>
        <div ref={rsiRef} style={{ width: '100%', height: '100%' }} />
      </div>

      {/* MACD sub-pane */}
      <div className="sub-pane" style={{ height: 70 }}>
        <span className="sub-pane-label">MACD(12,26,9)</span>
        <div ref={macdRef} style={{ width: '100%', height: '100%' }} />
      </div>
    </div>
  );
}
