/* ==========================================================================
   比亚迪股票价格走势分析 · 交互层
   技术约束：无构建工具、无网络依赖；Vue 3 全局构建 + TDesign UMD + ECharts
   数据：window.BYD_DATA（由 scripts/analyze.py 生成）
   ========================================================================== */
(function () {
  'use strict';

  var D = window.BYD_DATA;
  var S = D.series;
  var SUM = D.summary;
  var UP = '#d5493f';       // A 股口径：红涨
  var DOWN = '#17935e';     // A 股口径：绿跌
  var INK = '#142033';
  var BRAND = '#4475a7';
  var GRID = '#eef1f5';
  var LABEL = '#8d96a3';
  var FONT = 'Inter, -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif';

  var app = Vue.createApp({
    setup: function () {
      var tab = Vue.ref('overview');
      var range = Vue.ref('all');
      var zoomOn = Vue.ref(false);
      var zoomCfg = Vue.ref({ title: '', desc: '' });

      /* ---------------------------------------------------------- 派生数据 */
      var phases = D.phases;
      var upPhases = phases.filter(function (p) { return p.return >= 0; }).length;
      var downPhases = phases.length - upPhases;

      var monthUp = D.monthly.filter(function (m) { return m.return >= 0; }).length;
      var monthDown = D.monthly.length - monthUp;
      var worstMonth = D.monthly.slice().sort(function (a, b) { return a.return - b.return; })[0];

      // 日收益偏度（三阶标准化矩）
      var skew = (function () {
        var a = S.pctChg, n = a.length;
        var m = a.reduce(function (x, y) { return x + y; }, 0) / n;
        var v = a.reduce(function (x, y) { return x + Math.pow(y - m, 2); }, 0) / n;
        var s = a.reduce(function (x, y) { return x + Math.pow(y - m, 3); }, 0) / n;
        return (s / Math.pow(v, 1.5)).toFixed(2);
      })();

      // 最长连续水下（回撤 < 0）交易日
      var waterDays = (function () {
        var best = 0, cur = 0;
        S.drawdown.forEach(function (v) {
          if (v < 0) { cur += 1; best = Math.max(best, cur); } else { cur = 0; }
        });
        return best;
      })();

      // 量价四象限
      var quadRaw = SUM.volumeQuadrant;
      var quadTotal = Object.keys(quadRaw).reduce(function (s, k) { return s + quadRaw[k]; }, 0);
      var quads = [
        { name: '放量上涨', value: quadRaw['放量上涨'], cls: 'is-up-strong' },
        { name: '缩量上涨', value: quadRaw['缩量上涨'], cls: 'is-up-weak' },
        { name: '放量下跌', value: quadRaw['放量下跌'], cls: 'is-down-strong' },
        { name: '缩量下跌', value: quadRaw['缩量下跌'], cls: 'is-down-weak' }
      ].map(function (q) {
        q.pct = Math.round((q.value / quadTotal) * 1000) / 10;
        return q;
      });
      var quadDownShrinkPct = Math.round(
        (quadRaw['缩量下跌'] / (quadRaw['缩量下跌'] + quadRaw['放量下跌'])) * 1000
      ) / 10;

      /* ------------------------------------------------------------ 洞察文案 */
      var span = ((SUM.high / SUM.low - 1) * 100).toFixed(1);
      var insights = [
        {
          title: '跌幅集中在两段，全年不是单边下行',
          text: '全年 -23.43% 由两段下行叠加而成：2/01→3/16 的 -22.76% 与 7/31→12/20 的 -31.75%，' +
                '中间夹着一段长达 92 个交易日、+16.25% 的修复行情。<b>下跌是脉冲式的，修复是缓慢的</b>。',
          proof: ['阶段 4 段', '最长修复段 92 天', '次长下行段 97 天']
        },
        {
          title: '下半场贡献了全部跌幅',
          text: '上半年（截至 6 月末）仍为 +' + SUM.h1Return + '%，下半年直接转为 ' + SUM.h2Return + '%。' +
                '7 月末是本轮的趋势分水岭，此后收盘价再未站上 MA20。',
          proof: ['H1 +' + SUM.h1Return + '%', 'H2 ' + SUM.h2Return + '%']
        },
        {
          title: '回撤远大于跌幅，持有时点决定体验',
          text: '区间跌幅 23.43%，但自 2 月高点的最大回撤达 <b>-38.71%</b>（' + SUM.maxDrawdownDate + ' 见底）。' +
                '这意味着在 2 月高点买入的持有者，账面亏损比「年度收益」难看得多。',
          proof: ['最大回撤 -38.71%', '高低点振幅 ' + span + '%']
        },
        {
          title: '跌多于涨，但反弹弹性更强',
          text: '下跌 ' + SUM.downDays + ' 天、上涨 ' + SUM.upDays + ' 天，日胜率仅 ' + SUM.winRate + '%，' +
                '典型「阴跌多、阳线猛」结构。最大单日涨幅 <b>+' + SUM.maxUp + '%</b> 高于最大单日跌幅 ' +
                Math.abs(SUM.maxDown) + '%，说明多头的爆发力并未消失。',
          proof: ['胜率 ' + SUM.winRate + '%', '最长连跌 ' + SUM.maxStreakDown + ' 天', '最长连涨 ' + SUM.maxStreakUp + ' 天']
        },
        {
          title: '量价脱钩：跌得久，但不是放量砸出来的',
          text: '换手率与涨跌幅的相关系数仅 ' + SUM.corrTurnoverPct + '，日线级别几乎没有量价共振。' +
                '下跌日中 <b>' + quadDownShrinkPct + '%</b> 属于缩量下跌，更像流动性收缩下的估值下移，' +
                '而不是恐慌性放量出逃。',
          proof: ['r = ' + SUM.corrTurnoverPct, '缩量下跌 ' + quadRaw['缩量下跌'] + ' 天', '放量下跌仅 ' + quadRaw['放量下跌'] + ' 天']
        },
        {
          title: '波动即流动性：振幅与成交额高度同步',
          text: '成交额与振幅的相关系数达 <b>' + SUM.corrAmountAmplitude + '</b>，是本期唯一强相关的量价关系。' +
                '大波动日必然伴随大成交，说明价格发现集中在少数交易日，其余时间以低换手「磨」为主（日均换手仅 ' +
                SUM.avgTurnover + '%）。',
          proof: ['r = ' + SUM.corrAmountAmplitude, '日均换手 ' + SUM.avgTurnover + '%', '日均振幅 ' + SUM.avgAmplitude + '%']
        }
      ];

      /* ------------------------------------------------------------ 图表工具 */
      var charts = {};
      var built = {};
      var ranges = [
        { key: 'm1', label: '近 1 月', n: 22 },
        { key: 'm3', label: '近 3 月', n: 66 },
        { key: 'm6', label: '近 6 月', n: 132 },
        { key: 'all', label: '全年', n: S.dates.length }
      ];

      function pick(key) {
        for (var i = 0; i < ranges.length; i++) if (ranges[i].key === key) return ranges[i];
        return ranges[ranges.length - 1];
      }

      var baseText = {
        fontFamily: FONT,
        color: LABEL
      };

      function axisCommon(n) {
        return {
          axisLine: { lineStyle: { color: GRID } },
          axisTick: { show: false },
          axisLabel: {
            color: LABEL, fontSize: 9, fontFamily: FONT,
            hideOverlap: true, margin: 8,
            interval: n > 60 ? Math.floor(n / 4) : 'auto'
          },
          splitLine: { show: false }
        };
      }

      function yAxisCommon(fmt) {
        return {
          type: 'value',
          scale: true,
          axisLine: { show: false },
          axisTick: { show: false },
          axisLabel: { color: LABEL, fontSize: 9, fontFamily: FONT, formatter: fmt || '{value}', margin: 6 },
          splitLine: { lineStyle: { color: GRID, type: 'solid' } }
        };
      }

      var tooltipBase = {
        trigger: 'axis',
        confine: true,
        backgroundColor: 'rgba(20,32,51,.94)',
        borderWidth: 0,
        padding: [7, 10],
        textStyle: { color: '#eaf1f8', fontSize: 10.5, fontFamily: FONT },
        axisPointer: {
          lineStyle: { color: BRAND, width: 1, type: 'dashed' },
          label: { backgroundColor: INK, fontSize: 9 }
        }
      };

      function ensure(key, refName, option) {
        var el = Vue.ref(null);
        return { key: key, refName: refName, el: el, option: option };
      }

      function build(name, el, option) {
        if (!el) return null;
        if (!charts[name]) {
          charts[name] = echarts.init(el, null, { renderer: 'canvas', devicePixelRatio: 2 });
        }
        charts[name].setOption(option, true);
        charts[name].resize();
        built[name] = true;
        return charts[name];
      }

      /* -------------------------------------------------------------- 图表 1 */
      function sparkOption() {
        return {
          animationDuration: 900,
          grid: { left: 0, right: 0, top: 8, bottom: 0 },
          xAxis: { type: 'category', data: S.shortDates, show: false, boundaryGap: false },
          yAxis: { type: 'value', show: false, scale: true },
          series: [{
            type: 'line', data: S.close, smooth: 0.28, symbol: 'none',
            lineStyle: { width: 1.5, color: 'rgba(180,208,232,.85)' },
            areaStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: 'rgba(150,190,226,.45)' },
                { offset: 1, color: 'rgba(150,190,226,0)' }
              ])
            }
          }]
        };
      }

      /* -------------------------------------------------------------- 图表 2 */
      function klineOption(key) {
        var n = pick(key).n;
        var start = Math.max(0, S.dates.length - n);
        var dates = S.dates.slice(start).map(function (d) { return d.slice(5); });
        var ohlc = [], vol = [];
        for (var i = start; i < S.dates.length; i++) {
          ohlc.push([S.open[i], S.close[i], S.low[i], S.high[i]]);
          vol.push({
            value: S.volume[i],
            itemStyle: { color: S.close[i] >= S.open[i] ? 'rgba(213,73,63,.72)' : 'rgba(23,147,94,.72)' }
          });
        }
        return {
          animation: true,
          animationDuration: 500,
          textStyle: baseText,
          tooltip: Object.assign({}, tooltipBase, {
            formatter: function (ps) {
              var k = ps[0].dataIndex;
              var o = ohlc[k];
              var chg = S.pctChg[start + k];
              var col = chg >= 0 ? UP : DOWN;
              return '<b style="font-size:11px">' + S.dates[start + k] + '</b><br>' +
                '开 ' + o[0].toFixed(2) + '　收 ' + o[1].toFixed(2) + '<br>' +
                '高 ' + o[3].toFixed(2) + '　低 ' + o[2].toFixed(2) + '<br>' +
                '<span style="color:' + col + '">' + (chg >= 0 ? '+' : '') + chg.toFixed(2) + '%</span>' +
                '　量 ' + S.volume[start + k].toFixed(1) + ' 万手';
            }
          }),
          axisPointer: { link: [{ xAxisIndex: 'all' }] },
          grid: [
            { left: 34, right: 12, top: 8, height: '56%' },
            { left: 34, right: 12, top: '70%', height: '18%' }
          ],
          xAxis: [
            Object.assign({}, axisCommon(n), {
              type: 'category', data: dates, boundaryGap: true,
              axisPointer: { z: 100 }, axisLabel: { show: false }, axisLine: { show: false }
            }),
            Object.assign({}, axisCommon(n), {
              type: 'category', data: dates, gridIndex: 1,
              axisLabel: { color: LABEL, fontSize: 9, fontFamily: FONT, hideOverlap: true, interval: Math.floor(n / 4), margin: 6 }
            })
          ],
          yAxis: [
            Object.assign({ gridIndex: 0 }, yAxisCommon()),
            {
              gridIndex: 1, min: 0, max: function (v) { return v.max * 1.5; },
              axisLine: { show: false }, axisTick: { show: false },
              axisLabel: { show: false },
              splitLine: { show: false }
            }
          ],
          dataZoom: [
            { type: 'inside', xAxisIndex: [0, 1], start: 0, end: 100, zoomOnMouseWheel: false, moveOnMouseMove: true }
          ],
          series: [
            {
              name: '日K', type: 'candlestick', data: ohlc,
              itemStyle: {
                color: UP, color0: DOWN,
                borderColor: UP, borderColor0: DOWN, borderWidth: 1
              }
            },
            {
              name: '成交量', type: 'bar', xAxisIndex: 1, yAxisIndex: 1,
              data: vol, barWidth: '58%'
            }
          ]
        };
      }

      /* -------------------------------------------------------------- 图表 3 */
      function maOption() {
        function line(name, data, color, w) {
          return {
            name: name, type: 'line', data: data, smooth: true, symbol: 'none',
            connectNulls: true,
            itemStyle: { color: color },
            lineStyle: { width: w, color: color },
            emphasis: { disabled: true }
          };
        }
        return {
          textStyle: baseText,
          tooltip: Object.assign({}, tooltipBase, {
            formatter: function (ps) {
              var s = '<b style="font-size:11px">' + ps[0].axisValue + '</b>';
              ps.forEach(function (p) {
                if (p.value == null) return;
                s += '<br><span style="display:inline-block;width:6px;height:6px;border-radius:50%;background:' +
                  p.color + ';margin-right:5px"></span>' + p.seriesName +
                  ' <b style="float:right;margin-left:10px">' + Number(p.value).toFixed(2) + '</b>';
              });
              return s;
            }
          }),
          legend: {
            data: ['收盘价', 'MA5', 'MA20', 'MA60'],
            top: 0, left: 0, itemWidth: 8, itemHeight: 3, itemGap: 10,
            textStyle: { color: LABEL, fontSize: 9, fontFamily: FONT },
            icon: 'rect'
          },
          grid: { left: 4, right: 8, top: 30, bottom: 6, containLabel: true },
          xAxis: Object.assign({ type: 'category', data: S.shortDates, boundaryGap: false }, axisCommon(S.dates.length)),
          yAxis: yAxisCommon(),
          series: [
            line('收盘价', S.close, '#142033', 1.5),
            line('MA5', S.ma5, '#3f8fd6', 1.2),
            line('MA20', S.ma20, '#d18b28', 1.2),
            line('MA60', S.ma60, '#8e5fb5', 1.2)
          ]
        };
      }

      /* -------------------------------------------------------------- 图表 4 */
      function ddOption() {
        return {
          textStyle: baseText,
          tooltip: Object.assign({}, tooltipBase, {
            valueFormatter: function (v) { return Number(v).toFixed(2) + '%'; }
          }),
          grid: { left: 4, right: 8, top: 12, bottom: 6, containLabel: true },
          xAxis: Object.assign({ type: 'category', data: S.shortDates, boundaryGap: false }, axisCommon(S.dates.length)),
          yAxis: Object.assign(yAxisCommon('{value}%'), { max: 0 }),
          series: [{
            name: '回撤', type: 'line', data: S.drawdown, symbol: 'none', smooth: 0.2,
            lineStyle: { width: 1.4, color: DOWN },
            areaStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: 'rgba(23,147,94,.05)' },
                { offset: 1, color: 'rgba(23,147,94,.30)' }
              ])
            },
            markPoint: {
              symbol: 'circle', symbolSize: 7,
              data: [{ type: 'min', name: '最大回撤' }],
              itemStyle: { color: DOWN, borderColor: '#fff', borderWidth: 1.5 },
              label: {
                show: true, position: 'left', distance: 8,
                formatter: SUM.maxDrawdown + '%',
                color: DOWN, fontSize: 10, fontWeight: 'bold', fontFamily: FONT,
                backgroundColor: 'rgba(255,255,255,.92)', padding: [3, 7], borderRadius: 4
              }
            }
          }]
        };
      }

      /* -------------------------------------------------------------- 图表 5 */
      function monthOption() {
        return {
          textStyle: baseText,
          tooltip: Object.assign({}, tooltipBase, {
            formatter: function (ps) {
              var m = D.monthly[ps[0].dataIndex];
              return '<b>' + m.month + '</b><br>收益 <b style="color:' + (m.return >= 0 ? '#ff8f88' : '#5ed3a0') + '">' +
                (m.return >= 0 ? '+' : '') + m.return + '%</b><br>月末收盘 ' + m.close +
                '<br>月成交额 ' + m.vol + ' 亿';
            }
          }),
          grid: { left: 4, right: 8, top: 24, bottom: 6, containLabel: true },
          xAxis: Object.assign({ type: 'category', data: D.monthly.map(function (m) { return m.month.replace('月', ''); }) },
            axisCommon(12)),
          yAxis: Object.assign(yAxisCommon('{value}%'), { splitNumber: 3 }),
          series: [{
            type: 'bar', barWidth: '56%',
            data: D.monthly.map(function (m) {
              var up = m.return >= 0;
              return {
                value: m.return,
                itemStyle: {
                  color: up ? UP : DOWN,
                  borderRadius: up ? [3, 3, 0, 0] : [0, 0, 3, 3],
                  opacity: 0.92
                },
                // 逐项指定标签位置：正值在柱顶、负值在柱底
                label: {
                  show: true, position: up ? 'top' : 'bottom', distance: 4,
                  color: up ? UP : DOWN, fontSize: 8.5, fontFamily: FONT,
                  fontWeight: 'bold'
                }
              };
            }),
            label: {
              show: true, fontSize: 8.5, fontFamily: FONT,
              formatter: function (p) {
                var v = p.value;
                if (Math.abs(v) < 0.5) return '0';
                return (v > 0 ? '+' : '') + v.toFixed(0);
              }
            }
          }]
        };
      }

      /* -------------------------------------------------------------- 图表 6 */
      function histOption() {
        return {
          textStyle: baseText,
          tooltip: Object.assign({}, tooltipBase, {
            formatter: function (ps) {
              return '<b>' + ps[0].axisValue.toFixed(1) + '% 附近</b><br>' + ps[0].value + ' 个交易日';
            }
          }),
          grid: { left: 4, right: 8, top: 14, bottom: 6, containLabel: true },
          xAxis: Object.assign({
            type: 'category',
            data: D.histogram.map(function (b) { return b.bin; }),
            axisLabel: {
              color: LABEL, fontSize: 9, fontFamily: FONT, hideOverlap: true,
              formatter: function (v) { return v > 0 ? '+' + Number(v).toFixed(0) : Number(v).toFixed(0); }
            }
          }, { axisLine: { lineStyle: { color: GRID } }, axisTick: { show: false }, splitLine: { show: false } }),
          yAxis: Object.assign(yAxisCommon(), {
            splitNumber: 3,
            max: function (v) { return Math.ceil(v.max / 10) * 10 + 4; }
          }),
          series: [{
            type: 'bar', barWidth: '78%',
            data: D.histogram.map(function (b) {
              return {
                value: b.count,
                itemStyle: { color: b.bin >= 0 ? 'rgba(213,73,63,.82)' : 'rgba(23,147,94,.82)', borderRadius: 2 }
              };
            })
          }]
        };
      }

      /* -------------------------------------------------------------- 图表 7 */
      function scatterOption() {
        return {
          textStyle: baseText,
          tooltip: Object.assign({}, tooltipBase, {
            formatter: function (p) {
              return '换手 <b>' + p.value[0].toFixed(2) + '%</b><br>涨跌 <b>' +
                (p.value[1] >= 0 ? '+' : '') + p.value[1].toFixed(2) + '%</b>';
            }
          }),
          grid: { left: 4, right: 10, top: 14, bottom: 6, containLabel: true },
          xAxis: {
            type: 'value', scale: true, splitNumber: 4,
            axisLine: { show: false }, axisTick: { show: false },
            axisLabel: { color: LABEL, fontSize: 9, fontFamily: FONT, formatter: '{value}%' },
            splitLine: { lineStyle: { color: GRID } }
          },
          yAxis: Object.assign(yAxisCommon('{value}%'), { min: -6.5, max: 6.8, splitNumber: 4 }),
          series: [{
            type: 'scatter', data: D.scatter, symbolSize: 5,
            itemStyle: {
              color: function (p) { return p.value[1] >= 0 ? 'rgba(213,73,63,.62)' : 'rgba(23,147,94,.62)'; }
            },
            markLine: {
              silent: true, symbol: 'none',
              lineStyle: { color: 'rgba(141,150,163,.55)', type: 'dashed', width: 1 },
              label: { show: false },
              data: [{ yAxis: 0 }]
            }
          }]
        };
      }

      /* ---------------------------------------------------------- 构建调度 */
      var optionMap = {
        kline: function () { return klineOption(range.value); },
        ma: maOption,
        dd: ddOption,
        month: monthOption,
        hist: histOption,
        scatter: scatterOption
      };

      function buildTab(name) {
        var r = inst && inst.$refs;
        if (!r) return;
        if (name === 'overview') {
          if (r.spark) build('spark', r.spark, sparkOption());
          return;
        }
        var ids = name === 'trend' ? ['kline', 'ma', 'dd']
          : name === 'stats' ? ['month', 'hist', 'scatter'] : [];
        ids.forEach(function (id) {
          if (r[id]) build(id, r[id], optionMap[id]());
        });
        Object.keys(charts).forEach(function (k) {
          if (charts[k] && charts[k].getDom() && charts[k].getDom().offsetParent) charts[k].resize();
        });
      }

      /* ---------------------------------------------------------- 交互动作 */
      function setRange(key) {
        range.value = key;
        Vue.nextTick(function () {
          var el = inst && inst.$refs && inst.$refs.kline;
          if (el) build('kline', el, klineOption(key));
        });
      }

      var zoomMeta = {
        kline: { title: '复权 K 线 + 成交量', desc: '上图为日 OHLC，下图为成交量（万手）；红涨绿跌，可双指缩放查看细节。' },
        ma: { title: '收盘价与均线结构', desc: 'MA5（蓝）反应短期情绪，MA20（橙）刻画中期趋势，MA60（紫）代表长期方向。' },
        dd: { title: '回撤深度', desc: '自历史最高收盘价的回撤幅度。全年仅 1 月上旬贴近水面，其余时间长期处于水下。' },
        month: { title: '月度收益分布', desc: '以月末收盘对比上月末收盘计算，正负分离便于识别月份强弱。' },
        hist: { title: '日涨跌幅分布', desc: '主体集中在 ±2% 区间，负向尾部略厚，对应全年偏空的收益结构。' },
        scatter: { title: '换手率 × 日涨跌幅', desc: '点云无明显斜向趋势，视觉上印证量价弱相关的统计结论。' }
      };

      function zoom(name) {
        zoomCfg.value = zoomMeta[name];
        zoomOn.value = true;
        Vue.nextTick(function () {
          setTimeout(function () {
            // 弹层内容经 Teleport 渲染，$refs 不稳定，直接走 DOM 查询
            var el = document.querySelector('.zoom .chart');
            if (!el) return;
            var inst = echarts.getInstanceByDom(el) || echarts.init(el, null, { renderer: 'canvas', devicePixelRatio: 2 });
            inst.setOption(optionMap[name](), true);
            inst.resize();
            charts['zoom'] = inst;
          }, 120);
        });
      }

      var inst = null;

      Vue.onMounted(function () {
        inst = Vue.getCurrentInstance().proxy;
        setTimeout(function () { buildTab('overview'); }, 80);
        window.addEventListener('resize', function () {
          Object.keys(charts).forEach(function (k) {
            if (charts[k]) charts[k].resize();
          });
        });
      });

      Vue.watch(tab, function (v) {
        Vue.nextTick(function () { setTimeout(function () { buildTab(v); }, 90); });
      });

      Vue.watch(zoomOn, function (v) {
        if (!v) {
          var el = document.querySelector('.zoom .chart');
          if (el) {
            var inst = echarts.getInstanceByDom(el);
            if (inst) { inst.dispose(); }
            delete charts['zoom'];
          }
        }
      });

      return {
        tab: tab, range: range, zoomOn: zoomOn, zoomCfg: zoomCfg,
        meta: D.meta, summary: SUM, quality: D.quality, phases: phases,
        insights: insights, quads: quads, ranges: ranges,
        upPhases: upPhases, downPhases: downPhases,
        monthUp: monthUp, monthDown: monthDown, worstMonth: worstMonth,
        skew: skew, waterDays: waterDays, quadDownShrinkPct: quadDownShrinkPct,
        fmt: function (v) { return Number(v).toFixed(2); },
        pct: function (v) { return (v >= 0 ? '+' : '') + Number(v).toFixed(2) + '%'; },
        setRange: setRange, zoom: zoom
      };
    }
  });

  app.use(TDesign);
  var vm = app.mount('#app');
})();
