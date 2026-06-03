import { useEffect, useRef, useState, useCallback } from 'react';
import { createChart } from 'lightweight-charts';

const PERIODS = ['1D', '1W', '1M', '3M'];

const CHART_OPTS = {
  layout: { background: { color: '#080c18' }, textColor: '#506080' },
  grid:   { vertLines: { color: '#0d1428' }, horzLines: { color: '#0d1428' } },
  rightPriceScale: { borderColor: '#172038' },
  timeScale: { borderColor: '#172038', timeVisible: true, secondsVisible: false },
  handleScroll: false,
  handleScale:  false,
};

function fmt(n) {
  if (n == null) return '--';
  return '$' + Number(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export default function GrowthChart() {
  const containerRef = useRef();
  const chartRef     = useRef();
  const seriesRef    = useRef();
  const [period, setPeriod]   = useState('1M');
  const [stats, setStats]     = useState(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async (p) => {
    setLoading(true);
    try {
      const res = await fetch(`/api/portfolio/history?period=${p}`);
      const data = await res.json();
      if (!Array.isArray(data) || data.length < 2) return;

      // Update chart
      if (seriesRef.current) {
        seriesRef.current.setData(data);
        chartRef.current?.timeScale().fitContent();
      }

      // Compute stats
      const first = data[0].value;
      const last  = data[data.length - 1].value;
      const change    = last - first;
      const changePct = (change / first) * 100;
      setStats({ current: last, change, changePct });
    } catch (e) {
      console.error('GrowthChart load error', e);
    }
    setLoading(false);
  }, []);

  // Create chart once
  useEffect(() => {
    if (!containerRef.current) return;
    const chart = createChart(containerRef.current, {
      ...CHART_OPTS,
      width:  containerRef.current.clientWidth,
      height: containerRef.current.clientHeight,
    });
    chartRef.current = chart;

    const series = chart.addAreaSeries({
      lineColor:    '#00e676',
      topColor:     '#00e67630',
      bottomColor:  '#00e67602',
      lineWidth:    2,
      priceFormat:  { type: 'price', precision: 2, minMove: 0.01 },
    });
    seriesRef.current = series;

    const ro = new ResizeObserver(() => {
      if (containerRef.current) {
        chart.applyOptions({
          width:  containerRef.current.clientWidth,
          height: containerRef.current.clientHeight,
        });
      }
    });
    ro.observe(containerRef.current);

    return () => { ro.disconnect(); chart.remove(); };
  }, []);

  // Load data when period changes
  useEffect(() => { load(period); }, [period, load]);

  const up = stats && stats.change >= 0;

  return (
    <div className="panel growth-panel">
      <div className="panel-header">
        <span>PORTFOLIO GROWTH</span>
        <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
          {loading && <span className="dim" style={{ fontSize: 8 }}>loading…</span>}
          <div className="tf-group">
            {PERIODS.map(p => (
              <button
                key={p}
                className={`tf-btn ${period === p ? 'active' : ''}`}
                onClick={() => setPeriod(p)}
              >{p}</button>
            ))}
          </div>
        </div>
      </div>

      {stats && (
        <div className="growth-stats">
          <span className="growth-equity">{fmt(stats.current)}</span>
          <span className={up ? 'green' : 'red'} style={{ fontSize: 11, fontWeight: 700 }}>
            {up ? '+' : ''}{fmt(stats.change)}
          </span>
          <span className={up ? 'green' : 'red'} style={{ fontSize: 10 }}>
            ({up ? '+' : ''}{stats.changePct.toFixed(2)}%)
          </span>
        </div>
      )}

      <div ref={containerRef} className="growth-chart-container" />
    </div>
  );
}
