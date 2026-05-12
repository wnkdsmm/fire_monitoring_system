(function (global) {
    var shared = global.FireUi || {};
    var byId = shared.byId;
    var setSelectOptions = shared.setSelectOptions;
    var escapeHtml = shared.escapeHtml;
    var api = global.MlModelApi || {};
    var charts = global.MlModelCharts || {};

    var currentData = null;

    function parseYear(value) {
        var n = Number(String(value == null ? '' : value).trim());
        return Number.isFinite(n) ? Math.trunc(n) : null;
    }

    function collectAvailableYears(filters) {
        var result = [];
        var seen = {};
        var push = function (value) {
            var year = parseYear(value);
            if (year == null || seen[year]) {
                return;
            }
            seen[year] = true;
            result.push(year);
        };
        var availableYears = Array.isArray(filters && filters.available_years) ? filters.available_years : [];
        availableYears.forEach(function (item) { push(item && typeof item === 'object' ? item.value : item); });
        if (!result.length) {
            for (var year = 2026; year >= 1990; year -= 1) {
                result.push(year);
            }
        } else {
            result.sort(function (a, b) { return b - a; });
        }
        return result;
    }

    function buildMonthOptions() {
        return [
            { value: '1', label: 'Январь' }, { value: '2', label: 'Февраль' }, { value: '3', label: 'Март' },
            { value: '4', label: 'Апрель' }, { value: '5', label: 'Май' }, { value: '6', label: 'Июнь' },
            { value: '7', label: 'Июль' }, { value: '8', label: 'Август' }, { value: '9', label: 'Сентябрь' },
            { value: '10', label: 'Октябрь' }, { value: '11', label: 'Ноябрь' }, { value: '12', label: 'Декабрь' }
        ];
    }

    function buildYearOptions(years) {
        return years.map(function (year) { return { value: String(year), label: String(year) }; });
    }

    function setBusy(isBusy) {
        var button = byId('mlRefreshButton');
        if (!button) {
            return;
        }
        button.disabled = !!isBusy;
        button.classList.toggle('is-loading', !!isBusy);
    }

    function showError(message) {
        var node = byId('mlCompareError');
        if (!node) {
            return;
        }
        node.textContent = message || 'Нет данных для сравнения.';
        node.classList.remove('is-hidden');
    }

    function hideError() {
        var node = byId('mlCompareError');
        if (!node) {
            return;
        }
        node.textContent = '';
        node.classList.add('is-hidden');
    }

    function collectFormFilters() {
        return {
            table_name: 'all',
            table_names: [],
            cause: 'all',
            object_category: 'all',
            month: byId('mlMonthFilter') ? String(byId('mlMonthFilter').value || '').trim() : '',
            year_a: byId('mlYearAFilter') ? String(byId('mlYearAFilter').value || '').trim() : '',
            year_b: byId('mlYearBFilter') ? String(byId('mlYearBFilter').value || '').trim() : ''
        };
    }

    function renderHero(data) {
        var summary = (data && data.summary) || {};
        var description = byId('mlModelDescription');
        var tags = byId('mlHeroTags');
        var stats = byId('mlHeroStats');
        if (description) {
            description.textContent = summary.hero_summary || 'После загрузки здесь появится краткий вывод по ожидаемому числу пожаров и прогнозной нагрузке.';
        }
        if (tags) {
            tags.innerHTML = ''
                + '<span class="hero-tag">Таблица: <strong>' + escapeHtml(summary.selected_table_label || 'Все таблицы') + '</strong></span>'
                + '<span class="hero-tag">Главный фактор модели: <strong>' + escapeHtml(summary.top_feature_label || '-') + '</strong></span>'
                + '<span class="hero-tag">Событие пожара: <strong>' + escapeHtml(summary.event_probability_enabled ? (summary.average_event_probability_display || '—') : 'не показано') + '</strong></span>';
        }
        if (stats) {
            stats.innerHTML = ''
                + '<article class="hero-stat-card">'
                + '<span class="hero-stat-label">Средний ожидаемый день</span>'
                + '<strong class="hero-stat-value">' + escapeHtml(summary.average_expected_count_display || '0') + '</strong>'
                + '<span class="hero-stat-foot">Средняя дневная интенсивность на выбранном горизонте прогноза.</span>'
                + '</article>'
                + '<article class="hero-stat-card">'
                + '<span class="hero-stat-label">День с максимальной нагрузкой</span>'
                + '<strong class="hero-stat-value">' + escapeHtml(summary.peak_expected_count_display || '0') + '</strong>'
                + '<span class="hero-stat-foot">Максимальное ожидаемое число пожаров: ' + escapeHtml(summary.peak_expected_count_day_display || '-') + '.</span>'
                + '</article>';
        }
    }

    function renderQuality(data) {
        var quality = (data && data.quality_assessment) || {};
        var title = byId('mlQualityTitle');
        var subtitle = byId('mlQualitySubtitle');
        var cards = byId('mlQualityMetricCards');
        var tableShell = byId('mlCountTableShell');
        if (title) {
            title.textContent = quality.title || 'Валидация качества ML-прогноза количества пожаров';
        }
        if (subtitle) {
            subtitle.textContent = quality.subtitle || 'Метрики рассчитаны на единой исторической выборке и показывают точность прогноза количества пожаров по дням.';
        }
        if (cards) {
            var rows = Array.isArray(quality.metric_cards) ? quality.metric_cards : [];
            cards.innerHTML = rows.map(function (item) {
                return ''
                    + '<article class="stat-card">'
                    + '<span class="stat-label">' + escapeHtml(item.label || '-') + '</span>'
                    + '<strong class="stat-value">' + escapeHtml(item.value || '-') + '</strong>'
                    + '<span class="stat-foot">' + escapeHtml(item.meta || '') + '</span>'
                    + '</article>';
            }).join('');
        }
        if (tableShell) {
            var countTable = quality.count_table || {};
            var countRows = Array.isArray(countTable.rows) ? countTable.rows : [];
            if (!countRows.length) {
                tableShell.innerHTML = '<div class="mini-empty">' + escapeHtml(countTable.empty_message || 'Нет данных для сравнения методов.') + '</div>';
                return;
            }
            tableShell.innerHTML = ''
                + '<table class="forecast-table forecast-table-ml">'
                + '<thead><tr><th>Метод</th><th>Роль</th><th>MAE</th><th>RMSE</th><th>sMAPE</th><th>Девиация Пуассона</th><th>ΔMAE к базовой модели</th><th>Статус</th></tr></thead>'
                + '<tbody>' + countRows.map(function (row) {
                    return '<tr>'
                        + '<td>' + escapeHtml(row.method_label || '-') + '</td>'
                        + '<td>' + escapeHtml(row.role_label || '-') + '</td>'
                        + '<td>' + escapeHtml(row.mae_display || '-') + '</td>'
                        + '<td>' + escapeHtml(row.rmse_display || '-') + '</td>'
                        + '<td>' + escapeHtml(row.smape_display || '-') + '</td>'
                        + '<td>' + escapeHtml(row.poisson_display || '-') + '</td>'
                        + '<td>' + escapeHtml(row.mae_delta_display || '-') + '</td>'
                        + '<td>' + escapeHtml(row.selection_label || '-') + '</td>'
                        + '</tr>';
                }).join('') + '</tbody></table>';
        }
    }

    function applyData(data) {
        if (!data) {
            return;
        }
        currentData = data;
        var filters = data.filters || {};
        var compare = data.compare_series || {};

        var years = collectAvailableYears(filters);
        var month = String(compare.month || filters.compare_month || (new Date().getMonth() + 1));
        var yearA = String(compare.year_a || filters.year_a || '2024');
        var yearB = String(compare.year_b || filters.year_b || '2025');

        setSelectOptions('mlMonthFilter', buildMonthOptions(), month, 'Месяц');
        setSelectOptions('mlYearAFilter', buildYearOptions(years), yearA, 'Год A');
        setSelectOptions('mlYearBFilter', buildYearOptions(years), yearB, 'Год B');

        renderHero(data);
        renderQuality(data);
        charts.renderCompareChart(compare, 'mlCompareChart', 'mlCompareChartFallback', 'mlCompareChartSummary');
    }

    async function refreshCompareSeriesOnly() {
        hideError();
        setBusy(true);
        try {
            var request = collectFormFilters();
            var response = await api.fetchMlCompareSeries({
                useLocationSearch: false,
                buildPayload: function () { return request; }
            });
            var payload = response && response.payload ? response.payload : {};
            var result = payload.result || {};
            if (!result.compare_series || !Array.isArray(result.compare_series.rows)) {
                showError('Нет данных для сравнения выбранных лет за выбранный месяц.');
                charts.renderCompareChart({}, 'mlCompareChart', 'mlCompareChartFallback', 'mlCompareChartSummary');
                return;
            }
            applyData({
                filters: Object.assign({}, currentData && currentData.filters ? currentData.filters : {}, result.filters || {}),
                compare_series: result.compare_series
            });
        } catch (error) {
            showError((error && error.message) ? error.message : 'Нет данных для сравнения выбранных лет за выбранный месяц.');
            charts.renderCompareChart({}, 'mlCompareChart', 'mlCompareChartFallback', 'mlCompareChartSummary');
        } finally {
            setBusy(false);
        }
    }

    function wireEvents() {
        var form = byId('mlModelForm');
        if (form) {
            form.addEventListener('submit', function (event) {
                event.preventDefault();
                refreshCompareSeriesOnly();
            });
        }
        ['mlMonthFilter', 'mlYearAFilter', 'mlYearBFilter'].forEach(function (id) {
            var node = byId(id);
            if (node) {
                node.addEventListener('change', refreshCompareSeriesOnly);
            }
        });
    }

    function init() {
        applyData(global.__FIRE_ML_INITIAL__ || {});
        wireEvents();
    }

    global.MlModelRender = {
        init: init,
        refreshCompareSeriesOnly: refreshCompareSeriesOnly
    };
}(window));
