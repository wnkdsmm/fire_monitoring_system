(function (global) {
    var shared = global.FireUi;
    if (!shared || !global.AccessPointsRender || !global.AccessPointsState || !global.AccessPointsEvents) {
        return;
    }

    var byId = shared.byId;
    var renderApi = global.AccessPointsRender.create();
    var state = global.AccessPointsState.create({
        initialData: global.__FIRE_ACCESS_POINTS_INITIAL__ || {}
    });

    function getSelectedTableNames(form) {
        if (renderApi && typeof renderApi.getSelectedTableNamesFromForm === 'function') {
            return renderApi.getSelectedTableNamesFromForm();
        }
        return [];
    }

    function getFormParams() {
        var form = byId('accessPointsForm');
        var formData = form ? new FormData(form) : new FormData();
        var tableNames = getSelectedTableNames(form);
        return {
            table_name: tableNames.length === 1 ? tableNames[0] : 'all',
            table_names: tableNames,
            district: String(formData.get('district') || 'all'),
            year: 'all',
            feature_columns: formData.getAll('feature_columns').map(function (value) {
                return String(value || '').trim();
            }).filter(Boolean)
        };
    }

    function buildAccessPointsQuery(params) {
        var query = new URLSearchParams();
        var tableNames = Array.isArray(params.table_names) ? params.table_names : [];
        if (tableNames.length === 1) {
            query.set('table_name', tableNames[0]);
        } else if (tableNames.length > 1) {
            tableNames.forEach(function (tableName) {
                var normalized = String(tableName || '').trim();
                if (normalized) {
                    query.append('table_names', normalized);
                }
            });
        } else {
            query.set('table_name', params.table_name || 'all');
        }
        query.set('district', params.district || 'all');
        (Array.isArray(params.feature_columns) ? params.feature_columns : []).forEach(function (value) {
            query.append('feature_columns', value);
        });
        return query;
    }

    function updateUrl(params) {
        var query = buildAccessPointsQuery(params);
        window.history.replaceState({}, '', '/access-points?' + query.toString());
    }

    
    function validateFeatureSelection(params) {
        if (Array.isArray(params.feature_columns) && params.feature_columns.length) {
            return true;
        }
        renderApi.showError('Выберите хотя бы один фактор scoring, чтобы пересчитать рейтинг проблемных точек.');
        return false;
    }

    async function fetchAccessPoints(params) {
        if (!validateFeatureSelection(params)) {
            return;
        }

        var requestId = state.nextRequestId();
        var activeController = state.getCurrentController();
        if (activeController) {
            activeController.abort();
        }
        var controller = new AbortController();
        state.setCurrentController(controller);
        var refreshButton = byId('accessPointsRefreshButton');
        if (refreshButton) {
            refreshButton.disabled = true;
        }
        renderApi.showLoading('Собираем incidents по точкам, считаем explainable score, decomposition и uncertainty notes.');
        try {
            var query = buildAccessPointsQuery(params);
            var result = await shared.fetchJson('/api/access-points-data?' + query.toString(), {
                headers: { Accept: 'application/json' },
                signal: controller.signal
            }, 'Не удалось построить рейтинг проблемных точек.');
            var payload = result.payload;
            if (!state.isLatestRequest(requestId)) {
                return;
            }
            renderApi.render(payload);
            updateUrl(params);
        } catch (error) {
            if (error && error.name === 'AbortError') {
                renderApi.hideLoading();
                return;
            }
            if (!state.isLatestRequest(requestId)) {
                return;
            }
            renderApi.showError(error && error.message ? error.message : 'Не удалось построить рейтинг проблемных точек.');
        } finally {
            state.clearController(controller);
            if (refreshButton && !state.getCurrentController()) {
                refreshButton.disabled = false;
            }
        }
    }

    function bootstrap() {
        var initialData = state.getInitialData() || {};
        if (initialData.bootstrap_mode === 'deferred') {
            renderApi.showLoading();
            fetchAccessPoints(getFormParams());
        } else {
            renderApi.renderCharts(initialData.charts || {});
            if (shared.revealPageContent) { shared.revealPageContent(); }
        }
    }

    function init() {
        global.AccessPointsEvents.init({
            onBootstrap: bootstrap,
            onRetry: function () {
                fetchAccessPoints(getFormParams());
            },
            onSubmit: function () {
                fetchAccessPoints(getFormParams());
            },
            onTableFilterChange: function () {
                if (renderApi.syncTableChecklistSummary) {
                    renderApi.syncTableChecklistSummary();
                }
                fetchAccessPoints(getFormParams());
            },
            onSelectAllTables: function () {
                if (renderApi.selectAllTableNames) {
                    renderApi.selectAllTableNames();
                }
                if (renderApi.syncTableChecklistSummary) {
                    renderApi.syncTableChecklistSummary();
                }
                fetchAccessPoints(getFormParams());
            },
            onClearAllTables: function () {
                if (renderApi.clearAllTableNames) {
                    renderApi.clearAllTableNames();
                }
                if (renderApi.syncTableChecklistSummary) {
                    renderApi.syncTableChecklistSummary();
                }
            },
            onToggleTableFilter: function () {
                var root = byId('accessPointsTableFilter');
                var isOpen = root && root.classList.contains('is-open');
                if (!isOpen) {
                    if (renderApi.setTableChecklistOpen) {
                        renderApi.setTableChecklistOpen(true);
                    }
                } else {
                    if (renderApi.setTableChecklistOpen) {
                        renderApi.setTableChecklistOpen(false);
                    }
                }
            },
            onCloseTableFilter: function () {
                if (renderApi.setTableChecklistOpen) {
                    renderApi.setTableChecklistOpen(false);
                }
            }
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
        return;
    }
    init();
}(window));
