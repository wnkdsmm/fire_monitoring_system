(function (global) {
    var shared = global.FireUi || {};
    var byId = shared.byId;
    var createSingleTimer = shared.createSingleTimer;
    var apiClient = global.FireApiClient || {};
    var apiCall = apiClient.apiCall;
    var pollUntilDone = apiClient.pollUntilDone;
    var getErrorMessage = shared.getErrorMessage;
    var FIXED_FORECAST_DAYS = '7';

    var jobPollTimer = createSingleTimer();
    var currentJobState = null;
    var isFetching = false;

    function withHandlers(handlers) {
        return handlers || {};
    }

    function notifyBusy(handlers, busy) {
        isFetching = !!busy;
        if (handlers && typeof handlers.onBusyChange === 'function') {
            handlers.onBusyChange(isFetching);
        }
    }

    function notifyJobState(handlers, payload) {
        currentJobState = payload || null;
        if (handlers && typeof handlers.onJobState === 'function') {
            handlers.onJobState(currentJobState);
        }
    }

    function notifyCompleted(handlers, result, payload, requestBody) {
        if (handlers && typeof handlers.onCompleted === 'function') {
            handlers.onCompleted(result, payload || currentJobState, requestBody || null);
        }
    }

    function notifyError(handlers, error, fallbackMessage) {
        if (handlers && typeof handlers.onError === 'function') {
            handlers.onError(getErrorMessage(error, fallbackMessage), error);
        }
    }

    function padDatePart(value) {
        return value < 10 ? '0' + value : String(value);
    }

    function getCurrentUserDateIso() {
        var now = new Date();
        return String(now.getFullYear()) + '-' + padDatePart(now.getMonth() + 1) + '-' + padDatePart(now.getDate());
    }

    function withCurrentUserDate(query) {
        var params = new URLSearchParams(query || '');
        params.delete('temperature');
        params.delete('forecast_days');
        params.delete('history_window');
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
        var tableName = 'all';
        if (tableNames.length === 1) {
            tableName = tableNames[0];
        }
        return {
            table_name: tableName,
            table_names: tableNames,
            cause: params.get('cause') || 'all',
            object_category: params.get('object_category') || 'all',
            year: params.get('year') || '',
            month: params.get('month') || defaultMonth,
            year_a: params.get('year_a') || '2024',
            year_b: params.get('year_b') || '2025',
            forecast_days: FIXED_FORECAST_DAYS,
            current_user_date: params.get('current_user_date') || getCurrentUserDateIso()
        };
    }

    function buildRequestPayload(options) {
        var settings = options || {};
        var baseQuery = settings.useLocationSearch && global.location.search
            ? global.location.search.replace(/^\?/, '')
            : buildQueryFromForm(settings.formId || 'mlModelForm');
        var query = withCurrentUserDate(baseQuery);
        return {
            body: buildPayloadFromQuery(query),
            query: query
        };
    }

    function stopJobPolling() {
        jobPollTimer.clear();
    }

    function pollMlJob(jobId, handlers) {
        var callbacks = withHandlers(handlers);

        if (!jobId) {
            notifyBusy(callbacks, false);
            notifyError(callbacks, new Error('Не передан идентификатор ML-задачи.'), 'Не удалось получить статус ML-задачи.');
            return;
        }

        pollUntilDone(
            '/api/ml-model-jobs/' + encodeURIComponent(jobId),
            {
                requestOptions: { headers: { Accept: 'application/json' } },
                fallbackMessage: 'Фоновая ML-задача завершилась с ошибкой.'
            },
            {
                onUpdate: function (payload) {
                    notifyJobState(callbacks, payload);
                },
                onDone: function (payload) {
                    notifyBusy(callbacks, false);
                    notifyCompleted(callbacks, payload.result, payload, callbacks.__requestBody || null);
                },
                onError: function (error) {
                    notifyBusy(callbacks, false);
                    notifyError(callbacks, error, 'Не удалось получить статус ML-задачи.');
                }
            },
            {
                intervalMs: 800,
                scheduleNext: function (fn, delay) {
                    jobPollTimer.set(fn, delay);
                },
                isDone: function (payload) {
                    return Boolean(payload && payload.status === 'completed' && payload.result);
                },
                isFailed: function (payload) {
                    return Boolean(payload && (payload.status === 'failed' || payload.status === 'missing'));
                },
                getFailureMessage: function (payload) {
                    return payload && payload.error_message
                        ? payload.error_message
                        : 'Фоновая ML-задача завершилась с ошибкой.';
                }
            }
        );
    }

    async function startMlModelJob(options, handlers) {
        var settings = options || {};
        var callbacks = withHandlers(handlers);
        var requestPayload = buildRequestPayload(settings);

        stopJobPolling();
        currentJobState = null;
        notifyBusy(callbacks, true);
        callbacks.__requestBody = requestPayload.body;
        if (typeof callbacks.onStart === 'function') {
            callbacks.onStart(requestPayload, settings);
        }

        try {
            var result = await apiCall('/api/ml-model-jobs', {
                method: 'POST',
                headers: {
                    Accept: 'application/json',
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(requestPayload.body)
            }, 'Не удалось запустить ML-задачу.');
            var payload = result.payload;
            notifyJobState(callbacks, payload);

            global.history.replaceState(
                {},
                '',
                requestPayload.query ? (global.location.pathname + '?' + requestPayload.query) : global.location.pathname
            );

            if (payload.status === 'failed' || payload.status === 'missing') {
                throw new Error(payload && payload.error_message ? payload.error_message : 'Не удалось запустить ML-задачу.');
            }

            if (payload.status === 'completed' && payload.result) {
                notifyBusy(callbacks, false);
                notifyCompleted(callbacks, payload.result, payload, requestPayload.body);
                return;
            }

            pollMlJob(payload.job_id, callbacks);
        } catch (error) {
            notifyBusy(callbacks, false);
            notifyError(callbacks, error, 'Не удалось запустить ML-анализ. Попробуйте еще раз.');
        }
    }

    async function fetchMlCompareSeries(options) {
        var settings = options || {};
        var requestPayload = buildRequestPayload(settings);
        var body = (typeof settings.buildPayload === 'function')
            ? (settings.buildPayload(requestPayload.body || {}) || {})
            : (requestPayload.body || {});
        var comparePayload = {
            table_name: body.table_name || 'all',
            table_names: Array.isArray(body.table_names) ? body.table_names : [],
            cause: body.cause || 'all',
            object_category: body.object_category || 'all',
            month: body.month || '',
            year_a: body.year_a || '',
            year_b: body.year_b || '',
            current_user_date: body.current_user_date || getCurrentUserDateIso()
        };
        var result;
        try {
            result = await apiCall('/api/ml-compare-series', {
                method: 'POST',
                headers: {
                    Accept: 'application/json',
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(comparePayload)
            }, 'Не удалось загрузить compare-series.');
        } catch (error) {
            if (!(error && Number(error.status) === 404)) {
                throw error;
            }
            result = await fetchMlCompareSeriesViaJob(comparePayload);
        }
        return {
            payload: result.payload || {},
            requestBody: comparePayload
        };
    }

    async function fetchMlCompareSeriesViaJob(comparePayload) {
        var start = await apiCall('/api/ml-model-jobs', {
            method: 'POST',
            headers: {
                Accept: 'application/json',
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(comparePayload)
        }, 'Не удалось запустить ML-задачу для compare-series.');
        var startPayload = start.payload || {};
        if (startPayload.status === 'completed' && startPayload.result) {
            return {
                payload: {
                    status: 'completed',
                    result: {
                        compare_series: (startPayload.result && startPayload.result.compare_series) || {},
                        filters: (startPayload.result && startPayload.result.filters) || {}
                    }
                },
                response: start.response
            };
        }
        if (!startPayload.job_id) {
            throw new Error((startPayload && startPayload.error_message) || 'Не удалось получить задачу compare-series.');
        }

        return await new Promise(function (resolve, reject) {
            pollUntilDone(
                '/api/ml-model-jobs/' + encodeURIComponent(startPayload.job_id),
                {
                    requestOptions: { headers: { Accept: 'application/json' } },
                    fallbackMessage: 'Не удалось дождаться результата compare-series.'
                },
                {
                    onDone: function (payload, response) {
                        var result = payload && payload.result ? payload.result : {};
                        resolve({
                            payload: {
                                status: 'completed',
                                result: {
                                    compare_series: result.compare_series || {},
                                    filters: result.filters || {}
                                }
                            },
                            response: response
                        });
                    },
                    onError: function (error) {
                        reject(error);
                    }
                },
                {
                    intervalMs: 800,
                    isDone: function (payload) {
                        return Boolean(payload && payload.status === 'completed' && payload.result);
                    },
                    isFailed: function (payload) {
                        return Boolean(payload && (payload.status === 'failed' || payload.status === 'missing'));
                    },
                    getFailureMessage: function (payload) {
                        return payload && payload.error_message
                            ? payload.error_message
                            : 'Не удалось получить результат compare-series.';
                    }
                }
            );
        });
    }

    global.MlModelApi = {
        buildPayloadFromQuery: buildPayloadFromQuery,
        buildQueryFromForm: buildQueryFromForm,
        buildRequestPayload: buildRequestPayload,
        getCurrentJobState: function () {
            return currentJobState;
        },
        isFetching: function () {
            return isFetching;
        },
        pollMlJob: pollMlJob,
        fetchMlCompareSeries: fetchMlCompareSeries,
        startMlModelJob: startMlModelJob,
        stopJobPolling: stopJobPolling
    };
}(window));
