(function (global) {
    var shared = global.FireUi || {};

    global.DashboardEvents = {
        init: function initDashboardPage(options) {
            var byId = shared.byId;
            var createTableChecklist = shared.createTableChecklist;
            if (!byId) {
                return;
            }

            var form = byId('filtersForm');
            var tableFilterRoot = byId('dashboardTableFilter');
            var tableFilterToggle = byId('dashboardTableFilterToggle');
            var dashboardTableChecklist = typeof createTableChecklist === 'function'
                ? createTableChecklist({
                    rootId: 'dashboardTableFilter',
                    menuId: 'dashboardTableFilterMenu',
                    toggleId: 'dashboardTableFilterToggle',
                    summaryId: 'dashboardTableFilterSummary',
                    selectedListId: 'dashboardTableFilterSelectedList',
                    itemClassName: 'dashboard-table-checklist-item',
                    singleSelectedPrefix: '\u0412\u044b\u0431\u0440\u0430\u043d\u0430: '
                })
                : null;

            function updateTableSummary() {
                if (dashboardTableChecklist && typeof dashboardTableChecklist.syncSummary === 'function') {
                    dashboardTableChecklist.syncSummary();
                }
            }

            function setTableFilterOpen(isOpen) {
                if (dashboardTableChecklist && typeof dashboardTableChecklist.setOpen === 'function') {
                    dashboardTableChecklist.setOpen(isOpen);
                }
            }

            if (tableFilterToggle) {
                tableFilterToggle.addEventListener('click', function (event) {
                    event.preventDefault();
                    event.stopPropagation();
                    var isOpen = tableFilterRoot && tableFilterRoot.classList.contains('is-open');
                    setTableFilterOpen(!isOpen);
                });
            }

            if (form) {
                form.addEventListener('change', function (event) {
                    updateTableSummary();
                    if (options && typeof options.onFilterChange === 'function') {
                        options.onFilterChange();
                    }
                });
            }

            document.addEventListener('click', function (event) {
                if (!tableFilterRoot) {
                    return;
                }
                if (!tableFilterRoot.contains(event.target)) {
                    setTableFilterOpen(false);
                }
            });

            document.addEventListener('keydown', function (event) {
                if (event && event.key === 'Escape') {
                    setTableFilterOpen(false);
                }
            });

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
