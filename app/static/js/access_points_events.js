(function (global) {
    var shared = global.FireUi || {};

    global.AccessPointsEvents = {
        init: function initAccessPointsPage(options) {
            var byId = shared.byId;
            if (!byId) {
                return;
            }

            var form = byId('accessPointsForm');
            var tableFilterRoot = byId('accessPointsTableFilter');
            var tableFilterToggle = byId('accessPointsTableFilterToggle');
            var tableSelectAllButton = byId('accessPointsTableSelectAllButton');
            var tableClearAllButton = byId('accessPointsTableClearAllButton');
            if (form) {
                form.addEventListener('submit', function (event) {
                    event.preventDefault();
                    if (options && typeof options.onSubmit === 'function') {
                        options.onSubmit();
                    }
                });
                form.addEventListener('change', function (event) {
                    if (!event || !event.target || event.target.name !== 'table_names') {
                        return;
                    }
                    if (options && typeof options.onTableFilterChange === 'function') {
                        options.onTableFilterChange();
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

            var retryButton = byId('accessPointsRetryButton');
            if (retryButton) {
                retryButton.addEventListener('click', function () {
                    if (options && typeof options.onRetry === 'function') {
                        options.onRetry();
                    }
                });
            }

            if (options && typeof options.onBootstrap === 'function') {
                options.onBootstrap();
            }
        }
    };
}(window));
