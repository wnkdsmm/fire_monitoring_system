(function (global) {
    var shared = global.FireUi || {};
    var byId = shared.byId;
    var createTableChecklist = shared.createTableChecklist;
    var factory = global.FireStateFactory || {};
    var createModuleState = factory.createModuleState;

    global.DashboardState = {
        create: function createDashboardState(options) {
            var initialData = options && options.initialData ? options.initialData : null;
            var state = typeof createModuleState === 'function'
                ? createModuleState('dashboard', { initialData: initialData })
                : null;
            var fallbackInitialData = initialData;
            var dashboardTableChecklist = typeof createTableChecklist === 'function'
                ? createTableChecklist({
                    menuId: 'dashboardTableFilterMenu'
                })
                : null;

            function getInitialData() {
                return state ? state.get('initialData') : fallbackInitialData;
            }

            function collectSelectedFilters() {
                var selectedTableNames = dashboardTableChecklist && typeof dashboardTableChecklist.getSelectedValues === 'function'
                    ? dashboardTableChecklist.getSelectedValues()
                    : [];
                var totalTableOptions = Array.prototype.slice.call(
                    document.querySelectorAll('#dashboardTableFilterMenu input[name="table_names"]')
                ).length;
                var useAllTables = totalTableOptions > 0 && selectedTableNames.length === totalTableOptions;
                var normalizedTableNames = useAllTables ? [] : selectedTableNames;

                return {
                    table_name: normalizedTableNames.length === 1 ? normalizedTableNames[0] : 'all',
                    table_names: normalizedTableNames
                };
            }

            return {
                collectSelectedFilters: collectSelectedFilters,
                getInitialData: getInitialData
            };
        }
    };
}(window));
