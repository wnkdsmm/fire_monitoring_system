(function (global) {
    var shared = global.FireUi;
    if (!shared || !global.DashboardState || !global.DashboardRender || !global.DashboardEvents) {
        return;
    }

    var byId = shared.byId;
    var fetchJson = shared.fetchJson;
    var getApiErrorMessage = shared.getApiErrorMessage;
    var renderApi = global.DashboardRender.create();
    var state = global.DashboardState.create({
        initialData: global.__FIRE_DASHBOARD_INITIAL_DATA__ || null
    });
    var deferredRetryTimer = null;
    var deferredRetryAttempts = 0;

function buildDashboardApiError(response, payload) {
        const errorPayload = payload && payload.error ? payload.error : {};
        const statusCode = Number(errorPayload.status_code || (response && response.status) || 0);
        const fallbackMessage = (
            statusCode >= 500
                ? 'РќРµ СѓРґР°Р»РѕСЃСЊ РѕР±РЅРѕРІРёС‚СЊ РґР°РЅРЅС‹Рµ. РџРѕРїСЂРѕР±СѓР№С‚Рµ РїРѕРІС‚РѕСЂРёС‚СЊ Р·Р°РїСЂРѕСЃ.'
                : 'РџСЂРѕРІРµСЂСЊС‚Рµ РїР°СЂР°РјРµС‚СЂС‹ С„РёР»СЊС‚СЂР° Рё РїРѕРІС‚РѕСЂРёС‚Рµ Р·Р°РїСЂРѕСЃ.'
        );
        const message = getApiErrorMessage(payload, fallbackMessage);
        const error = new Error(message);
        error.dashboardStatusCode = statusCode;
        error.dashboardErrorId = errorPayload.error_id || '';
        error.dashboardCode = errorPayload.code || '';
        return error;
    }

    function readDashboardPayload(payload) {
        if (!payload || typeof payload !== 'object') {
            const contractError = new Error('РЎРµСЂРІРёСЃ РЅРµ РІРµСЂРЅСѓР» РґР°РЅРЅС‹Рµ. РџСЂРѕРІРµСЂСЊС‚Рµ СЃРѕРµРґРёРЅРµРЅРёРµ Рё РїРѕРїСЂРѕР±СѓР№С‚Рµ СЃРЅРѕРІР°.');
            contractError.dashboardStatusCode = 502;
            throw contractError;
        }

        if (payload.bootstrap_mode === 'deferred') {
            return { __deferred: true };
        }

        return payload;
    }

    async function fetchDashboardPayload(url, options) {
        try {
            const result = await fetchJson(
                url,
                options,
                'РќРµ СѓРґР°Р»РѕСЃСЊ РѕР±РЅРѕРІРёС‚СЊ РґР°РЅРЅС‹Рµ. РџРѕРїСЂРѕР±СѓР№С‚Рµ РїРѕРІС‚РѕСЂРёС‚СЊ Р·Р°РїСЂРѕСЃ.'
            );
            return readDashboardPayload(result.payload);
        } catch (error) {
            if (error instanceof SyntaxError) {
                const contractError = new Error('РЎРµСЂРІРёСЃ РЅРµ РІРµСЂРЅСѓР» РґР°РЅРЅС‹Рµ. РџСЂРѕРІРµСЂСЊС‚Рµ СЃРѕРµРґРёРЅРµРЅРёРµ Рё РїРѕРїСЂРѕР±СѓР№С‚Рµ СЃРЅРѕРІР°.');
                contractError.dashboardStatusCode = 502;
                throw contractError;
            }
            if (error && Object.prototype.hasOwnProperty.call(error, 'payload')) {
                throw buildDashboardApiError(error, error.payload);
            }
            throw error;
        }
    }

async function fetchDashboardData() {
        if (deferredRetryTimer) {
            clearTimeout(deferredRetryTimer);
            deferredRetryTimer = null;
        }
        deferredRetryAttempts = 0;
        const form = byId('filtersForm');
        const button = byId('refreshDashboardButton');
        if (!form) {
            return;
        }

        const params = new URLSearchParams(new FormData(form));
        const query = params.toString();

        if (button) {
            button.disabled = true;
        }

        try {
            renderApi.hideDashboardError();
            const summaryData = await fetchDashboardPayload('/api/dashboard-data?' + query + '&level=summary', {
                headers: {
                    'Accept': 'application/json'
                }
            });
            if (summaryData && summaryData.__deferred) {
                const deferredMessage = new Error('Р”Р°РЅРЅС‹Рµ Р·Р°РіСЂСѓР¶Р°СЋС‚СЃСЏ, РѕР±РЅРѕРІРёС‚Рµ СЃС‚СЂР°РЅРёС†Сѓ С‡РµСЂРµР· РЅРµСЃРєРѕР»СЊРєРѕ СЃРµРєСѓРЅРґ.');
                deferredMessage.dashboardStatusCode = 0;
                renderApi.showDashboardError(deferredMessage);
                if (deferredRetryAttempts < 3) {
                    deferredRetryAttempts += 1;
                    deferredRetryTimer = setTimeout(function () {
                        deferredRetryTimer = null;
                        fetchDashboardData();
                    }, 4000);
                }
                return;
            }
            deferredRetryAttempts = 0;
            renderApi.applyDashboardData(summaryData);
            renderApi.showChartsLoading();
            fetchDashboardPayload('/api/dashboard-data?' + query + '&level=full', {
                headers: {
                    'Accept': 'application/json'
                }
            }).then(function (fullData) {
                if (fullData && !fullData.__deferred) {
                    renderApi.applyDashboardData(fullData);
                }
            }).catch(function () {
                renderApi.showChartsLoading && (function() {
                    var ids = ['yearlyFiresChart','distributionChart','yearlyAreaChart',
                        'cumulativeAreaChart','monthlyHeatmapChart','monthlyProfileChart','areaBucketsChart'];
                    ids.forEach(function(id) {
                        var el = document.getElementById(id);
                        if (el) el.innerHTML = '<div class="chart-loading chart-loading--error">Не удалось загрузить графики. Обновите страницу.</div>';
                    });
                })();
            });
            window.history.replaceState({}, '', renderApi.buildDashboardPageHref(state.collectSelectedFilters()));
        } catch (error) {
            renderApi.showDashboardError(error);
        } finally {
            if (button) {
                button.disabled = false;
            }
        }
    }

    function syncBriefLink() {
        var filters = state.collectSelectedFilters();
        renderApi.updateDashboardBriefExport(filters);
        renderApi.updateDashboardScreenLinks(filters);
    }

    function bootstrap() {
        var initialData = state.getInitialData();
        var isDeferredBootstrap = !!(initialData && initialData.bootstrap_mode === 'deferred');
        var initialCharts = initialData && initialData.charts ? initialData.charts : {};
        var initialYearlyTrend = initialCharts && initialCharts.yearly_trend ? initialCharts.yearly_trend : null;
        var hasInitialYearlyTrendPlotly = !!(
            initialYearlyTrend
            && initialYearlyTrend.plotly
            && Array.isArray(initialYearlyTrend.plotly.data)
            && initialYearlyTrend.plotly.data.length
        );
        var shouldFetchOnLoad = !initialData || isDeferredBootstrap || !hasInitialYearlyTrendPlotly;

        if (initialData && !isDeferredBootstrap) {
            renderApi.renderDashboardCharts(initialData.charts || {});
            if (shared.revealPageContent) { shared.revealPageContent(); }
        }
        syncBriefLink();

        if (shouldFetchOnLoad) {
            fetchDashboardData();
        }

        global.fireDashboard = {
            reload: fetchDashboardData,
            afterImport: function () {
                fetchDashboardData();
            }
        };
    }

    function init() {
        global.DashboardEvents.init({
            onBootstrap: bootstrap,
            onFilterChange: syncBriefLink,
            onTableFilterOpen: syncBriefLink,
            onTableFilterChange: function () {
                syncBriefLink();
            },
            onRetry: fetchDashboardData,
            onSubmit: fetchDashboardData
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
        return;
    }
    init();
}(window));
