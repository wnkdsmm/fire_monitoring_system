(function (global) {
    var shared = global.FireUi || {};
    var byId = shared.byId;
    var apiClient = global.FireApiClient || {};
    var apiCall = apiClient.apiCall;

    function padDatePart(value) {
        return value < 10 ? '0' + value : String(value);
    }

    function getCurrentUserDateIso() {
        var now = new Date();
        return String(now.getFullYear()) + '-' + padDatePart(now.getMonth() + 1) + '-' + padDatePart(now.getDate());
    }

    function withCurrentUserDate(query) {
        var params = new URLSearchParams(query || '');
        params.set('current_user_date', getCurrentUserDateIso());
        return params.toString();
    }

    function buildQueryFromForm(formId) {
        var form = byId(formId || 'mlModelForm');
        if (!form) {
            return '';
        }
        return new URLSearchParams(new FormData(form)).toString();
    }

    function buildPayloadFromQuery(query) {
        var params = new URLSearchParams(query || '');
        var defaultMonth = String(new Date().getMonth() + 1);
        var tableNames = params.getAll('table_names').map(function (value) {
            return String(value || '').trim();
        }).filter(function (value) {
            return value.length > 0;
        });
        if (!tableNames.length) {
            var singleTable = String(params.get('table_name') || '').trim();
            if (singleTable && singleTable !== 'all') {
                tableNames = [singleTable];
            }
        }
        var tableName = tableNames.length === 1 ? tableNames[0] : 'all';
        return {
            table_name: tableName,
            table_names: tableNames,
            cause: params.get('cause') || 'all',
            object_category: params.get('object_category') || 'all',
            month: params.get('month') || defaultMonth,
            year_a: params.get('year_a') || '2024',
            year_b: params.get('year_b') || '2025',
            year_ml: params.get('year_ml') || String(new Date().getFullYear()),
            current_user_date: params.get('current_user_date') || getCurrentUserDateIso()
        };
    }

    function buildRequestPayload(options) {
        var settings = options || {};
        var baseQuery = settings.useLocationSearch && global.location.search
            ? global.location.search.replace(/^\?/, '')
            : buildQueryFromForm(settings.formId || 'mlModelForm');
        var query = withCurrentUserDate(baseQuery);
        var body = buildPayloadFromQuery(query);
        if (typeof settings.buildPayload === 'function') {
            body = settings.buildPayload(body) || body;
        }
        return {
            body: body,
            query: query
        };
    }

    async function fetchMlCompareSeries(options) {
        var settings = options || {};
        var requestPayload = buildRequestPayload(settings);
        var body = requestPayload.body || {};
        var comparePayload = {
            table_name: body.table_name || 'all',
            table_names: Array.isArray(body.table_names) ? body.table_names : [],
            cause: body.cause || 'all',
            object_category: body.object_category || 'all',
            month: body.month || '',
            year_a: body.year_a || '',
            year_b: body.year_b || '',
            year_ml: body.year_ml || '',
            current_user_date: body.current_user_date || getCurrentUserDateIso()
        };
        var result = await apiCall('/api/ml-compare-series', {
            method: 'POST',
            headers: {
                Accept: 'application/json',
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(comparePayload)
        }, 'Не удалось загрузить compare-series.');
        return {
            payload: result.payload || {},
            requestBody: comparePayload
        };
    }

    async function fetchMlCausesChart(options) {
        var settings = options || {};
        var requestPayload = buildRequestPayload(settings);
        var body = requestPayload.body || {};
        var causesPayload = {
            table_name: body.table_name || 'all',
            table_names: Array.isArray(body.table_names) ? body.table_names : [],
            cause: body.cause || 'all',
            object_category: body.object_category || 'all',
            month: body.month || '',
            year_a: body.year_a || '',
            year_b: body.year_b || '',
            current_user_date: body.current_user_date || getCurrentUserDateIso()
        };
        var result = await apiCall('/api/ml-causes-chart', {
            method: 'POST',
            headers: {
                Accept: 'application/json',
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(causesPayload)
        }, 'Не удалось загрузить данные по причинам.');
        return { payload: result.payload || {}, requestBody: causesPayload };
    }

    global.MlModelApi = {
        buildPayloadFromQuery: buildPayloadFromQuery,
        buildQueryFromForm: buildQueryFromForm,
        buildRequestPayload: buildRequestPayload,
        fetchMlCompareSeries: fetchMlCompareSeries,
        fetchMlCausesChart: fetchMlCausesChart
    };
}(window));
