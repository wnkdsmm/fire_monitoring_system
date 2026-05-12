(function (global) {
    var shared = global.FireUi || {};
    var api = global.MlModelApi || {};
    var charts = global.MlModelCharts || {};

    var byId = shared.byId;
    var createTimerGroup = shared.createTimerGroup;
    var escapeHtml = shared.escapeHtml;
    var renderMetricCards = shared.renderMetricCards;
    var setHref = shared.setHref;
    var setSectionHidden = shared.setSectionHidden;
    var setSelectOptions = shared.setSelectOptions;
    var setStepProgress = shared.setStepProgress;
    var setText = shared.setText;
    var setValue = shared.setValue;
    var setHidden = shared.setHidden;
    var createTableChecklist = shared.createTableChecklist;

    var currentMlData = null;
    var tableCheckboxDebounceTimer = null;
    var latestCompareRequest = null;
    var compareRequestSeq = 0;
    var keepUserCompareSelection = false;
    var progressTimers = createTimerGroup();
    var appgDefaultInitialized = false;
    var mlTableChecklist = typeof createTableChecklist === 'function'
        ? createTableChecklist({
            rootId: 'mlTableFilter',
            menuId: 'mlTableFilterMenu',
            toggleId: 'mlTableFilterToggle',
            summaryId: 'mlTableFilterSummary',
            selectedListId: 'mlTableFilterSelectedList',
            itemClassName: 'ml-table-checklist-item'
        })
        : null;
    var progressSteps = [
        {
            label: 'Загрузка данных',
            lead: 'Загружаем данные ML-прогноза',
            message: 'Получаем выбранный срез и обновляем параметры страницы.'
        },
        {
            label: 'Агрегация',
            lead: 'Агрегируем историю',
            message: 'Собираем дневной ряд, фильтры и доступные признаки.'
        },
        {
            label: 'Обучение / валидация',
            lead: 'Обучение и валидация',
            message: 'Считаем backtesting, прогноз и итоговые таблицы.'
        },
        {
            label: 'Построение визуализаций',
            lead: 'Обновляем визуализации',
            message: 'Подставляем графики, таблицы и карточки результата.'
        }
    ];

    function normalizeRangeDisplay(value) {
        var text = String(value || '').trim();
        return text.replace(/^\d+\s*%\s*:\s*/, '');
    }

    function parseYear(value) {
        var normalized = String(value == null ? '' : value).trim();
        if (!normalized) {
            return null;
        }
        var year = Number(normalized);
        if (!Number.isFinite(year)) {
            return null;
        }
        year = Math.trunc(year);
        return year > 0 ? year : null;
    }

    function normalizeCompareValue(value) {
        var normalized = String(value == null ? '' : value).trim();
        return normalized;
    }

    function extractCompareFromResponse(data) {
        var safeData = data || {};
        var filters = safeData.filters || {};
        var compareSeries = safeData.compare_series || {};
        var responseYearA = normalizeCompareValue(
            filters.year_a != null ? filters.year_a : compareSeries.year_a
        );
        var responseYearB = normalizeCompareValue(
            filters.year_b != null ? filters.year_b : compareSeries.year_b
        );
        return {
            year_a: responseYearA,
            year_b: responseYearB
        };
    }

    function extractCompareFromRequestBody(requestBody) {
        var body = requestBody || {};
        return {
            year_a: normalizeCompareValue(body.year_a),
            year_b: normalizeCompareValue(body.year_b)
        };
    }

    function shouldLogCompareMismatch(expected, actual) {
        if (!expected) {
            return false;
        }
        if (!expected.year_a && !expected.year_b) {
            return false;
        }
        if (!actual) {
            return true;
        }
        return expected.year_a !== actual.year_a || expected.year_b !== actual.year_b;
    }

    function collectAvailableYears(filters) {
        var years = [];
        var seen = {};
        var pushYear = function (value) {
            var year = parseYear(value);
            if (year == null || seen[year]) {
                return;
            }
            seen[year] = true;
            years.push(year);
        };

        var availableYears = Array.isArray(filters && filters.available_years) ? filters.available_years : [];
        availableYears.forEach(function (item) {
            if (item && typeof item === 'object') {
                pushYear(item.value);
                return;
            }
            pushYear(item);
        });

        return years;
    }

    function buildYearOptions(selectedYear, config) {
        var settings = config || {};
        var years = Array.isArray(settings.years) ? settings.years.slice() : [];
        var includeEmptyOption = settings.includeEmptyOption !== false;
        var nowYear = new Date().getFullYear();
        var defaultMinYear = 1990;
        var defaultMaxYear = nowYear + 1;

        var normalizedYears = years
            .map(parseYear)
            .filter(function (value) { return value != null; });
        var selected = parseYear(selectedYear);
        if (selected != null) {
            normalizedYears.push(selected);
        }
        if (Array.isArray(settings.extraYears)) {
            settings.extraYears.forEach(function (value) {
                var parsed = parseYear(value);
                if (parsed != null) {
                    normalizedYears.push(parsed);
                }
            });
        }

        var minYear = null;
        var maxYear = null;
        normalizedYears.forEach(function (year) {
            if (minYear == null || year < minYear) {
                minYear = year;
            }
            if (maxYear == null || year > maxYear) {
                maxYear = year;
            }
        });

        if (settings.expandToDefault || minYear == null || maxYear == null) {
            minYear = (minYear == null) ? defaultMinYear : Math.min(minYear, defaultMinYear);
            maxYear = (maxYear == null) ? defaultMaxYear : Math.max(maxYear, defaultMaxYear);
        }

        var options = [{ value: '', label: 'Текущий режим' }];
        if (!includeEmptyOption) {
            options = [];
        }
        for (var year = maxYear; year >= minYear; year -= 1) {
            options.push({ value: String(year), label: String(year) });
        }
        return options;
    }

    function buildMonthOptions() {
        return [
            { value: '', label: 'Все месяцы' },
            { value: '1', label: 'Январь' },
            { value: '2', label: 'Февраль' },
            { value: '3', label: 'Март' },
            { value: '4', label: 'Апрель' },
            { value: '5', label: 'Май' },
            { value: '6', label: 'Июнь' },
            { value: '7', label: 'Июль' },
            { value: '8', label: 'Август' },
            { value: '9', label: 'Сентябрь' },
            { value: '10', label: 'Октябрь' },
            { value: '11', label: 'Ноябрь' },
            { value: '12', label: 'Декабрь' }
        ];
    }

    function renderSidebarStatus(data) {
        var container = byId('mlSidebarStatus');
        if (!container) {
            return;
        }

        var summary = data && data.summary ? data.summary : {};
        var badgeClass = 'status-badge';
        if (data && data.has_data && !data.error_message) {
            badgeClass += ' status-badge-live';
        }

        var badgeLabel = 'Нужно уточнить фильтры';
        if (data && data.error_message) {
            badgeLabel = 'Требуется повторный расчет';
        } else if ((api.isFetching && api.isFetching()) || (data && data.bootstrap_mode === 'deferred')) {
            badgeLabel = 'Собираем ML-прогноз';
        } else if (data && data.has_data) {
            badgeLabel = 'ML-прогноз готов';
        }

        container.innerHTML = ''
            + '<span class="' + badgeClass + '">' + escapeHtml(badgeLabel) + '</span>'
            + '<div class="status-line"><span>Модель по числу пожаров</span><strong>' + escapeHtml(summary.count_model_label || 'Регрессия Пуассона') + '</strong></div>'
            + '<div class="status-line"><span>Событие пожара</span><strong>' + escapeHtml(summary.event_model_label || 'Не обучен') + '</strong></div>'
            + '<div class="status-line"><span>Проверка на истории</span><strong>' + escapeHtml(summary.backtest_method_label || 'Проверка на истории не выполнена') + '</strong></div>'
            + '<div class="status-line"><span>Период</span><strong>' + escapeHtml(summary.history_period_label || 'Нет данных') + '</strong></div>';
    }

    function renderHero(data) {
        var summary = data.summary || {};
        setText('mlModelDescription', summary.hero_summary || data.model_description || 'После загрузки здесь появится краткий вывод по ожидаемому числу пожаров и надежности расчета.');

        var heroTags = byId('mlHeroTags');
        if (heroTags) {
            heroTags.innerHTML = ''
                + '<span class="hero-tag">Таблица: <strong>' + escapeHtml(summary.selected_table_label || 'Нет таблицы') + '</strong></span>'
                + '<span class="hero-tag">Главный фактор модели: <strong>' + escapeHtml(summary.top_feature_label || '-') + '</strong></span>'
                + '<span class="hero-tag">'
                + (summary.event_probability_enabled
                    ? 'Средняя вероятность P(>=1 пожара): <strong>' + escapeHtml(summary.average_event_probability_display || '—') + '</strong>'
                    : 'Событие пожара: <strong>не показано</strong>')
                + '</span>';
        }

        var heroStats = byId('mlHeroStats');
        if (heroStats) {
            heroStats.innerHTML = ''
                + '<article class="hero-stat-card">'
                + '<span class="hero-stat-label">Средний ожидаемый день</span>'
                + '<strong class="hero-stat-value">' + escapeHtml(summary.average_expected_count_display || '0') + '</strong>'
                + '<span class="hero-stat-foot">Средняя дневная интенсивность на выбранном горизонте прогноза.</span>'
                + '</article>'
                + '<article class="hero-stat-card hero-stat-card-soft">'
                + '<span class="hero-stat-label">День с максимальной нагрузкой</span>'
                + '<strong class="hero-stat-value">' + escapeHtml(summary.peak_expected_count_display || '0') + '</strong>'
                + '<span class="hero-stat-foot">Максимальное ожидаемое число пожаров: ' + escapeHtml(summary.peak_expected_count_day_display || '-') + '.</span>'
                + '</article>';
        }
    }

    function renderSummaryCards(summary) {
        var container = byId('mlStatsGrid');
        if (!container) {
            return;
        }

        container.innerHTML = ''
            + '<article class="stat-card stat-card-accent">'
            + '<span class="stat-label">Пожаров в обучении</span>'
            + '<strong class="stat-value">' + escapeHtml(summary.fires_count_display || '0') + '</strong>'
            + '<span class="stat-foot">После выбранных фильтров.</span>'
            + '</article>'
            + '<article class="stat-card">'
            + '<span class="stat-label">Длина истории</span>'
            + '<strong class="stat-value">' + escapeHtml(summary.history_days_display || '0') + '</strong>'
            + '<span class="stat-foot">Непрерывный дневной ряд с нулями между пожарами.</span>'
            + '</article>'
            + '<article class="stat-card">'
            + '<span class="stat-label">Ожидаемо на всём горизонте</span>'
            + '<strong class="stat-value">' + escapeHtml(summary.predicted_total_display || '0') + '</strong>'
            + '<span class="stat-foot">Ожидаемое число пожаров на всем горизонте.</span>'
            + '</article>'
            + '<article class="stat-card">'
            + '<span class="stat-label">Дней с повышенной нагрузкой</span>'
            + '<strong class="stat-value">' + escapeHtml(summary.elevated_risk_days_display || '0') + '</strong>'
            + '<span class="stat-foot">Количество дней, где риск-индекс не ниже 75/100.</span>'
            + '</article>';
    }

    function renderOptionalMetricCards(sectionId, containerId, items, emptyMessage) {
        var hasItems = Array.isArray(items) && items.length;
        var container = byId(containerId);
        setSectionHidden(sectionId, !hasItems);
        if (!container) {
            return;
        }
        if (!hasItems) {
            container.innerHTML = '';
            return;
        }
        renderMetricCards(containerId, items, emptyMessage || '');
    }

    function renderClassBalanceWarning(containerId, classBalanceWarning) {
        var container = byId(containerId);
        if (!container) {
            return;
        }

        var warningNode = container.querySelector('[data-role="class-balance-warning"]');
        if (!warningNode) {
            warningNode = document.createElement('p');
            warningNode.setAttribute('data-role', 'class-balance-warning');
            warningNode.className = 'help is-warning is-hidden';
            warningNode.textContent = 'Классы несбалансированы (< 10% или > 90%). F1 может быть неинформативным.';
        }

        var f1Card = null;
        Array.prototype.forEach.call(container.querySelectorAll('.stat-card'), function (card) {
            if (f1Card) {
                return;
            }
            var labelNode = card.querySelector('.stat-label');
            if (!labelNode) {
                return;
            }
            var labelText = String(labelNode.textContent || '').trim().toUpperCase();
            if (labelText === 'F1') {
                f1Card = card;
            }
        });

        if (f1Card) {
            f1Card.insertAdjacentElement('afterend', warningNode);
        } else if (!warningNode.parentElement) {
            container.appendChild(warningNode);
        }

        warningNode.classList.toggle('is-hidden', !classBalanceWarning);
    }

    function renderImportanceNote(note) {
        var node = byId('mlImportanceChartNote');
        if (!node) {
            return;
        }
        node.textContent = note || '';
        node.classList.toggle('is-hidden', !note);
    }

    function renderCriticalNotes(items) {
        var panel = byId('mlNotesPanel');
        var container = byId('mlNotesList');
        var notes = Array.isArray(items)
            ? items.filter(function (item) { return item != null && String(item).trim(); }).slice(0, 2)
            : [];
        if (!panel || !container) {
            return;
        }

        panel.classList.toggle('is-hidden', !notes.length);
        container.innerHTML = notes.map(function (item) {
            return '<li>' + escapeHtml(item) + '</li>';
        }).join('');
    }

    function getSelectedTableNamesFromForm() {
        if (mlTableChecklist && typeof mlTableChecklist.getSelectedValues === 'function') {
            return mlTableChecklist.getSelectedValues();
        }
        return [];
    }

    function renderTableChecklist(options, selectedTableNames) {
        if (mlTableChecklist && typeof mlTableChecklist.renderChecklist === 'function') {
            mlTableChecklist.renderChecklist(options, selectedTableNames);
        }
    }

    function setTableChecklistOpen(isOpen) {
        if (mlTableChecklist && typeof mlTableChecklist.setOpen === 'function') {
            mlTableChecklist.setOpen(isOpen);
        }
    }

    function renderCountTable(table) {
        var container = byId('mlCountTableShell');
        var safeTable = table || {};
        var rows = Array.isArray(safeTable.rows) ? safeTable.rows : [];
        if (!container) {
            return;
        }

        if (!rows.length) {
            container.innerHTML = '<div class="mini-empty">' + escapeHtml(safeTable.empty_message || 'Сравнение baseline, сценарного прогноза и count-моделей появится после проверки на истории.') + '</div>';
            return;
        }

        container.innerHTML = ''
            + '<table class="forecast-table">'
            + '<thead><tr><th>Метод</th><th>Роль</th><th>MAE</th><th>RMSE</th><th>sMAPE</th><th>Девиация Пуассона</th><th>ΔMAE к базовой модели</th><th>Статус</th></tr></thead>'
            + '<tbody>' + rows.map(function (row) {
                return ''
                    + '<tr>'
                    + '<td data-label="Метод">' + escapeHtml(row.method_label || '-') + '</td>'
                    + '<td data-label="Роль">' + escapeHtml(row.role_label || '-') + '</td>'
                    + '<td data-label="MAE">' + escapeHtml(row.mae_display || '-') + '</td>'
                    + '<td data-label="RMSE">' + escapeHtml(row.rmse_display || '-') + '</td>'
                    + '<td data-label="SMAPE">' + escapeHtml(row.smape_display || '-') + '</td>'
                    + '<td data-label="Девиация Пуассона">' + escapeHtml(row.poisson_display || '-') + '</td>'
                    + '<td data-label="MAE к базовой модели">' + escapeHtml(row.mae_delta_display || '-') + '</td>'
                    + '<td data-label="Статус">' + escapeHtml(row.selection_label || '-') + '</td>'
                    + '</tr>';
            }).join('') + '</tbody></table>';
    }

    function renderForecastTable(rows) {
        var container = byId('mlForecastTableShell');
        if (!container) {
            return;
        }

        if (!Array.isArray(rows) || !rows.length) {
            container.innerHTML = '<div class="mini-empty">После обучения здесь появится прогноз по будущим датам.</div>';
            return;
        }

        container.innerHTML = ''
            + '<table class="forecast-table forecast-table-ml">'
            + '<colgroup><col style="width:22%"><col style="width:22%"><col style="width:56%"></colgroup>'
            + '<thead><tr><th>Дата</th><th>Ожидаемое число пожаров</th><th>Диапазон</th></tr></thead>'
            + '<tbody>' + rows.map(function (row) {
                return ''
                    + '<tr>'
                    + '<td data-label="Дата">' + escapeHtml(row.date_display || '-') + '</td>'
                    + '<td data-label="Ожидаемое число пожаров">' + escapeHtml(row.forecast_value_display || '0') + '</td>'
                    + '<td data-label="Диапазон">' + escapeHtml(normalizeRangeDisplay(row.range_display || '—')) + '</td>'
                    + '</tr>';
            }).join('') + '</tbody></table>';
    }

    function renderFeatureCards(items) {
        var container = byId('mlFeatureCards');
        if (!container) {
            return;
        }

        if (!Array.isArray(items) || !items.length) {
            container.innerHTML = '<div class="mini-empty">После расчета здесь появятся данные, на которых реально держится модель.</div>';
            return;
        }

        container.innerHTML = items.map(function (feature) {
            return ''
                + '<article class="forecast-feature-card status-' + escapeHtml(feature.status || 'missing') + '">'
                + '<div class="forecast-feature-head">'
                + '<strong>' + escapeHtml(feature.label || '-') + '</strong>'
                + '<span class="forecast-badge">' + escapeHtml(feature.status_label || '-') + '</span>'
                + '</div>'
                + '<p>' + escapeHtml(feature.description || '') + '</p>'
                + '</article>';
        }).join('');
    }

    function renderStatsSkeletons() {
        var container = byId('mlStatsGrid');
        if (!container) {
            return;
        }

        container.innerHTML = [0, 1, 2, 3].map(function (index) {
            return ''
                + '<article class="stat-card' + (index === 0 ? ' stat-card-accent' : '') + ' ml-skeleton-card">'
                + '<span class="ml-skeleton-line short"></span>'
                + '<span class="ml-skeleton-line value"></span>'
                + '<span class="ml-skeleton-line long"></span>'
                + '</article>';
        }).join('');
    }

    function renderCardSkeletons(containerId, count) {
        var container = byId(containerId);
        if (!container) {
            return;
        }

        var items = [];
        for (var index = 0; index < count; index += 1) {
            items.push(''
                + '<article class="stat-card ml-skeleton-card">'
                + '<span class="ml-skeleton-line short"></span>'
                + '<span class="ml-skeleton-line value"></span>'
                + '<span class="ml-skeleton-line long"></span>'
                + '</article>');
        }
        container.innerHTML = items.join('');
    }

    function renderTableSkeleton(containerId, columns, rows) {
        var container = byId(containerId);
        if (!container) {
            return;
        }

        var rowHtml = [];
        for (var rowIndex = 0; rowIndex < rows; rowIndex += 1) {
            var cells = [];
            for (var columnIndex = 0; columnIndex < columns; columnIndex += 1) {
                cells.push('<span class="ml-skeleton-table-cell"></span>');
            }
            rowHtml.push('<div class="ml-skeleton-table-row" style="--ml-skeleton-cols:' + columns + '">' + cells.join('') + '</div>');
        }
        container.innerHTML = '<div class="ml-skeleton-table">' + rowHtml.join('') + '</div>';
    }

    function renderFeatureSkeleton() {
        var container = byId('mlFeatureCards');
        if (!container) {
            return;
        }

        container.innerHTML = ''
            + '<div class="ml-skeleton-feature-list">'
            + [0, 1, 2, 3].map(function () {
                return ''
                    + '<article class="forecast-feature-card ml-skeleton-feature">'
                    + '<span class="ml-skeleton-line short"></span>'
                    + '<span class="ml-skeleton-line medium"></span>'
                    + '<span class="ml-skeleton-line long"></span>'
                    + '</article>';
            }).join('')
            + '</div>';
    }

    function showInitialSkeletons() {
        renderStatsSkeletons();
        renderCardSkeletons('mlQualityMetricCards', 4);
        renderOptionalMetricCards('mlQualityEventMetricsSection', 'mlQualityEventMetricCards', []);
        renderClassBalanceWarning('mlQualityEventMetricCards', false);
        renderTableSkeleton('mlCountTableShell', 8, 4);
        charts.renderChartSkeleton('mlForecastChart', 'mlForecastChartFallback');
        charts.renderChartSkeleton('mlCompareChart', 'mlCompareChartFallback');
        charts.renderChartSkeleton('mlAppgChart', 'mlAppgChartFallback');
        renderTableSkeleton('mlForecastTableShell', 4, 4);
        charts.renderChartSkeleton('mlImportanceChart', 'mlImportanceChartFallback');
        renderImportanceNote('');
        renderFeatureSkeleton();
        renderCriticalNotes([]);
    }

    function applyMlModelData(data, options) {
        if (!data) {
            return;
        }
        var settings = options || {};

        currentMlData = data;

        var filters = data.filters || {};
        var summary = data.summary || {};
        var quality = data.quality_assessment || {};
        var chartData = data.charts || {};

        renderSidebarStatus(data);
        renderHero(data);
        renderSummaryCards(summary);
        var selectedTableNames = Array.isArray(filters.table_names)
            ? filters.table_names
            : ((filters.table_name && filters.table_name !== 'all') ? [filters.table_name] : []);
        if (!selectedTableNames.length && (!filters.table_name || filters.table_name === 'all')) {
            selectedTableNames = (Array.isArray(filters.available_tables) ? filters.available_tables : [])
                .map(function (option) { return option && option.value ? String(option.value).trim() : ''; })
                .filter(function (value) { return value && value !== 'all'; });
        }
        renderTableChecklist(filters.available_tables, selectedTableNames);
        setTableChecklistOpen(false);
        setSelectOptions('mlCauseFilter', filters.available_causes, filters.cause, 'Все причины');
        setSelectOptions('mlObjectCategoryFilter', filters.available_object_categories, filters.object_category, 'Все категории');
        var inferredLatestYear = null;
        var appgGraphSeries = (Array.isArray(data.appg_period_series) && data.appg_period_series.length)
            ? data.appg_period_series
            : (data.appg_series || []);
        if (Array.isArray(appgGraphSeries) && appgGraphSeries.length) {
            appgGraphSeries.forEach(function (item) {
                var rawDate = String((item && item.current_date) || '');
                var candidate = parseInt(rawDate.slice(0, 4), 10);
                if (!isNaN(candidate) && (inferredLatestYear == null || candidate > inferredLatestYear)) {
                    inferredLatestYear = candidate;
                }
            });
        }
        var defaultMonth = String((new Date().getMonth() + 1));
        var effectiveYear = filters.year == null || filters.year === '' ? (inferredLatestYear == null ? '' : String(inferredLatestYear)) : String(filters.year);
        var effectiveMonth = '';
        if (filters.month != null && filters.month !== '') {
            effectiveMonth = String(filters.month);
        } else if (!effectiveYear) {
            effectiveMonth = defaultMonth;
        }
        var historyYears = collectAvailableYears(filters);
        var compareSeries = data.compare_series || {};
        var responseCompare = extractCompareFromResponse(data);
        var requestCompare = settings.requestCompare || null;
        var formCompareYearA = byId('mlYearAFilter') ? String(byId('mlYearAFilter').value || '').trim() : '';
        var formCompareYearB = byId('mlYearBFilter') ? String(byId('mlYearBFilter').value || '').trim() : '';
        var compareYearA = responseCompare.year_a || (effectiveYear || String(new Date().getFullYear()));
        var compareYearB = responseCompare.year_b || String(Math.max(1990, parseInt(compareYearA, 10) - 1));
        var compareMonth = compareSeries.month != null ? String(compareSeries.month) : (effectiveMonth || defaultMonth);
        var compareYearOptions = buildYearOptions(compareYearA, {
            years: historyYears,
            extraYears: [compareYearA, compareYearB, effectiveYear],
            expandToDefault: historyYears.length < 2,
            includeEmptyOption: false
        });

        setSelectOptions('mlYearFilter', buildYearOptions(effectiveYear, {
            years: historyYears,
            extraYears: [compareYearA, compareYearB, effectiveYear],
            expandToDefault: historyYears.length < 2
        }), effectiveYear, 'Текущий режим');
        setSelectOptions('mlMonthFilter', buildMonthOptions(), compareMonth, 'Все месяцы');
        if (keepUserCompareSelection && requestCompare) {
            setSelectOptions('mlYearAFilter', compareYearOptions, formCompareYearA || requestCompare.year_a || compareYearA, 'Текущий режим');
            setSelectOptions('mlYearBFilter', compareYearOptions, formCompareYearB || requestCompare.year_b || compareYearB, 'Текущий режим');
        } else {
            setSelectOptions('mlYearAFilter', compareYearOptions, compareYearA, 'Текущий режим');
            setSelectOptions('mlYearBFilter', compareYearOptions, compareYearB, 'Текущий режим');
        }
        setText('mlForecastDaysDisplay', (summary.forecast_days_display || '7') + ' дней');

        setText('mlQualityTitle', quality.title || 'Валидация качества ML-прогноза количества пожаров');
        setText('mlQualitySubtitle', quality.subtitle || 'Метрики рассчитаны на единой исторической выборке и показывают точность прогноза количества пожаров по дням.');
        renderMetricCards('mlQualityMetricCards', quality.metric_cards || [], 'После расчета здесь появятся метрики качества ML-прогноза.');
        renderOptionalMetricCards('mlQualityEventMetricsSection', 'mlQualityEventMetricCards', quality.event_metric_cards || [], '');
        renderClassBalanceWarning(
            'mlQualityEventMetricCards',
            Boolean(quality.class_balance_warning)
        );
        setText('mlCountTableTitle', (quality.count_table && quality.count_table.title) || 'Сравнение методов прогноза количества пожаров');
        renderCountTable(quality.count_table || {});
        setText('mlForecastTitle', 'Сколько пожаров ожидается по дням');
        charts.renderLineChart(chartData.forecast, 'mlForecastChart', 'mlForecastChartFallback');
        charts.renderCompareChart(compareSeries, 'mlCompareChart', 'mlCompareChartFallback', 'mlCompareChartSummary');
        charts.renderAppgChart(appgGraphSeries || [], 'mlAppgChart', 'mlAppgChartFallback', 'mlAppgChartNote');
        if (Array.isArray(data.forecast_rows) && data.forecast_rows.length) {
            var forecastFallback = byId('mlForecastChartFallback');
            if (forecastFallback) {
                forecastFallback.classList.add('is-hidden');
                forecastFallback.style.display = 'none';
            }
        }
        renderForecastTable(data.forecast_rows || []);

        setText('mlImportanceTitle', 'Что сильнее всего влияет на прогноз');
        charts.renderBarsChart(chartData.importance, 'mlImportanceChart', 'mlImportanceChartFallback');
        renderImportanceNote(chartData.importance && chartData.importance.note ? chartData.importance.note : '');
        renderFeatureCards(data.features || []);
        renderCriticalNotes(data.notes || []);
        if (shared.revealPageContent) { shared.revealPageContent(); }
    }

    function clearProgressTimers() {
        progressTimers.clear();
    }

    function updateProgressStep(activeIndex, options) {
        var settings = options || {};
        var activeStep = progressSteps[Math.max(0, Math.min(progressSteps.length - 1, activeIndex))];
        var leadText = settings.lead || activeStep.lead;
        var messageText = settings.message || activeStep.message;

        setStepProgress({
            activeIndex: activeIndex,
            isError: settings.isError,
            isFinished: settings.isFinished,
            lead: leadText,
            leadId: 'mlLoadingLead',
            message: messageText,
            messageId: 'mlLoadingMessage',
            stepSelector: '.ml-progress-step',
            stepsId: 'mlProgressSteps'
        });
    }

    function setRefreshButtonState(isBusy) {
        var button = byId('mlRefreshButton');
        if (!button) {
            return;
        }
        button.disabled = !!isBusy;
        button.classList.toggle('is-loading', !!isBusy);
    }

    function setLoadingStateMode(mode) {
        var loadingState = byId('mlLoadingState');
        var skeleton = byId('mlLoadingSkeleton');
        if (!loadingState) {
            return;
        }
        loadingState.classList.remove('is-pending', 'is-ready');
        if (mode === 'ready') {
            loadingState.classList.add('is-ready');
        } else {
            loadingState.classList.add('is-pending');
        }
        if (skeleton) {
            skeleton.classList.toggle('is-hidden', mode === 'ready');
        }
    }

    function showLoadingState() {
        var asyncState = byId('mlAsyncState');
        var loadingState = byId('mlLoadingState');
        var errorState = byId('mlErrorState');
        setHidden(asyncState, false);
        setHidden(loadingState, false);
        setHidden(errorState, true);
        setText('mlErrorMessage', '');
        setLoadingStateMode('pending');
    }

    function hideLoadingState() {
        var asyncState = byId('mlAsyncState');
        var loadingState = byId('mlLoadingState');
        var errorState = byId('mlErrorState');
        setHidden(loadingState, true);
        if (asyncState && errorState && errorState.classList.contains('is-hidden')) {
            setHidden(asyncState, true);
        }
    }

    function showError(message) {
        var asyncState = byId('mlAsyncState');
        var loadingState = byId('mlLoadingState');
        var errorState = byId('mlErrorState');
        var activeIndex = 0;
        var currentJobState = api.getCurrentJobState ? api.getCurrentJobState() : null;

        setHidden(asyncState, false);
        setHidden(loadingState, false);
        setHidden(errorState, false);
        if (currentJobState && currentJobState.status === 'running') {
            activeIndex = 1;
        }
        if (currentJobState && currentJobState.backtest_job
            && (currentJobState.backtest_job.status === 'running' || currentJobState.backtest_job.status === 'completed')) {
            activeIndex = 2;
        }
        setLoadingStateMode('ready');
        updateProgressStep(activeIndex, {
            isError: true,
            lead: 'Не удалось завершить ML-анализ',
            message: message || 'Попробуйте повторить запуск с теми же фильтрами.'
        });
        setText('mlErrorMessage', message || 'Не удалось загрузить ML-данные. Попробуйте еще раз.');
    }

    function hideError() {
        var asyncState = byId('mlAsyncState');
        var loadingState = byId('mlLoadingState');
        var errorState = byId('mlErrorState');
        setHidden(errorState, true);
        setText('mlErrorMessage', '');
        if (asyncState && loadingState && loadingState.classList.contains('is-hidden')) {
            setHidden(asyncState, true);
        }
    }

    function collectMlFiltersFromForm() {
        var tableNames = getSelectedTableNamesFromForm();
        var yearValue = byId('mlYearFilter') ? String(byId('mlYearFilter').value || '').trim() : '';
        var monthValue = byId('mlMonthFilter') ? String(byId('mlMonthFilter').value || '').trim() : '';
        var yearAValue = byId('mlYearAFilter') ? String(byId('mlYearAFilter').value || '').trim() : '';
        var yearBValue = byId('mlYearBFilter') ? String(byId('mlYearBFilter').value || '').trim() : '';
        return {
            table_name: tableNames.length === 1 ? tableNames[0] : 'all',
            table_names: tableNames,
            cause: byId('mlCauseFilter') ? byId('mlCauseFilter').value : 'all',
            object_category: byId('mlObjectCategoryFilter') ? byId('mlObjectCategoryFilter').value : 'all',
            year: yearValue,
            month: monthValue,
            year_a: yearAValue,
            year_b: yearBValue,
        };
    }

    function syncTableChecklistSummary() {
        if (mlTableChecklist && typeof mlTableChecklist.syncSummary === 'function') {
            mlTableChecklist.syncSummary();
        }
    }

    function updateAsyncStateForJob(jobPayload) {
        var safeJob = jobPayload || {};
        var backtestJob = safeJob.backtest_job || null;
        var activeIndex = 0;
        var lead = 'ML-задача поставлена в очередь';
        var message = 'Ожидаем запуска фонового расчета.';
        var finished = false;

        if (safeJob.status === 'running') {
            activeIndex = 1;
            lead = 'Агрегируем историю и признаки';
            message = 'Собираем SQL-агрегаты, фильтры и дневной ряд для ML-прогноза.';
        }
        if (backtestJob && (backtestJob.status === 'running' || backtestJob.status === 'completed')) {
            activeIndex = 2;
            lead = backtestJob.status === 'completed' ? 'Валидация завершена' : 'Выполняем обучение и валидацию';
            message = backtestJob.logs && backtestJob.logs.length
                ? backtestJob.logs[backtestJob.logs.length - 1]
                : 'Проверяем модели на истории и выбираем рабочую конфигурацию.';
        }
        if (safeJob.logs && safeJob.logs.length) {
            message = safeJob.logs[safeJob.logs.length - 1];
        }
        if (safeJob.status === 'completed') {
            activeIndex = 3;
            lead = 'ML-анализ завершён';
            message = 'Результат готов, визуализации и таблицы уже подставлены в интерфейс.';
            finished = true;
        }
        setLoadingStateMode(finished ? 'ready' : 'pending');
        updateProgressStep(activeIndex, {
            isFinished: finished,
            lead: lead,
            message: message
        });
    }

    function startMlModelJob(options) {
        var settings = options || {};
        api.startMlModelJob(settings, {
            onBusyChange: function (isBusy) {
                setRefreshButtonState(isBusy);
                renderSidebarStatus(currentMlData || global.__FIRE_ML_INITIAL__ || {});
            },
            onStart: function (requestPayload) {
                clearProgressTimers();
                showLoadingState();
                hideError();
                var requestBody = requestPayload && requestPayload.body ? requestPayload.body : null;
                latestCompareRequest = {
                    id: ++compareRequestSeq,
                    compare: extractCompareFromRequestBody(requestBody),
                    requestBody: requestBody
                };
                updateProgressStep(0, {
                    lead: 'ML-задача поставлена в очередь',
                    message: 'Подготавливаем фоновый запуск анализа.'
                });
                renderSidebarStatus(currentMlData || global.__FIRE_ML_INITIAL__ || {});

                if (settings.initialLoad) {
                    showInitialSkeletons();
                }
            },
            onJobState: function (payload) {
                updateAsyncStateForJob(payload);
            },
            onCompleted: function (result, payload, requestBody) {
                var expected = latestCompareRequest && latestCompareRequest.requestBody
                    ? extractCompareFromRequestBody(latestCompareRequest.requestBody)
                    : extractCompareFromRequestBody(requestBody);
                var actual = extractCompareFromResponse(result);
                if (shouldLogCompareMismatch(expected, actual) && global.console && typeof global.console.warn === 'function') {
                    global.console.warn('[ml-compare] response year mismatch', {
                        request_payload: latestCompareRequest && latestCompareRequest.requestBody
                            ? latestCompareRequest.requestBody
                            : requestBody,
                        response_filters: result && result.filters ? result.filters : {},
                        response_compare_series: result && result.compare_series ? result.compare_series : {}
                    });
                }
                applyMlModelData(result, {
                    requestCompare: expected
                });
                keepUserCompareSelection = false;
                updateAsyncStateForJob(payload || {});
                hideError();
                renderSidebarStatus(currentMlData || result || global.__FIRE_ML_INITIAL__ || {});
            },
            onError: function (message) {
                hideLoadingState();
                showError(message);
                renderSidebarStatus(currentMlData || global.__FIRE_ML_INITIAL__ || {});
            }
        });
    }

    function init() {
        var form = byId('mlModelForm');
        var initialData = global.__FIRE_ML_INITIAL__ || null;
        var tableFilterRoot = byId('mlTableFilter');
        var tableFilterToggle = byId('mlTableFilterToggle');
        var syncScreenLinks = function () {
            syncTableChecklistSummary();
        };

        if (form) {
            form.addEventListener('submit', function (event) {
                event.preventDefault();
                startMlModelJob();
            });
            form.addEventListener('change', function (event) {
                syncScreenLinks();
                var targetName = event && event.target ? event.target.name : '';
                if (targetName === 'table_names') {
                    if (tableCheckboxDebounceTimer !== null) {
                        clearTimeout(tableCheckboxDebounceTimer);
                    }
                    tableCheckboxDebounceTimer = setTimeout(function () {
                        tableCheckboxDebounceTimer = null;
                        startMlModelJob();
                    }, 400);
                    return;
                }
                if (
                    targetName === 'year'
                    || targetName === 'month'
                    || targetName === 'year_a'
                    || targetName === 'year_b'
                    || targetName === 'cause'
                    || targetName === 'object_category'
                ) {
                    if (targetName === 'year_a' || targetName === 'year_b') {
                        keepUserCompareSelection = true;
                    }
                    startMlModelJob();
                }
            });
            form.addEventListener('input', function (event) {
                if (event && event.target && event.target.tagName === 'INPUT') {
                    syncScreenLinks();
                }
            });
        }
        if (tableFilterToggle) {
            tableFilterToggle.addEventListener('click', function (event) {
                event.preventDefault();
                event.stopPropagation();
                var isOpen = tableFilterRoot && tableFilterRoot.classList.contains('is-open');
                if (isOpen) {
                    setTableChecklistOpen(false);
                } else {
                    setTableChecklistOpen(true);
                }
            });
        }
        document.addEventListener('click', function (event) {
            if (!tableFilterRoot) {
                return;
            }
            if (!tableFilterRoot.contains(event.target)) {
                setTableChecklistOpen(false);
            }
        });
        document.addEventListener('keydown', function (event) {
            if (event && event.key === 'Escape') {
                setTableChecklistOpen(false);
            }
        });
        var retryButton = byId('mlRetryButton');
        if (retryButton) {
            retryButton.addEventListener('click', function () {
                startMlModelJob();
            });
        }

        syncScreenLinks();
        if (initialData && initialData.bootstrap_mode !== 'deferred') {
            applyMlModelData(initialData);
            if (!appgDefaultInitialized) {
                appgDefaultInitialized = true;
                startMlModelJob();
            }
        } else {
            applyMlModelData(initialData || {});
            updateProgressStep(0, {
                lead: 'Лёгкий shell страницы уже открыт',
                message: 'Запускаем ML-анализ в фоне и следим за статусом по job_id.'
            });
            startMlModelJob({ initialLoad: true, useLocationSearch: true });
        }
    }

    global.MlModelRender = {
        applyMlModelData: applyMlModelData,
        init: init,
        startMlModelJob: startMlModelJob
    };
}(window));
