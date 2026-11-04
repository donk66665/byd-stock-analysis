/* ==========================================================================
   比亚迪股价分析看板 — 交互与图表
   依赖：Vue 3（全局 Vue）、TDesign（全局 TDesign）、ECharts（全局 echarts）
   ========================================================================== */
(function () {
  'use strict';

  var D = window.__DATA__;
  if (!D) {
    document.body.innerHTML = '<p style="padding:40px;font-family:sans-serif">数据未加载：请确认 web/data.js 存在。</p>';
    return;
  }

  /* ---------------- 通用格式化 ---------------- */
  var nf0 = new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 0 });
  var nf2 = new Intl.NumberFormat('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  function fmt(v) { return v == null ? '—' : nf2.format(v); }
  function fmtInt(v) { return v == null ? '—' : nf0.format(Math.round(v)); }
  function pct(v) {
    if (v == null) return '—';
    return (v > 0 ? '+' : '') + Number(v).toFixed(2) + '%';
  }
  function tone(v) { return v > 0 ? 'up' : (v < 0 ? 'down' : ''); }

  /* ---------------- ECharts 公共样式 ---------------- */
  var C = {
    ink: '#14171C', ink2: '#4A5058', ink3: '#858C96',
    line: '#E3E6EB', grid: '#EEF1F4',
    brand: '#8C2F39', blue: '#1F4E79', orange: '#E08A3C', slate: '#8794A8',
    up: '#D9342B', down: '#10995A'
  };

  var TOOLTIP = {
    backgroundColor: 'rgba(255,255,255,.97)',
    borderColor: C.line,
    borderWidth: 1,
    padding: [10, 13],
    textStyle: { color: C.ink, fontSize: 12, fontFamily: 'inherit' },
    extraCssText: 'box-shadow:0 6px 24px rgba(20,23,28,.10);border-radius:8px;'
  };

  function axisCat(dates, showLabel, formatter) {
    return {
      type: 'category',
      data: dates,
      boundaryGap: false,
      axisLine: { lineStyle: { color: C.line } },
      axisTick: { show: false },
      axisLabel: showLabel
        ? { color: C.ink3, fontSize: 11, formatter: formatter || function (v) { return v.slice(5); } }
        : { show: false },
      splitLine: { show: false }
    };
  }

  function axisVal(extra) {
    return Object.assign({
      type: 'value',
      scale: true,
      splitLine: { lineStyle: { color: C.grid, type: 'dashed' } },
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: C.ink3, fontSize: 11 }
    }, extra || {});
  }

  function areaGrad(rgb) {
    return new echarts.graphic.LinearGradient(0, 0, 0, 1, [
      { offset: 0, color: 'rgba(' + rgb + ',.15)' },
      { offset: 1, color: 'rgba(' + rgb + ',0)' }
    ]);
  }

  /* ---------------- 折线图构造 ---------------- */
  function lineOption(s) {
    return {
      animationDuration: 700,
      animationEasing: 'cubicOut',
      grid: { left: 4, right: 20, top: 38, bottom: 6, containLabel: true },
      tooltip: Object.assign({}, TOOLTIP, {
        trigger: 'axis',
        axisPointer: { type: 'line', lineStyle: { color: '#C9CFD6', type: 'dashed' } },
        valueFormatter: function (v) { return v == null ? '—' : nf2.format(v) + ' 元'; }
      }),
      legend: {
        right: 0, top: 0, itemWidth: 16, itemHeight: 3, itemGap: 16,
        textStyle: { color: C.ink2, fontSize: 12 }
      },
      xAxis: axisCat(s.dates, true),
      yAxis: axisVal(),
      series: [
        {
          name: '收盘价', type: 'line', data: s.close, showSymbol: false,
          lineStyle: { width: 1.7, color: C.blue },
          areaStyle: { color: areaGrad('31,78,121') },
          emphasis: { focus: 'series' }
        },
        {
          name: 'MA20', type: 'line', data: s.ma20, showSymbol: false, smooth: true,
          lineStyle: { width: 1.2, color: C.orange }, emphasis: { focus: 'series' }
        },
        {
          name: 'MA60', type: 'line', data: s.ma60, showSymbol: false, smooth: true,
          lineStyle: { width: 1.2, color: C.slate }, emphasis: { focus: 'series' }
        }
      ]
    };
  }

  /* ---------------- K 线图构造 ---------------- */
  function klineOption(k) {
    var vol = k.vol.map(function (v, i) {
      var rising = k.chg[i] >= 0;
      return {
        value: v,
        itemStyle: { color: rising ? 'rgba(217,52,43,.55)' : 'rgba(16,153,90,.55)' }
      };
    });

    return {
      animation: false,
      axisPointer: { link: [{ xAxisIndex: 'all' }] },
      grid: [
        { left: 4, right: 20, top: 34, height: '56%', containLabel: true },
        { left: 4, right: 20, top: '74%', height: '14%', containLabel: true }
      ],
      tooltip: Object.assign({}, TOOLTIP, {
        trigger: 'axis',
        axisPointer: { type: 'cross', crossStyle: { color: '#B9C0C8' } },
        formatter: function (ps) {
          var out = '<div style="font-weight:600;margin-bottom:6px">' + ps[0].axisValue + '</div>';
          ps.forEach(function (p) {
            if (p.seriesType === 'candlestick') {
              var d = p.data;
              out += '<div style="display:flex;justify-content:space-between;gap:18px"><span>开/收</span><b>' +
                nf2.format(d[1]) + ' / ' + nf2.format(d[2]) + '</b></div>';
              out += '<div style="display:flex;justify-content:space-between;gap:18px"><span>低/高</span><b>' +
                nf2.format(d[3]) + ' / ' + nf2.format(d[4]) + '</b></div>';
            } else if (p.seriesType === 'bar') {
              out += '<div style="display:flex;justify-content:space-between;gap:18px"><span>成交量</span><b>' +
                nf0.format(p.data.value || p.data) + ' 手</b></div>';
            } else if (p.value != null) {
              out += '<div style="display:flex;justify-content:space-between;gap:18px"><span>' +
                p.seriesName + '</span><b>' + nf2.format(p.value) + '</b></div>';
            }
          });
          return out;
        }
      }),
      xAxis: [
        Object.assign(axisCat(k.dates, false), { boundaryGap: true }),
        Object.assign(axisCat(k.dates, true), { boundaryGap: true, gridIndex: 1 })
      ],
      yAxis: [
        axisVal(),
        {
          gridIndex: 1, scale: true, splitNumber: 2,
          axisLine: { show: false }, axisTick: { show: false },
          axisLabel: { show: false }, splitLine: { show: false }
        }
      ],
      dataZoom: [
        { type: 'inside', xAxisIndex: [0, 1], start: 0, end: 100 },
        {
          type: 'slider', xAxisIndex: [0, 1], start: 0, end: 100,
          bottom: 4, height: 16, borderColor: 'transparent',
          backgroundColor: '#F5F6F8', fillerColor: 'rgba(140,47,57,.10)',
          handleStyle: { color: '#fff', borderColor: '#C9CFD6' },
          moveHandleStyle: { color: '#DDE2E8' },
          dataBackground: { lineStyle: { color: '#C9CFD6' }, areaStyle: { color: '#EDF0F3' } },
          selectedDataBackground: { lineStyle: { color: C.brand }, areaStyle: { color: 'rgba(140,47,57,.10)' } },
          textStyle: { color: C.ink3, fontSize: 10 }
        }
      ],
      series: [
        {
          name: 'K线', type: 'candlestick', data: k.ohlc,
          itemStyle: {
            color: C.up, color0: C.down,
            borderColor: C.up, borderColor0: C.down, borderWidth: 1
          },
          markPoint: {
            symbol: 'pin', symbolSize: 44,
            label: { fontSize: 10, color: '#fff', formatter: function (p) { return nf0.format(p.value); } },
            data: [
              {
                name: '区间高', coord: [k.high.date, k.high.value], value: k.high.value,
                itemStyle: { color: C.up }
              },
              {
                name: '区间低', coord: [k.low.date, k.low.value], value: k.low.value,
                itemStyle: { color: C.down }
              }
            ]
          }
        },
        { name: 'MA5', type: 'line', data: k.ma5, showSymbol: false, smooth: true, lineStyle: { width: 1, color: C.orange } },
        { name: 'MA10', type: 'line', data: k.ma10, showSymbol: false, smooth: true, lineStyle: { width: 1, color: '#7B8FA8' } },
        { name: 'MA20', type: 'line', data: k.ma20, showSymbol: false, smooth: true, lineStyle: { width: 1, color: C.brand } },
        { name: '成交量', type: 'bar', xAxisIndex: 1, yAxisIndex: 1, data: vol, barWidth: '62%' }
      ]
    };
  }

  /* ---------------- 热力图构造 ---------------- */
  function corrOption(corr) {
    var labels = corr.labels, m = corr.matrix, data = [];
    for (var i = 0; i < labels.length; i++) {
      for (var j = 0; j < labels.length; j++) {
        data.push([j, i, m[i][j]]);
      }
    }
    return {
      animationDuration: 600,
      grid: { left: 78, right: 26, top: 18, bottom: 96 },
      tooltip: Object.assign({}, TOOLTIP, {
        formatter: function (p) {
          return '<b>' + labels[p.value[1]] + ' × ' + labels[p.value[0]] + '</b><br/>' +
            'Pearson r = ' + Number(p.value[2]).toFixed(4);
        }
      }),
      xAxis: {
        type: 'category', data: labels, position: 'top',
        axisLine: { show: false }, axisTick: { show: false },
        splitArea: { show: false },
        axisLabel: { color: C.ink2, fontSize: 11, interval: 0, rotate: 0 }
      },
      yAxis: {
        type: 'category', data: labels, inverse: true,
        axisLine: { show: false }, axisTick: { show: false },
        splitArea: { show: false },
        axisLabel: { color: C.ink2, fontSize: 11, interval: 0 }
      },
      visualMap: {
        min: -0.2, max: 1, calculable: false, orient: 'horizontal',
        left: 'center', bottom: 6, itemWidth: 12, itemHeight: 150,
        precision: 2,
        text: ['强正相关 1.0', '-0.2 负相关'],
        textStyle: { color: C.ink3, fontSize: 11 },
        inRange: { color: ['#4A7BD0', '#B9CBE6', '#F7F9FB', '#E4C6C9', '#C0717A'] }
      },
      series: [{
        type: 'heatmap', data: data,
        label: {
          show: true, fontSize: 10.5, color: '#2A2E35',
          formatter: function (p) { return Number(p.value[2]).toFixed(2); }
        },
        itemStyle: { borderColor: '#fff', borderWidth: 2, borderRadius: 3 },
        emphasis: {
          itemStyle: { shadowBlur: 8, shadowColor: 'rgba(20,23,28,.18)' }
        }
      }]
    };
  }

  /* ---------------- 描述性统计表行构造 ----------------
     成交量、成交额原始量级达 6~11 位，直接进表格会把列撑破并折行，
     故换算为「万手」「亿元」并在表头标注单位（数值仍保持等价）。 */
  var STAT_UNIT = {
    '成交量': { label: '成交量（万手）', div: 1e4 },
    '成交额': { label: '成交额（亿元）', div: 1e8 }
  };

  function buildStatRows(src) {
    return Object.keys(src).map(function (name) {
      var o = src[name];
      var u = STAT_UNIT[name];
      var div = u ? u.div : 1;
      var f = function (v) { return v == null ? '—' : fmt(v / div); };
      return {
        name: u ? u.label : name,
        mean: f(o.mean), std: f(o.std), min: f(o.min),
        q25: f(o.q25), median: f(o.median), q75: f(o.q75), max: f(o.max),
        skew: o.skew == null ? '—' : o.skew.toFixed(2),
        kurt: o.kurt == null ? '—' : o.kurt.toFixed(2)
      };
    });
  }

  /* ---------------- Vue 应用 ---------------- */
  var app = Vue.createApp({
    data: function () {
      return {
        meta: D.meta,
        kpi: D.kpi,
        kline: D.kline,
        tab: 'textbook',
        statScope: '2023',
        charts: {}
      };
    },

    computed: {
      /* 2023 年首末收盘，用于任务③的说明文案 */
      kpi_2023: function () {
        var a = this.annualMap['2023'];
        return a ? { start: a.start, end: a.end, chg: a.chg_pct } : { start: null, end: null, chg: null };
      },

      annualMap: function () {
        var out = {};
        D.annual.forEach(function (a) { out[String(a.year)] = a; });
        return out;
      },

      lastChg: function () {
        var c = D.series_full.close;
        if (c.length < 2) return null;
        return (c[c.length - 1] / c[c.length - 2] - 1) * 100;
      },

      kpis: function () {
        var k = D.kpi;
        return [
          {
            label: '最新收盘',
            value: fmt(k.last_close),
            unit: '元',
            tone: '',
            note: '前一交易日 ' + pct(this.lastChg)
          },
          {
            label: '区间累计涨跌',
            value: pct(k.total_return_pct),
            unit: '',
            tone: tone(k.total_return_pct),
            note: k.first_date + ' 起'
          },
          {
            label: '区间最高',
            value: fmt(k.high.value),
            unit: '元',
            tone: '',
            note: k.high.date
          },
          {
            label: '区间最低',
            value: fmt(k.low.value),
            unit: '元',
            tone: '',
            note: k.low.date
          },
          {
            label: '年化波动率',
            value: fmt(k.ann_vol_pct),
            unit: '%',
            tone: '',
            note: '日收益标准差 × √252'
          },
          {
            label: '最大回撤',
            value: pct(k.max_drawdown_pct),
            unit: '',
            tone: 'down',
            note: '峰谷回撤，未年化'
          }
        ];
      },

      /* --- 前 5 行表 --- */
      headColumns: function () {
        var cols = [{ colKey: '日期', title: '日期', width: 112, fixed: 'left' }];
        D.meta.columns.slice(1).forEach(function (name) {
          var isBig = name === '成交量' || name === '成交额';
          cols.push({
            colKey: name,
            title: name,
            width: isBig ? 152 : 88,
            align: 'right',
            cell: function (h, ctx) {
              var v = ctx.row[name];
              // 教材任务要求「输出前 5 行」，此处保留原始量纲不做换算
              if (name === '成交额') return nf2.format(v);
              if (name === '成交量') return fmtInt(v);
              return fmt(v);
            }
          });
        });
        return cols;
      },

      headRows: function () { return D.head; },

      /* --- 描述性统计表 --- */
      statColumns: function () {
        return [
          { colKey: 'name', title: '变量', width: 116, fixed: 'left' },
          { colKey: 'mean', title: '均值', align: 'right' },
          { colKey: 'std', title: '标准差', align: 'right' },
          { colKey: 'min', title: '最小值', align: 'right' },
          { colKey: 'q25', title: '25%', align: 'right' },
          { colKey: 'median', title: '中位数', align: 'right' },
          { colKey: 'q75', title: '75%', align: 'right' },
          { colKey: 'max', title: '最大值', align: 'right' },
          { colKey: 'skew', title: '偏度', align: 'right' },
          { colKey: 'kurt', title: '峰度', align: 'right' }
        ];
      },

      statRows: function () {
        return buildStatRows(this.statScope === '2023' ? D.describe_2023 : D.describe_full);
      },

      statRowsFull: function () {
        return buildStatRows(D.describe_full);
      },

      /* --- 年度表 --- */
      annualColumns: function () {
        return [
          { colKey: 'year', title: '年份', width: 78 },
          { colKey: 'trading_days', title: '交易日', align: 'right', width: 84 },
          { colKey: 'start', title: '年初收盘', align: 'right' },
          { colKey: 'end', title: '年末收盘', align: 'right' },
          {
            colKey: 'chg_pct', title: '年度涨跌', align: 'right',
            cell: function (h, ctx) {
              var v = ctx.row.chg_pct;
              return h ? h('span', { class: tone(v) }, pct(v)) : pct(v);
            }
          },
          { colKey: 'high', title: '年内最高', align: 'right' },
          { colKey: 'low', title: '年内最低', align: 'right' },
          {
            colKey: 'amp_pct', title: '高低振幅', align: 'right',
            cell: function (h, ctx) { return pct(ctx.row.amp_pct); }
          },
          {
            colKey: 'ann_vol_pct', title: '年化波动', align: 'right',
            cell: function (h, ctx) { return fmt(ctx.row.ann_vol_pct) + '%'; }
          }
        ];
      },

      annualRows: function () {
        return D.annual.map(function (a) {
          return {
            year: a.year,
            trading_days: a.trading_days,
            start: fmt(a.start), end: fmt(a.end),
            chg_pct: a.chg_pct, high: fmt(a.high), low: fmt(a.low),
            amp_pct: a.amp_pct, ann_vol_pct: a.ann_vol_pct
          };
        });
      }
    },

    methods: {
      fmt: fmt,
      fmtInt: fmtInt,
      pct: pct,

      initChart: function (id, option) {
        var el = document.getElementById(id);
        if (!el) return null;
        var inst = echarts.getInstanceByDom(el) || echarts.init(el, null, { renderer: 'canvas' });
        inst.setOption(option, true);
        this.charts[id] = inst;
        return inst;
      },

      renderAll: function () {
        this.initChart('close2023Chart', lineOption(D.series_2023));
        this.initChart('closeFullChart', lineOption(D.series_full));
        this.initChart('klineChart', klineOption(D.kline));
        this.initChart('corrChart', corrOption(D.corr));
      },

      resizeAll: function () {
        var self = this;
        Object.keys(this.charts).forEach(function (k) {
          self.charts[k].resize();
        });
      }
    },

    mounted: function () {
      var self = this;
      // 等 Tabs 完成首次布局后再初始化，避免隐藏面板拿到 0 宽高
      requestAnimationFrame(function () {
        self.renderAll();
        requestAnimationFrame(function () { self.resizeAll(); });
      });

      window.addEventListener('resize', function () { self.resizeAll(); });
    },

    watch: {
      tab: function () {
        var self = this;
        // 切换后等 DOM 显示再 resize，否则画布尺寸停留在隐藏时的 0
        requestAnimationFrame(function () {
          self.renderAll();
          self.resizeAll();
        });
      }
    }
  });

  var TD = window.TDesign && (window.TDesign.default || window.TDesign);
  if (TD) app.use(TD);
  app.mount('#app');
})();
