(function (global) {
    var shared = global.FireUi || {};

    global.DashboardEvents = {
        init: function initDashboardPage(options) {
            var byId = shared.byId;
            var createTableChecklist = shared.createTableChecklist;
            var initTableFilter = shared.initTableFilter;
            if (!byId) {
                return;
            }

            var form = byId('filtersForm');
            var selectAllButton = byId('dashboardTableSelectAllButton');
            var clearAllButton = byId('dashboardTableClearAllButton');
            var dashboardTableChecklist = typeof createTableChecklist === 'function'
                ? createTableChecklist({
                    rootId: 'dashboardTableFilter',
                    menuId: 'dashboardTableFilterMenu',
                    toggleId: 'dashboardTableFilterToggle',
                    summaryId: 'dashboardTableFilterSummary',
                    selectedListId: 'dashboardTableFilterSelectedList',
                    itemClassName: 'dashboard-table-checklist-item',
                    singleSelectedPrefix: '\u0412\u044b\u0431\u0440\u0430\u043d\u0430: ',
                    compactSelectedList: true,
                    selectedListMode: 'chips',
                    selectAllWhenEmpty: true
                })
                : null;

            if (typeof initTableFilter === 'function') {
                initTableFilter({
                    checklist: dashboardTableChecklist,
                    rootId: 'dashboardTableFilter',
                    toggleId: 'dashboardTableFilterToggle',
                    formId: 'filtersForm',
                    onOpen: function () {
                        if (options && typeof options.onTableFilterOpen === 'function') {
                            options.onTableFilterOpen();
                        }
                    },
                    onChange: function () {
                        updateTableSummary();
                        if (options && typeof options.onTableFilterChange === 'function') {
                            options.onTableFilterChange();
                        }
                    }
                });
            }

            function updateTableSummary() {
                if (dashboardTableChecklist && typeof dashboardTableChecklist.syncSummary === 'function') {
                    dashboardTableChecklist.syncSummary();
                }
            }

            if (form) {
                form.addEventListener('change', function (event) {
                    if (event && event.target && event.target.name === 'table_names') {
                        return;
                    }
                    if (options && typeof options.onFilterChange === 'function') {
                        options.onFilterChange();
                    }
                });
            }

            if (selectAllButton) {
                selectAllButton.addEventListener('click', function (event) {
                    event.preventDefault();
                    if (dashboardTableChecklist && typeof dashboardTableChecklist.selectAll === 'function') {
                        dashboardTableChecklist.selectAll();
                    }
                    updateTableSummary();
                    if (options && typeof options.onSelectAllTables === 'function') {
                        options.onSelectAllTables();
                    }
                });
            }

            if (clearAllButton) {
                clearAllButton.addEventListener('click', function (event) {
                    event.preventDefault();
                    if (dashboardTableChecklist && typeof dashboardTableChecklist.clearAll === 'function') {
                        dashboardTableChecklist.clearAll();
                    }
                    updateTableSummary();
                    if (options && typeof options.onClearAllTables === 'function') {
                        options.onClearAllTables();
                    }
                });
            }

            updateTableSummary();

            if (form) {
                form.addEventListener('submit', function (event) {
                    event.preventDefault();
                    if (options && typeof options.onSubmit === 'function') {
                        options.onSubmit();
                    }
                });
            }

            var retryButton = byId('dashboardInlineRetryButton');
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
