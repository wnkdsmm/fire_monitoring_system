(function (global) {
    var shared = global.FireUi || {};

    global.ClusteringEvents = {
        init: function initClusteringPage(options) {
            var byId = shared.byId;
            if (!byId) {
                return;
            }

            var form = byId('clusteringForm');
            var tableFilterRoot = byId('clusterTableFilter');
            var tableFilterToggle = byId('clusterTableFilterToggle');
            var tableSelectAllButton = byId('clusterTableSelectAllButton');
            var tableClearAllButton = byId('clusterTableClearAllButton');
            var retryButton = byId('clusteringRetryButton');
            var initialData = options && options.initialData ? options.initialData : null;

            if (form) {
                form.addEventListener('submit', function (event) {
                    event.preventDefault();
                    if (options && typeof options.onSubmit === 'function') {
                        options.onSubmit();
                    }
                });
            }

            if (tableFilterToggle) {
                tableFilterToggle.addEventListener('click', function (event) {
                    event.preventDefault();
                    event.stopPropagation();
                    if (options && typeof options.onToggleTableFilter === 'function') {
                        options.onToggleTableFilter();
                    }
                });
            }

            if (tableSelectAllButton) {
                tableSelectAllButton.addEventListener('click', function (event) {
                    event.preventDefault();
                    if (options && typeof options.onSelectAllTables === 'function') {
                        options.onSelectAllTables();
                    }
                });
            }

            if (tableClearAllButton) {
                tableClearAllButton.addEventListener('click', function (event) {
                    event.preventDefault();
                    if (options && typeof options.onClearAllTables === 'function') {
                        options.onClearAllTables();
                    }
                });
            }

            if (form) {
                form.addEventListener('change', function (event) {
                    if (!event || !event.target || event.target.name !== 'table_names') {
                        return;
                    }
                    if (typeof global.stopClusteringJobPolling === 'function') {
                        global.stopClusteringJobPolling();
                    }
                    if (options && typeof options.onTableFilterChange === 'function') {
                        options.onTableFilterChange();
                    }
                });
            }

            document.addEventListener('click', function (event) {
                if (!tableFilterRoot) {
                    return;
                }
                if (!tableFilterRoot.contains(event.target) && options && typeof options.onCloseTableFilter === 'function') {
                    options.onCloseTableFilter();
                }
            });

            document.addEventListener('keydown', function (event) {
                if (event && event.key === 'Escape' && options && typeof options.onCloseTableFilter === 'function') {
                    options.onCloseTableFilter();
                }
            });

            if (retryButton) {
                retryButton.addEventListener('click', function () {
                    if (options && typeof options.onRetry === 'function') {
                        options.onRetry();
                    }
                });
            }

            if (initialData && options && typeof options.onInitialData === 'function') {
                options.onInitialData(initialData);
            }

            if ((!initialData || initialData.bootstrap_mode === 'deferred') && options && typeof options.onDeferredLoad === 'function') {
                options.onDeferredLoad();
            }
        }
    };
}(window));
