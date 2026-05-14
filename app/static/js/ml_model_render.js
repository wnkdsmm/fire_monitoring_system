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
        var availableTables = Array.isArray(filters && filters.available_tables) ? filters.available_tables : [];
        availableTables.forEach(function (item) {
            var value = String((item && item.value) || '').trim();
            if (!value || value === 'all') {
                return;
            }
            var matches = value.match(/(19\d{2}|20\d{2}|2100)/g) || [];
            matches.forEach(function (token) { push(token); });
        });
        if (result.length) {
            result.sort(function (a, b) { return b - a; });
        }
        return result;
    }

    function ensureYearInList(years, candidate) {
        var year = parseYear(candidate);
        if (year == null) {
            return years;
        }
        if (years.indexOf(year) === -1) {
            years.push(year);
            years.sort(function (a, b) { return b - a; });
        }
        return years;
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

    function currentUserYear() {
        return new Date().getFullYear();
    }

    function buildFutureYearOptions() {
        var base = currentUserYear();
        var result = [];
        for (var step = 0; step <= 3; step += 1) {
            var year = base + step;
            result.push({ value: String(year), label: String(year) });
        }
        return result;
    }

    function resolveYearPair(years, rawYearA, rawYearB) {
        var explicitYearA = String(rawYearA || '').trim();
        var explicitYearB = String(rawYearB || '').trim();
        if (!years.length) {
            var fallbackNow = String(new Date().getFullYear());
            return {
                yearA: explicitYearA || fallbackNow,
                yearB: explicitYearB || explicitYearA || fallbackNow
            };
        }
        var fallbackA = years.length ? String(years[0]) : '2024';
        var fallbackB = years.length > 1 ? String(years[1]) : fallbackA;
        var allowed = {};
        years.forEach(function (year) { allowed[String(year)] = true; });
        var yearA = explicitYearA;
        var yearB = explicitYearB;
        if (!allowed[yearA]) {
            yearA = fallbackA;
        }
        if (!allowed[yearB]) {
            yearB = fallbackB;
        }
        return { yearA: yearA, yearB: yearB };
    }

    function setBusy(isBusy) {
        var form = byId('mlModelForm');
        if (!form) {
            return;
        }
        form.classList.toggle('is-loading', !!isBusy);
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
        var filters = (currentData && currentData.filters) || {};
        var tableNames = Array.isArray(filters.table_names)
            ? filters.table_names.map(function (value) { return String(value || '').trim(); }).filter(function (value) { return value.length > 0; })
            : [];
        var tableName = String(filters.table_name || '').trim() || 'all';
        var cause = String(filters.cause || '').trim() || 'all';
        var objectCategory = String(filters.object_category || '').trim() || 'all';
        var month = byId('mlMonthFilter') ? String(byId('mlMonthFilter').value || '').trim() : '';
        var yearA = byId('mlYearAFilter') ? String(byId('mlYearAFilter').value || '').trim() : '';
        var yearB = byId('mlYearBFilter') ? String(byId('mlYearBFilter').value || '').trim() : '';
        var yearMl = byId('mlFutureYearFilter') ? String(byId('mlFutureYearFilter').value || '').trim() : '';
        var years = collectAvailableYears(filters);
        ensureYearInList(years, yearA);
        ensureYearInList(years, yearB);
        var resolved = resolveYearPair(years, yearA, yearB);
        var defaultYearMl = String(currentUserYear());
        return {
            table_name: tableName,
            table_names: tableNames,
            cause: cause,
            object_category: objectCategory,
            month: month || String(new Date().getMonth() + 1),
            year_a: resolved.yearA,
            year_b: resolved.yearB,
            year_ml: yearMl || defaultYearMl
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
                + '<span class="hero-tag">Сравнение: <strong>факт и ML-достройка</strong></span>'
                + '<span class="hero-tag">Горизонт: <strong>выбранный месяц</strong></span>';
        }
        if (stats) {
            stats.innerHTML = ''
                + '<article class="hero-stat-card">'
                + '<span class="hero-stat-label">Исторический период</span>'
                + '<strong class="hero-stat-value">' + escapeHtml(summary.history_period_label || '-') + '</strong>'
                + '<span class="hero-stat-foot">Данные, доступные для сравнения по дням месяца.</span>'
                + '</article>'
                + '<article class="hero-stat-card">'
                + '<span class="hero-stat-label">Записей в срезе</span>'
                + '<strong class="hero-stat-value">' + escapeHtml(summary.fires_count_display || '0') + '</strong>'
                + '<span class="hero-stat-foot">Количество пожаров после фильтров таблиц, причины и категории.</span>'
                + '</article>';
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
        ensureYearInList(years, compare.year_a || filters.year_a);
        ensureYearInList(years, compare.year_b || filters.year_b);
        if (!years.length) {
            var fallbackYears = [];
            var yearFromCompareA = parseYear(compare.year_a);
            var yearFromCompareB = parseYear(compare.year_b);
            if (yearFromCompareA != null) {
                fallbackYears.push(yearFromCompareA);
            }
            if (yearFromCompareB != null && fallbackYears.indexOf(yearFromCompareB) === -1) {
                fallbackYears.push(yearFromCompareB);
            }
            fallbackYears.sort(function (a, b) { return b - a; });
            years = fallbackYears;
        }
        var month = String(compare.month || filters.compare_month || (new Date().getMonth() + 1));
        var resolved = resolveYearPair(years, compare.year_a || filters.year_a, compare.year_b || filters.year_b);
        var yearA = resolved.yearA;
        var yearB = resolved.yearB;
        var yearMl = String(compare.year_ml || filters.year_ml || currentUserYear());

        setSelectOptions('mlMonthFilter', buildMonthOptions(), month, 'Месяц');
        setSelectOptions('mlYearAFilter', buildYearOptions(years), yearA, 'Год 1');
        setSelectOptions('mlYearBFilter', buildYearOptions(years), yearB, 'Год 2');
        setSelectOptions('mlFutureYearFilter', buildFutureYearOptions(), yearMl, 'Год ML');

        renderHero(data);
        charts.renderCompareChart(compare, 'mlCompareChart', 'mlCompareChartFallback', 'mlCompareChartSummary');
    }

    async function refreshCompareSeriesOnly() {
        hideError();
        setBusy(true);
        try {
            var request = collectFormFilters();
            var seriesPromise = api.fetchMlCompareSeries({
                useLocationSearch: false,
                buildPayload: function () { return request; }
            });
            var causesPromise = api.fetchMlCausesChart({
                useLocationSearch: false,
                buildPayload: function () { return request; }
            });
            var seriesResponse = await seriesPromise;
            var payload = seriesResponse && seriesResponse.payload ? seriesResponse.payload : {};
            var result = payload.result || {};
            if (!result.compare_series || !Array.isArray(result.compare_series.rows)) {
                showError('Нет данных для сравнения выбранных лет за выбранный месяц.');
                charts.renderCompareChart({}, 'mlCompareChart', 'mlCompareChartFallback', 'mlCompareChartSummary');
                charts.renderCausesChart({}, 'mlCausesChart');
                return;
            }
            applyData(Object.assign(
                {},
                currentData || {},
                {
                    filters: Object.assign({}, currentData && currentData.filters ? currentData.filters : {}, result.filters || {}),
                    compare_series: result.compare_series
                }
            ));
            try {
                var causesResponse = await causesPromise;
                var causesResult = (causesResponse && causesResponse.payload && causesResponse.payload.result) || {};
                charts.renderCausesChart(causesResult, 'mlCausesChart');
            } catch (_e) {
                charts.renderCausesChart({}, 'mlCausesChart');
            }
        } catch (error) {
            showError((error && error.message) ? error.message : 'Нет данных для сравнения выбранных лет за выбранный месяц.');
            charts.renderCompareChart({}, 'mlCompareChart', 'mlCompareChartFallback', 'mlCompareChartSummary');
            charts.renderCausesChart({}, 'mlCausesChart');
        } finally {
            setBusy(false);
        }
    }

    function wireEvents() {
        ['mlMonthFilter', 'mlYearAFilter', 'mlYearBFilter'].forEach(function (id) {
            var node = byId(id);
            if (node) {
                node.addEventListener('change', refreshCompareSeriesOnly);
            }
        });
        var futureYearNode = byId('mlFutureYearFilter');
        if (futureYearNode) {
            futureYearNode.addEventListener('change', refreshCompareSeriesOnly);
        }
    }

    function init() {
        applyData(global.__FIRE_ML_INITIAL__ || {});
        wireEvents();
        refreshCompareSeriesOnly();
    }

    global.MlModelRender = {
        init: init,
        refreshCompareSeriesOnly: refreshCompareSeriesOnly
    };
}(window));
