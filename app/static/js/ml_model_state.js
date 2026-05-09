(function (global) {
    var shared = global.FireUi || {};
    var byId = shared.byId;
    var createTableChecklist = shared.createTableChecklist;
    var factory = global.FireStateFactory || {};
    var createModuleState = factory.createModuleState;

    global.MlModelState = {
        create: function createMlModelState(options) {
            var initialData = options && options.initialData ? options.initialData : null;
            var state = typeof createModuleState === 'function'
                ? createModuleState('ml_model', { currentData: initialData })
                : null;
            var fallbackCurrentData = initialData;
            var mlTableChecklist = typeof createTableChecklist === 'function'
                ? createTableChecklist({
                    menuId: 'mlTableFilterMenu'
                })
                : null;

            function setCurrentData(data) {
                if (!state) {
                    fallbackCurrentData = data || null;
                    return fallbackCurrentData;
                }
                return state.set('currentData', data || null);
            }

            function getCurrentData() {
                return state ? state.get('currentData') : fallbackCurrentData;
            }

            function collectSelectedFilters() {
                var selectedTableNames = mlTableChecklist && typeof mlTableChecklist.getSelectedValues === 'function'
                    ? mlTableChecklist.getSelectedValues()
                    : [];
                return {
                    table_name: selectedTableNames.length === 1 ? selectedTableNames[0] : 'all',
                    table_names: selectedTableNames,
                    cause: byId('mlCauseFilter') ? byId('mlCauseFilter').value : 'all',
                    object_category: byId('mlObjectCategoryFilter') ? byId('mlObjectCategoryFilter').value : 'all'
                };
            }

            return {
                collectSelectedFilters: collectSelectedFilters,
                getCurrentData: getCurrentData,
                setCurrentData: setCurrentData
            };
        }
    };
}(window));
