(function (global) {
    var shared = global.FireUi;
    if (!shared) {
        return;
    }

    global.DashboardRender = {
        create: function createDashboardRender() {
            var applyToneClass = shared.applyToneClass;
            var byId = shared.byId;
            var escapeHtml = shared.escapeHtml;
            var renderListItems = shared.renderListItems;
            var renderPlotlyInContainer = shared.renderPlotlyInContainer;
            var setHref = shared.setHref;
            var setText = shared.setText;
            var createTableChecklist = shared.createTableChecklist;
            var dashboardTableChecklist = typeof createTableChecklist === 'function'
                ? createTableChecklist({
                    rootId: 'dashboardTableFilter',
                    menuId: 'dashboardTableFilterMenu',
                    toggleId: 'dashboardTableFilterToggle',
                    summaryId: 'dashboardTableFilterSummary',
                    selectedListId: 'dashboardTableFilterSelectedList',
                    itemClassName: 'dashboard-table-checklist-item',
                    singleSelectedPrefix: 'Выбрана: ',
                    compactSelectedList: true,
                    selectedListMode: 'chips',
                    selectAllWhenEmpty: true
                })
                : null;

    function renderTableChecklist(options, selectedTableNames) {
        if (dashboardTableChecklist && typeof dashboardTableChecklist.renderChecklist === 'function') {
            dashboardTableChecklist.renderChecklist(options, selectedTableNames);
        }
    }

    function renderRankingList(containerId, items, emptyMessage, accentClass) {
        const container = byId(containerId);
        if (!container) {
            return;
        }

        if (!Array.isArray(items) || !items.length) {
            container.innerHTML = '<div class="mini-empty">' + escapeHtml(emptyMessage) + '</div>';
            return;
        }

        container.innerHTML = items.map(function (item) {
            return '<div class="ranking-row ' + accentClass + '" title="' + escapeHtml(item.label + ': ' + item.value_display) + '">' +
                '<div class="ranking-label">' + escapeHtml(item.label) + '</div>' +
                '<div class="ranking-meta">' + escapeHtml(item.value_display) + '</div>' +
            '</div>';
        }).join('');
    }

    function renderDashboardCharts(charts) {
        var safeCharts = charts || {};
        renderPlotlyInContainer(safeCharts.yearly_fires, 'yearlyFiresChart');
        renderPlotlyInContainer(safeCharts.yearly_area, 'distributionChart');
        renderPlotlyInContainer(safeCharts.yearly_trend, 'recentYearsChart');
        renderPlotlyInContainer(safeCharts.monthly_heatmap, 'monthlyHeatmapChart');
        renderPlotlyInContainer(safeCharts.monthly_profile, 'monthlyProfileChart');
    }

    function showChartsLoading() {
        var ids = [
            'yearlyFiresChart',
            'distributionChart',
            'recentYearsChart',
            'monthlyHeatmapChart',
            'monthlyProfileChart',
        ];
        ids.forEach(function (id) {
            var container = byId(id);
            if (container) {
                container.innerHTML = '<div class="chart-loading">Загрузка...</div>';
            }
        });
    }

    function renderNotesPanel(notes) {
        const panel = byId('dashboardNotesPanel');
        const list = byId('dashboardNotesList');
        if (!panel || !list) {
            return;
        }

        if (!Array.isArray(notes) || !notes.length) {
            panel.classList.add('is-hidden');
            list.innerHTML = '';
            return;
        }

        panel.classList.remove('is-hidden');
        renderListItems('dashboardNotesList', notes, '');
    }

    function hideDashboardError() {
        const card = byId('dashboardInlineError');
        if (card) {
            card.classList.add('is-hidden');
        }
        setText('dashboardInlineErrorLead', '');
        setText('dashboardInlineErrorMessage', '');
    }

    function showDashboardError(error) {
        const card = byId('dashboardInlineError');
        if (!card) {
            return;
        }

        const statusCode = Number(error && error.dashboardStatusCode ? error.dashboardStatusCode : 0);
        const errorId = error && error.dashboardErrorId ? String(error.dashboardErrorId) : '';
        const baseMessage = error && error.message
            ? String(error.message)
            : 'Не удалось обновить панель. Попробуйте повторить запрос.';
        const lead = statusCode >= 500
            ? 'Не удалось обновить панель'
            : statusCode >= 400
                ? 'Проверьте параметры запроса'
                : 'Не удалось загрузить данные';
        const fullMessage = errorId ? baseMessage + ' Код ошибки: ' + errorId + '.' : baseMessage;

        setText('dashboardInlineErrorLead', lead);
        setText('dashboardInlineErrorMessage', fullMessage);
        card.classList.remove('is-hidden');
    }

function renderManagementCards(items) {
        const container = byId('managementBriefCards');
        if (!container) {
            return;
        }

        if (!Array.isArray(items) || !items.length) {
            container.innerHTML = '<div class="mini-empty">Сводка появится после загрузки данных.</div>';
            return;
        }

        container.innerHTML = items.map(function (item) {
            return '<article class="executive-brief-card tone-' + escapeHtml(item.tone || 'sky') + '">' +
                '<span class="stat-label">' + escapeHtml(item.label || '-') + '</span>' +
                '<strong class="stat-value executive-brief-value">' + escapeHtml(item.value || '-') + '</strong>' +
                '<span class="stat-foot">' + escapeHtml(item.meta || '') + '</span>' +
            '</article>';
        }).join('');
    }

    function renderManagementTerritories(items) {
        const container = byId('managementTerritories');
        if (!container) {
            return;
        }

        if (!Array.isArray(items) || !items.length) {
            container.innerHTML = '<div class="mini-empty">Территории первого внимания появятся после расчёта.</div>';
            return;
        }

        container.innerHTML = items.map(function (item) {
            return '<article class="executive-territory-card tone-' + escapeHtml(item.risk_tone || 'sky') + '">' +
                '<div class="executive-territory-head">' +
                    '<strong>' + escapeHtml(item.label || 'Территория') + '</strong>' +
                    '<span class="executive-territory-score">' + escapeHtml(item.risk_display || '0 / 100') + '</span>' +
                '</div>' +
                '<div class="executive-territory-tags">' +
                    '<span class="forecast-badge risk-badge tone-' + escapeHtml(item.risk_tone || 'sky') + '">' + escapeHtml(item.risk_class_label || 'Нет оценки') + '</span>' +
                    '<span class="forecast-badge risk-badge tone-sky">' + escapeHtml(item.priority_label || 'Плановое наблюдение') + '</span>' +
                '</div>' +
                '<p class="executive-territory-reason">' + escapeHtml(item.drivers_display || 'Недостаточно данных для объяснения приоритета.') + '</p>' +
                '<div class="executive-territory-action">' +
                    '<strong>' + escapeHtml(item.action_label || 'Плановое наблюдение') + '</strong>' +
                    '<span>' + escapeHtml(item.action_hint || '') + '</span>' +
                '</div>' +
                '<div class="executive-territory-meta">' +
                    '<span>' + escapeHtml(item.context_label || 'Контекст не указан') + '</span>' +
                    '<span>Последний пожар: ' + escapeHtml(item.last_fire_display || '-') + '</span>' +
                '</div>' +
            '</article>';
        }).join('');
    }

    function renderManagementActions(items) {
        const container = byId('managementActionList');
        if (!container) {
            return;
        }

        if (!Array.isArray(items) || !items.length) {
            container.innerHTML = '<div class="mini-empty">Рекомендации появятся после расчёта.</div>';
            return;
        }

        container.innerHTML = items.map(function (item) {
            return '<article class="executive-action-item">' +
                '<strong>' + escapeHtml(item.label || 'Рекомендация') + '</strong>' +
                '<span>' + escapeHtml(item.detail || '') + '</span>' +
            '</article>';
        }).join('');
    }

    function buildDashboardBriefHref(filters) {
        const params = new URLSearchParams();
        const safeFilters = filters || {};
        const selectedTables = Array.isArray(safeFilters.table_names) ? safeFilters.table_names : [];
        if (selectedTables.length) {
            selectedTables.forEach(function (tableName) {
                var normalized = String(tableName || '').trim();
                if (normalized) {
                    params.append('table_names', normalized);
                }
            });
        } else if (safeFilters.table_name) {
            params.set('table_name', safeFilters.table_name);
        }

        const query = params.toString();
        return '/brief/dashboard.txt' + (query ? '?' + query : '');
    }

    function updateDashboardBriefExport(filters) {
        const href = buildDashboardBriefHref(filters || {});
        Array.prototype.forEach.call(
            document.querySelectorAll('#dashboardBrief .executive-brief-download'),
            function (link) {
                link.setAttribute('href', href);
            }
        );
    }

    function updateDashboardScreenLinks() {}

    function buildDashboardPageHref(filters, mode) {
        const params = new URLSearchParams();
        const safeFilters = filters || {};
        const selectedTables = Array.isArray(safeFilters.table_names) ? safeFilters.table_names : [];
        if (selectedTables.length) {
            selectedTables.forEach(function (tableName) {
                var normalized = String(tableName || '').trim();
                if (normalized) {
                    params.append('table_names', normalized);
                }
            });
        } else if (safeFilters.table_name) {
            params.set('table_name', safeFilters.table_name);
        }
        if (mode) {
            params.set('mode', mode);
        }

        const query = params.toString();
        return query ? '/?' + query : '/';
    }

        function applyDashboardData(data) {
        if (!data) {
            return;
        }

        const summary = data.summary || {};
        const scope = data.scope || {};
        const trend = data.trend || {};
        const charts = data.charts || {};
        const rankings = data.rankings || {};
        const filters = data.filters || {};
        const management = data.management || {};
        const brief = management.brief || {};

        var selectedTableNames = Array.isArray(filters.table_names)
            ? filters.table_names
            : ((filters.table_name && filters.table_name !== 'all') ? [filters.table_name] : []);
        if (!selectedTableNames.length && (!filters.table_name || filters.table_name === 'all')) {
            selectedTableNames = (Array.isArray(filters.available_tables) ? filters.available_tables : [])
                .map(function (option) { return option && option.value ? String(option.value).trim() : ''; })
                .filter(function (value) { return value && value !== 'all'; });
        }
        renderTableChecklist(filters.available_tables, selectedTableNames);

        setText('heroTableLabel', scope.table_label || 'Все таблицы');
        setText('heroYearLabel', scope.year_label || 'Все годы');
        setText('heroGroupLabel', scope.group_label || 'Нет данных');
        setText('heroHorizonDays', String(management.priority_horizon_days || '14') + ' дней');
        setText('dashboardLeadSummary', brief.lead || management.summary_line || 'После загрузки данных здесь появится краткий территориальный вывод и первая территория для проверки.');
        setText('managementHeroPriority', brief.top_territory_label || management.priority_territory_label || '-');
        setText('managementHeroPriorityMeta', brief.priority_reason || management.priority_reason || 'Недостаточно данных для определения первой территории.');
        setText('managementHeroConfidence', brief.confidence_label || management.confidence_label || 'Ограниченная');
        setText('managementHeroConfidenceScore', brief.confidence_score_display || management.confidence_score_display || '0 / 100');
        setText('managementHeroConfidenceMeta', brief.confidence_summary || management.confidence_summary || 'После загрузки данных здесь появится пояснение, насколько надежен территориальный приоритет.');
        applyToneClass(byId('dashboardPriorityCard'), brief.priority_tone || management.priority_tone || 'sky');
        applyToneClass(byId('dashboardConfidenceCard'), brief.confidence_tone || management.confidence_tone || 'fire');
        renderManagementCards((management.brief && management.brief.cards) || []);
        renderManagementTerritories(management.territories || []);
        renderManagementActions(management.actions || []);
        updateDashboardBriefExport({
            table_name: filters.table_name || '',
            table_names: selectedTableNames
        });
        updateDashboardScreenLinks({
            table_name: filters.table_name || '',
            table_names: selectedTableNames
        });

        setText('trendTitle', trend.title || 'Как менялась ситуация');
        setText('trendCurrentValue', trend.current_value_display || '0');
        setText('trendCurrentYear', trend.current_year || '-');
        setText('trendDeltaValue', trend.delta_display || 'Нет базы сравнения');
        setText('trendDescription', trend.description || '');

        const trendCard = byId('trendCard');
        if (trendCard) {
            trendCard.classList.remove('trend-up', 'trend-down', 'trend-flat');
            trendCard.classList.add('trend-' + (trend.direction || 'flat'));
        }

        setText('firesCountValue', summary.fires_count_display || '0');
        setText('firesCountFoot', scope.table_label || 'Все таблицы');
        setText('deathsValue', summary.deaths_display || '0');
        setText('injuriesValue', summary.injuries_display || '0');
        setText('evacuatedValue', summary.evacuated_display || '0');
        setText('childrenTotalValue', summary.children_total_display || '0');
        setText('severityValue', (summary.deaths_per_fire_pct_display || '0.0') + ' на 100 пожаров');

        setText('sidebarDatabaseTablesCount', scope.database_tables_count_display || '0');
        setText('sidebarYearsCoveredCount', summary.years_covered_display || '0');
        setText('sidebarPeriodLabel', summary.period_label || 'Нет данных');

        setText('yearlyFiresTitle', charts.yearly_fires ? charts.yearly_fires.title : 'Причины возгораний');
        setText('distributionTitle', charts.yearly_area ? charts.yearly_area.title : 'Последствия, эвакуация и дети');

        setText('monthlyHeatmapTitle', charts.monthly_heatmap ? charts.monthly_heatmap.title : 'Сезонность по месяцам и годам');
        setText('monthlyProfileTitle', charts.monthly_profile ? charts.monthly_profile.title : 'Сезонность по месяцам');
        setText('distributionMeta', charts.yearly_area ? charts.yearly_area.description : 'Что показывает блок: тяжесть последствий пожаров и влияние на людей.');

        setText('monthlyHeatmapMeta', charts.monthly_heatmap ? charts.monthly_heatmap.description : 'Количество пожаров по месяцам и годам.');
        setText('monthlyProfileMeta', charts.monthly_profile ? charts.monthly_profile.description : 'Что показывает блок: сезонный рисунок пожаров, если нужно планировать профилактику заранее.');

        var hasFullCharts = charts && (
            charts.yearly_fires !== undefined ||
            charts.yearly_area !== undefined ||
            charts.monthly_heatmap !== undefined ||
            charts.monthly_profile !== undefined
        );
        if (hasFullCharts) {
            renderDashboardCharts(charts);
        } else if (charts && charts.yearly_trend !== undefined) {
            renderPlotlyInContainer(charts.yearly_trend, 'recentYearsChart');
        }

        renderRankingList('topDistributionList', rankings.top_distribution, 'Нет данных по распределению.', 'ranking-row-fire');
        renderRankingList('topTablesList', rankings.top_tables, 'Нет таблиц в текущем фильтре.', 'ranking-row-table');
        renderRankingList('recentYearsList', rankings.recent_years, 'Недостаточно годовых данных.', 'ranking-row-year');
        renderNotesPanel(data.notes || []);
        if (shared.revealPageContent) { shared.revealPageContent(); }
    }

            return {
                applyDashboardData: applyDashboardData,
                buildDashboardPageHref: buildDashboardPageHref,
                hideDashboardError: hideDashboardError,
                renderDashboardCharts: renderDashboardCharts,
                showChartsLoading: showChartsLoading,
                showDashboardError: showDashboardError,
                updateDashboardBriefExport: updateDashboardBriefExport,
                updateDashboardScreenLinks: updateDashboardScreenLinks
            };
        }
    };
}(window));
