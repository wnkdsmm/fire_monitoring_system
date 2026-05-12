(function (global) {
    var shared = global.FireUi || {};
    var byId = shared.byId;
    var escapeHtml = shared.escapeHtml;
    var normalizeCssColor = shared.normalizeCssColor;
    var normalizePercent = shared.normalizePercent;

    function setChartEmptyState(chartNode, isEmpty) {
        var panel = chartNode && typeof chartNode.closest === 'function'
            ? chartNode.closest('.chart-panel')
            : null;
        if (chartNode) {
            chartNode.classList.toggle('is-empty', !!isEmpty);
        }
        if (panel) {
            panel.classList.toggle('is-chart-empty', !!isEmpty);
        }
    }

    function applyChartDecorators(root) {
        var scope = root && typeof root.querySelectorAll === 'function' ? root : document;
        Array.prototype.forEach.call(scope.querySelectorAll('[data-legend-color]'), function (node) {
            node.style.setProperty('--legend-color', normalizeCssColor(node.getAttribute('data-legend-color'), 'currentColor'));
        });
        Array.prototype.forEach.call(scope.querySelectorAll('[data-bar-width]'), function (node) {
            node.style.setProperty('--ml-bar-width', normalizePercent(node.getAttribute('data-bar-width'), '0%'));
        });
    }

    function renderFallback(chartNode, fallbackNode, message) {
        if (!chartNode || !fallbackNode) {
            return;
        }
        setChartEmptyState(chartNode, true);
        chartNode.innerHTML = '';
        fallbackNode.textContent = message || 'РќРµС‚ РґР°РЅРЅС‹С… РґР»СЏ РіСЂР°С„РёРєР°.';
        fallbackNode.classList.remove('is-hidden');
        fallbackNode.style.display = '';
    }


    function renderBarsChart(chart, chartId, fallbackId) {
        var chartNode = byId(chartId);
        var fallbackNode = byId(fallbackId);
        if (!chartNode || !fallbackNode) {
            return;
        }

        var items = chart && chart.items;
        if (!Array.isArray(items) || !items.length) {
            renderFallback(chartNode, fallbackNode, chart && chart.empty_message);
            return;
        }

        setChartEmptyState(chartNode, false);
        fallbackNode.classList.add('is-hidden');
        var maxValue = Math.max.apply(null, items.map(function (item) { return item.value; }).concat([1]));
        var html = '<div class="ml-bars">';
        items.forEach(function (item) {
            var percent = Math.max(8, Math.round((item.value / maxValue) * 100));
            html += ''
                + '<div class="ml-bar-row">'
                + '<div class="ml-bar-meta"><span>' + escapeHtml(item.label) + '</span><strong>' + escapeHtml(item.value_display) + '%</strong></div>'
                + '<div class="ml-bar-track"><div class="ml-bar-fill" data-bar-width="' + percent + '%"></div></div>'
                + '</div>';
        });
        html += '</div>';
        chartNode.innerHTML = html;
        applyChartDecorators(chartNode);
    }

    function renderAppgChart(appgSeries, chartId, fallbackId, noteId) {
        var chartNode = byId(chartId);
        var fallbackNode = byId(fallbackId);
        var noteNode = noteId ? byId(noteId) : null;
        if (!chartNode || !fallbackNode) {
            return;
        }
        var rows = Array.isArray(appgSeries) ? appgSeries : [];
        var currentCount = rows.filter(function (row) {
            return row && row.current_value != null && !isNaN(Number(row.current_value));
        }).length;
        var appgAvailableCount = rows.filter(function (row) {
            return row && row.appg_available && row.appg_value != null && !isNaN(Number(row.appg_value));
        }).length;

        if (!rows.length) {
            renderFallback(chartNode, fallbackNode, 'Нет данных для APPG-сравнения за выбранный период.');
            if (noteNode) {
                noteNode.textContent = '';
                noteNode.classList.add('is-hidden');
            }
            return;
        }

        setChartEmptyState(chartNode, false);
        fallbackNode.classList.add('is-hidden');
        fallbackNode.style.display = 'none';
        if (noteNode) {
            if (appgAvailableCount < currentCount) {
                noteNode.textContent = 'Для части дат АППГ недоступен (нет записи за D-1 год).';
                noteNode.classList.remove('is-hidden');
            } else {
                noteNode.textContent = '';
                noteNode.classList.add('is-hidden');
            }
        }

        var width = 920;
        var height = 360;
        var padding = { top: 20, right: 24, bottom: 54, left: 54 };
        var innerWidth = width - padding.left - padding.right;
        var innerHeight = height - padding.top - padding.bottom;
        var denominator = Math.max(rows.length - 1, 1);

        var values = [];
        rows.forEach(function (row) {
            if (row && row.current_value != null) { values.push(Number(row.current_value)); }
            if (row && row.appg_value != null) { values.push(Number(row.appg_value)); }
        });
        var yMin = 0;
        var yMax = Math.max.apply(null, values.concat([1]));
        yMax = Math.max(1, Math.ceil((yMax + 0.5) * 2) / 2);
        if (yMax <= yMin) { yMax = yMin + 1; }

        function x(index) {
            return padding.left + (index / denominator) * innerWidth;
        }
        function y(value) {
            return padding.top + innerHeight - ((value - yMin) / (yMax - yMin)) * innerHeight;
        }
        function dateLabel(isoDate) {
            var text = String(isoDate || '');
            return text.length >= 10 ? (text.slice(8, 10) + '.' + text.slice(5, 7)) : text;
        }
        function buildSegmentPath(getValue) {
            var segments = [];
            var path = '';
            for (var i = 0; i < rows.length; i += 1) {
                var val = getValue(rows[i]);
                if (val == null || isNaN(val)) {
                    if (path) { segments.push(path); path = ''; }
                    continue;
                }
                var cmd = path ? ' L ' : 'M ';
                path += cmd + x(i).toFixed(2) + ' ' + y(Number(val)).toFixed(2);
            }
            if (path) { segments.push(path); }
            return segments;
        }

        var gridLines = '';
        var axisLabels = '';
        for (var step = 0; step <= 4; step += 1) {
            var value = yMin + ((yMax - yMin) * step / 4);
            var py = y(value);
            gridLines += '<line x1="' + padding.left + '" y1="' + py.toFixed(2) + '" x2="' + (width - padding.right) + '" y2="' + py.toFixed(2) + '" class="ml-grid-line"></line>';
            axisLabels += '<text x="' + (padding.left - 10) + '" y="' + (py + 4).toFixed(2) + '" text-anchor="end" class="ml-axis-label">' + escapeHtml(String(Math.round(value * 10) / 10).replace('.', ',')) + '</text>';
        }

        var tickIndexes = [0, Math.floor((rows.length - 1) / 2), rows.length - 1]
            .filter(function (value, index, arr) { return arr.indexOf(value) === index && value >= 0; });
        tickIndexes.forEach(function (index) {
            axisLabels += '<text x="' + x(index).toFixed(2) + '" y="' + (height - 16) + '" text-anchor="middle" class="ml-axis-label">' + escapeHtml(dateLabel(rows[index].current_date)) + '</text>';
        });

        var currentSegments = buildSegmentPath(function (row) { return row.current_value; });
        var appgSegments = buildSegmentPath(function (row) { return row.appg_value; });

        var svg = ''
            + '<svg viewBox="0 0 ' + width + ' ' + height + '" class="ml-svg-chart" preserveAspectRatio="none">'
            + gridLines
            + '<line x1="' + padding.left + '" y1="' + (height - padding.bottom) + '" x2="' + (width - padding.right) + '" y2="' + (height - padding.bottom) + '" class="ml-axis-line"></line>'
            + '<line x1="' + padding.left + '" y1="' + padding.top + '" x2="' + padding.left + '" y2="' + (height - padding.bottom) + '" class="ml-axis-line"></line>';

        currentSegments.forEach(function (path) {
            svg += '<path d="' + path + '" class="ml-line-forecast"></path>';
        });
        appgSegments.forEach(function (path) {
            svg += '<path d="' + path + '" class="ml-line-appg"></path>';
        });

        rows.forEach(function (row, index) {
            var currentValue = row && row.current_value != null ? Number(row.current_value) : null;
            if (currentValue != null && !isNaN(currentValue)) {
                svg += '<circle cx="' + x(index).toFixed(2) + '" cy="' + y(currentValue).toFixed(2) + '" r="3.5" class="ml-forecast-point"></circle>';
            }
            if (row && row.appg_available && row.appg_value != null) {
                var appgValue = Number(row.appg_value);
                if (!isNaN(appgValue)) {
                    svg += '<circle cx="' + x(index).toFixed(2) + '" cy="' + y(appgValue).toFixed(2) + '" r="3" class="ml-appg-point"></circle>';
                }
            }
        });

        svg += axisLabels + '</svg>';

        chartNode.innerHTML = ''
            + '<div class="ml-chart-legend">'
            + '<span class="ml-chart-legend-item"><i data-legend-color="#0F766E"></i>Текущий период</span>'
            + '<span class="ml-chart-legend-item"><i data-legend-color="#B45309"></i>АППГ (D-1 год)</span>'
            + '</div>'
            + '<div class="ml-chart-shell">' + svg + '</div>';
        applyChartDecorators(chartNode);
    }

    function renderCompareChart(compareSeries, chartId, fallbackId, summaryId) {
        var chartNode = byId(chartId);
        var fallbackNode = byId(fallbackId);
        var summaryNode = summaryId ? byId(summaryId) : null;
        if (!chartNode || !fallbackNode) {
            return;
        }
        var data = compareSeries || {};
        var rows = Array.isArray(data.rows) ? data.rows : [];
        var historyHasData = data.history_has_data === true;
        var aYear = data.year_a != null ? String(data.year_a) : 'A';
        var bYear = data.year_b != null ? String(data.year_b) : 'B';
        var aPoints = rows.filter(function (row) { return row && row.a_value != null && !isNaN(Number(row.a_value)); }).length;
        var bPoints = rows.filter(function (row) { return row && row.b_value != null && !isNaN(Number(row.b_value)); }).length;
        if (!rows.length || (!aPoints && !bPoints)) {
            renderFallback(chartNode, fallbackNode, 'Нет данных для сравнения выбранных лет за выбранный месяц.');
            if (summaryNode) {
                summaryNode.textContent = '';
            }
            return;
        }

        setChartEmptyState(chartNode, false);
        fallbackNode.classList.add('is-hidden');
        fallbackNode.style.display = 'none';

        var values = [];
        rows.forEach(function (row) {
            if (row && row.a_value != null) { values.push(Number(row.a_value)); }
            if (row && row.b_value != null) { values.push(Number(row.b_value)); }
        });
        var yMin = 0;
        var yMax = Math.max.apply(null, values.concat([1]));
        yMax = Math.max(1, Math.ceil((yMax + 0.5) * 2) / 2);
        var width = 920;
        var height = 360;
        var padding = { top: 20, right: 24, bottom: 54, left: 54 };
        var innerWidth = width - padding.left - padding.right;
        var innerHeight = height - padding.top - padding.bottom;
        var denominator = Math.max(rows.length - 1, 1);

        function x(index) { return padding.left + (index / denominator) * innerWidth; }
        function y(value) { return padding.top + innerHeight - ((value - yMin) / (yMax - yMin || 1)) * innerHeight; }
        function buildSegments(key) {
            var segments = [];
            var path = '';
            rows.forEach(function (row, i) {
                var raw = row ? row[key] : null;
                var val = raw == null ? null : Number(raw);
                if (val == null || isNaN(val)) {
                    if (path) { segments.push(path); path = ''; }
                    return;
                }
                path += (path ? ' L ' : 'M ') + x(i).toFixed(2) + ' ' + y(val).toFixed(2);
            });
            if (path) { segments.push(path); }
            return segments;
        }

        var gridLines = '';
        var axisLabels = '';
        for (var step = 0; step <= 4; step += 1) {
            var value = yMin + ((yMax - yMin) * step / 4);
            var py = y(value);
            gridLines += '<line x1="' + padding.left + '" y1="' + py.toFixed(2) + '" x2="' + (width - padding.right) + '" y2="' + py.toFixed(2) + '" class="ml-grid-line"></line>';
            axisLabels += '<text x="' + (padding.left - 10) + '" y="' + (py + 4).toFixed(2) + '" text-anchor="end" class="ml-axis-label">' + escapeHtml(String(Math.round(value * 10) / 10).replace('.', ',')) + '</text>';
        }
        var ticks = [0, Math.floor((rows.length - 1) / 2), rows.length - 1].filter(function (v, i, arr) { return arr.indexOf(v) === i && v >= 0; });
        ticks.forEach(function (idx) {
            axisLabels += '<text x="' + x(idx).toFixed(2) + '" y="' + (height - 16) + '" text-anchor="middle" class="ml-axis-label">' + escapeHtml(String(rows[idx].day || '')) + '</text>';
        });

        var aSegments = buildSegments('a_value');
        var bSegments = buildSegments('b_value');
        var svg = '<svg viewBox="0 0 ' + width + ' ' + height + '" class="ml-svg-chart" preserveAspectRatio="none">'
            + gridLines
            + '<line x1="' + padding.left + '" y1="' + (height - padding.bottom) + '" x2="' + (width - padding.right) + '" y2="' + (height - padding.bottom) + '" class="ml-axis-line"></line>'
            + '<line x1="' + padding.left + '" y1="' + padding.top + '" x2="' + padding.left + '" y2="' + (height - padding.bottom) + '" class="ml-axis-line"></line>';
        aSegments.forEach(function (path) { svg += '<path d="' + path + '" class="ml-line-forecast"></path>'; });
        bSegments.forEach(function (path) { svg += '<path d="' + path + '" class="ml-line-appg"></path>'; });
        svg += axisLabels + '</svg>';

        chartNode.innerHTML = ''
            + '<div class="ml-chart-legend">'
            + '<span class="ml-chart-legend-item"><i data-legend-color="#0F766E"></i>' + escapeHtml(aYear) + '</span>'
            + '<span class="ml-chart-legend-item"><i data-legend-color="#B45309"></i>' + escapeHtml(bYear) + '</span>'
            + '</div>'
            + '<div class="ml-chart-shell">' + svg + '</div>';
        applyChartDecorators(chartNode);

        if (summaryNode) {
            var aSummary = data.a_summary || {};
            var bSummary = data.b_summary || {};
            summaryNode.textContent = 'Год A (' + aYear + '): факт ' + String(aSummary.fact_days || 0) + ', ML ' + String(aSummary.ml_days || 0)
                + ' | Год B (' + bYear + '): факт ' + String(bSummary.fact_days || 0) + ', ML ' + String(bSummary.ml_days || 0)
                + (historyHasData ? '' : ' | diag: history_has_data=false');
        }
    }
function renderChartSkeleton(chartId, fallbackId) {
        var chartNode = byId(chartId);
        var fallbackNode = byId(fallbackId);
        if (chartNode) {
            setChartEmptyState(chartNode, false);
            chartNode.innerHTML = '<div class="ml-chart-placeholder"></div>';
        }
        if (fallbackNode) {
            fallbackNode.classList.add('is-hidden');
            fallbackNode.style.display = 'none';
        }
    }

    global.MlModelCharts = {
        renderAppgChart: renderAppgChart,
        renderCompareChart: renderCompareChart,
        renderBarsChart: renderBarsChart,
        renderChartSkeleton: renderChartSkeleton
    };
}(window));

