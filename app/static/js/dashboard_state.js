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

                return {
                    table_name: selectedTableNames.length === 1 ? selectedTableNames[0] : 'all',
                    table_names: selectedTableNames,
                    group_column: byId('groupColumnFilter') ? byId('groupColumnFilter').value : ''
                };
            }

            return {
                collectSelectedFilters: collectSelectedFilters,
                getInitialData: getInitialData
            };
        }
    };
}(window));
