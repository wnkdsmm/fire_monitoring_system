(function (global) {
    var shared = global.FireUi || {};
    var byId = shared.byId;
    var escapeHtml = shared.escapeHtml;
    var normalizeCssColor = shared.normalizeCssColor;

    function formatMetric(value) {
        var n = Number(value);
        if (!isFinite(n)) {
            return '-';
        }
        return n.toFixed(2);
    }

    function renderGuideHint(compareSeries, overlapBC) {
        var hintNode = byId('mlCompareGuideHint');
        if (!hintNode) {
            return;
        }
        var hints = [];
        var quality = (compareSeries && compareSeries.d_quality) || {};
        if (quality.quality_available === false) {
            hints.push('Качество Poisson сейчас недоступно: ' + String(quality.reason || 'insufficient_history'));
        }
        if (overlapBC) {
            hints.push('Compare-series совпадает с Год 2 для текущих параметров.');
        }
        if (!hints.length) {
            hintNode.textContent = '';
            hintNode.classList.add('is-hidden');
            return;
        }
        hintNode.textContent = hints.join(' ');
        hintNode.classList.remove('is-hidden');
    }

    function applyLegendDecorators(root) {
        var scope = root && typeof root.querySelectorAll === 'function' ? root : document;
        Array.prototype.forEach.call(scope.querySelectorAll('[data-legend-color]'), function (node) {
            node.style.setProperty('--legend-color', normalizeCssColor(node.getAttribute('data-legend-color'), 'currentColor'));
        });
    }

    function setChartEmptyState(chartNode, isEmpty) {
        var panel = chartNode && typeof chartNode.closest === 'function' ? chartNode.closest('.chart-panel') : null;
        if (chartNode) {
            chartNode.classList.toggle('is-empty', !!isEmpty);
        }
        if (panel) {
            panel.classList.toggle('is-chart-empty', !!isEmpty);
        }
    }

    function renderFallback(chartNode, fallbackNode, message) {
        if (!chartNode || !fallbackNode) {
            return;
        }
        setChartEmptyState(chartNode, true);
        chartNode.innerHTML = '';
        fallbackNode.textContent = message || 'Нет данных для графика.';
        fallbackNode.classList.remove('is-hidden');
        fallbackNode.style.display = '';
    }

    function ensureChartTooltip(chartNode) {
        if (!chartNode) {
            return null;
        }
        var existing = chartNode.querySelector('.ml-chart-tooltip');
        if (existing) {
            return existing;
        }
        var tooltip = document.createElement('div');
        tooltip.className = 'ml-chart-tooltip is-hidden';
        chartNode.appendChild(tooltip);
        return tooltip;
    }

    function wirePointTooltips(chartNode) {
        if (!chartNode) {
            return;
        }
        var tooltip = ensureChartTooltip(chartNode);
        if (!tooltip) {
            return;
        }

        function hideTooltip() {
            tooltip.classList.add('is-hidden');
            tooltip.textContent = '';
        }

        function showTooltip(event, text) {
            if (!text) {
                hideTooltip();
                return;
            }
            tooltip.textContent = text;
            tooltip.classList.remove('is-hidden');
            var hostRect = chartNode.getBoundingClientRect();
            var tipRect = tooltip.getBoundingClientRect();
            var offsetX = 12;
            var offsetY = 12;
            var left = event.clientX - hostRect.left + offsetX;
            var top = event.clientY - hostRect.top + offsetY;
            if (left + tipRect.width > hostRect.width - 8) {
                left = Math.max(8, event.clientX - hostRect.left - tipRect.width - 12);
            }
            if (top + tipRect.height > hostRect.height - 8) {
                top = Math.max(8, event.clientY - hostRect.top - tipRect.height - 12);
            }
            tooltip.style.left = left.toFixed(0) + 'px';
            tooltip.style.top = top.toFixed(0) + 'px';
        }

        Array.prototype.forEach.call(chartNode.querySelectorAll('.ml-point[data-tip]'), function (point) {
            point.addEventListener('mouseenter', function (event) {
                showTooltip(event, point.getAttribute('data-tip') || '');
            });
            point.addEventListener('mousemove', function (event) {
                showTooltip(event, point.getAttribute('data-tip') || '');
            });
            point.addEventListener('mouseleave', hideTooltip);
            point.addEventListener('blur', hideTooltip);
        });
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
        var cYear = data.year_ml != null ? String(data.year_ml) : 'Compare-series';
        var dYear = data.year_model != null ? String(data.year_model) : cYear;
        var aPoints = rows.filter(function (row) { return row && row.a_value != null && !isNaN(Number(row.a_value)); }).length;
        var bPoints = rows.filter(function (row) { return row && row.b_value != null && !isNaN(Number(row.b_value)); }).length;
        var cPoints = rows.filter(function (row) { return row && row.c_value != null && !isNaN(Number(row.c_value)); }).length;
        var dPoints = rows.filter(function (row) { return row && row.d_value != null && !isNaN(Number(row.d_value)); }).length;
        var overlapBC = false;
        if (bPoints && cPoints) {
            var same = 0;
            var both = 0;
            rows.forEach(function (row) {
                if (!row || row.b_value == null || row.c_value == null) {
                    return;
                }
                var bVal = Number(row.b_value);
                var cVal = Number(row.c_value);
                if (isNaN(bVal) || isNaN(cVal)) {
                    return;
                }
                both += 1;
                if (Math.abs(bVal - cVal) < 1e-9 && String(row.b_source || '') === String(row.c_source || '')) {
                    same += 1;
                }
            });
            overlapBC = both > 0 && same === both;
        }

        if (!rows.length || (!aPoints && !bPoints)) {
            if (cPoints) {
                // Allow rendering chart when only Compare-series has points.
            } else {
                renderGuideHint(data, overlapBC);
                renderFallback(chartNode, fallbackNode, 'Нет данных для сравнения выбранных лет за выбранный месяц.');
                if (summaryNode) {
                    summaryNode.textContent = '';
                }
                return;
            }
        }

        if (!rows.length || (!aPoints && !bPoints && !cPoints && !dPoints)) {
            renderGuideHint(data, overlapBC);
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
            if (row && row.c_value != null) { values.push(Number(row.c_value)); }
            if (row && row.d_value != null) { values.push(Number(row.d_value)); }
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

        function buildPoints(key, pointClass, yearLabel, sourceKey) {
            var points = '';
            rows.forEach(function (row, i) {
                var raw = row ? row[key] : null;
                var val = raw == null ? null : Number(raw);
                if (val == null || isNaN(val)) {
                    return;
                }
                var dayText = row && row.day != null ? String(row.day) : '';
                var source = row && row[sourceKey] ? String(row[sourceKey]) : '';
                var sourceLabel = source === 'ml' ? 'ML' : (source === 'ml_model' ? 'ML-model (Poisson)' : 'факт');
                var valueText = String(Math.round(val * 100) / 100).replace('.', ',');
                var tip = 'Год: ' + yearLabel + ' | День: ' + dayText + ' | Значение: ' + valueText + ' | Источник: ' + sourceLabel;
                points += '<circle cx="' + x(i).toFixed(2) + '" cy="' + y(val).toFixed(2) + '" r="4.2" class="ml-point ' + pointClass + '" tabindex="0" data-tip="' + escapeHtml(tip) + '"></circle>';
            });
            return points;
        }

        var gridLines = '';
        var axisLabels = '';
        for (var step = 0; step <= 4; step += 1) {
            var value = yMin + ((yMax - yMin) * step / 4);
            var py = y(value);
            gridLines += '<line x1="' + padding.left + '" y1="' + py.toFixed(2) + '" x2="' + (width - padding.right) + '" y2="' + py.toFixed(2) + '" class="ml-grid-line"></line>';
            axisLabels += '<text x="' + (padding.left - 10) + '" y="' + (py + 4).toFixed(2) + '" text-anchor="end" class="ml-axis-label">' + escapeHtml(String(Math.round(value * 10) / 10).replace('.', ',')) + '</text>';
        }

        rows.forEach(function (row, idx) {
            var day = row ? row.day : '';
            if (day == null || day === '') {
                return;
            }
            var textClass = (Number(day) % 2 === 0) ? 'ml-axis-label ml-axis-label-muted' : 'ml-axis-label';
            axisLabels += '<text x="' + x(idx).toFixed(2) + '" y="' + (height - 16) + '" text-anchor="middle" class="' + textClass + '">' + escapeHtml(String(day)) + '</text>';
        });

        var svg = '<svg viewBox="0 0 ' + width + ' ' + height + '" class="ml-svg-chart" preserveAspectRatio="none">'
            + gridLines
            + '<line x1="' + padding.left + '" y1="' + (height - padding.bottom) + '" x2="' + (width - padding.right) + '" y2="' + (height - padding.bottom) + '" class="ml-axis-line"></line>'
            + '<line x1="' + padding.left + '" y1="' + padding.top + '" x2="' + padding.left + '" y2="' + (height - padding.bottom) + '" class="ml-axis-line"></line>';

        buildSegments('a_value').forEach(function (path) { svg += '<path d="' + path + '" class="ml-line-forecast"></path>'; });
        buildSegments('b_value').forEach(function (path) { svg += '<path d="' + path + '" class="ml-line-appg"></path>'; });
        buildSegments('c_value').forEach(function (path) {
            var className = overlapBC ? 'ml-line-compare-series ml-line-compare-series-overlap' : 'ml-line-compare-series';
            svg += '<path d="' + path + '" class="' + className + '"></path>';
        });
        buildSegments('d_value').forEach(function (path) { svg += '<path d="' + path + '" class="ml-line-poisson"></path>'; });
        svg += buildPoints('a_value', 'ml-forecast-point', aYear, 'a_source');
        svg += buildPoints('b_value', 'ml-appg-point', bYear, 'b_source');
        svg += buildPoints('c_value', 'ml-compare-series-point', 'Compare-series ' + cYear, 'c_source');
        svg += buildPoints('d_value', 'ml-poisson-point', 'ML-prog (Poisson) ' + dYear, 'd_source');
        svg += axisLabels + '</svg>';

        var modes = data.modes || {};
        var legendA = aYear + (modes.year_a === 'ml' ? ' (ML)' : (modes.year_a === 'mixed' ? ' (факт+ML)' : ' (факт)'));
        var legendB = bYear + (modes.year_b === 'ml' ? ' (ML)' : (modes.year_b === 'mixed' ? ' (факт+ML)' : ' (факт)'));
        var legendC = 'Compare-series ' + cYear + (modes.year_ml === 'ml' ? ' (ML)' : (modes.year_ml === 'mixed' ? ' (факт+ML)' : ' (факт)'));
        var legendD = 'ML-prog (Poisson) ' + dYear;

        chartNode.innerHTML = ''
            + '<div class="ml-chart-legend">'
            + '<span class="ml-chart-legend-item"><i data-legend-color="#0F766E"></i>' + escapeHtml(legendA) + '</span>'
            + '<span class="ml-chart-legend-item"><i data-legend-color="#B45309"></i>' + escapeHtml(legendB) + '</span>'
            + '<span class="ml-chart-legend-item"><i data-legend-color="#1D4ED8"></i>' + escapeHtml(legendC) + '</span>'
            + '<span class="ml-chart-legend-item"><i data-legend-color="#7C3AED"></i>' + escapeHtml(legendD) + '</span>'
            + '</div>'
            + '<div class="ml-chart-shell">' + svg + '</div>';
        applyLegendDecorators(chartNode);
        wirePointTooltips(chartNode);
        renderGuideHint(data, overlapBC);

        if (summaryNode) {
            var aSummary = data.a_summary || {};
            var bSummary = data.b_summary || {};
            var cSummary = data.c_summary || {};
            var dSummary = data.d_summary || {};
            var dQuality = data.d_quality || {};
            var qualityText = '';
            if (dQuality.quality_available === true) {
                qualityText = ' | Poisson quality: MAE ' + formatMetric(dQuality.mae)
                    + ' | RMSE ' + formatMetric(dQuality.rmse)
                    + ' | sMAPE ' + formatMetric(dQuality.smape) + '%'
                    + ' | n=' + String(dQuality.sample_size || 0)
                    + ' | folds=' + String(dQuality.folds_used || 0);
            } else {
                qualityText = ' | Poisson quality: недоступно (' + String(dQuality.reason || 'insufficient_history') + ')';
            }
            summaryNode.textContent = 'Год 1 (' + aYear + '): факт ' + String(aSummary.fact_days || 0) + ', ML ' + String(aSummary.ml_days || 0)
                + ' | Год 2 (' + bYear + '): факт ' + String(bSummary.fact_days || 0) + ', ML ' + String(bSummary.ml_days || 0)
                + ' | Compare-series (' + cYear + '): факт ' + String(cSummary.fact_days || 0) + ', ML ' + String(cSummary.ml_days || 0)
                + ' | ML-prog (Poisson): model_days ' + String(dSummary.model_days || 0) + ', clipped_days ' + String(dSummary.clipped_days || 0)
                + qualityText
                + (overlapBC ? ' | Compare-series совпадает с Год 2 для выбранных параметров' : '')
                + (modes.overall === 'ml_ml' ? ' | обе линии построены ML' : '')
                + (historyHasData ? '' : ' | нет входных данных');
        }
    }

    global.MlModelCharts = {
        renderCompareChart: renderCompareChart
    };
}(window));
