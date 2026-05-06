(function () {
    var shared = window.FireUi;
    var byId = shared.byId;
    var escapeHtml = shared.escapeHtml;
    var fetchJson = shared.fetchJson;

    function setStatus(message, tone) {
        var node = byId('tableActionStatus');
        if (!node) {
            return;
        }

        if (!message) {
            node.textContent = '';
            node.dataset.tone = '';
            node.classList.add('is-hidden');
            return;
        }

        node.textContent = message;
        node.dataset.tone = tone || 'info';
        node.classList.remove('is-hidden');
    }

    function setButtonBusy(button, isBusy, busyLabel) {
        if (!button) {
            return;
        }

        if (!button.dataset.defaultLabel) {
            button.dataset.defaultLabel = button.textContent || '';
        }

        if (isBusy) {
            button.dataset.wasDisabled = button.disabled ? 'true' : 'false';
            button.disabled = true;
        } else {
            button.disabled = button.dataset.wasDisabled === 'true';
            delete button.dataset.wasDisabled;
        }

        button.classList.toggle('is-loading', !!isBusy);
        button.textContent = isBusy ? (busyLabel || button.dataset.defaultLabel) : button.dataset.defaultLabel;
    }

    function updateCount(id, value) {
        var node = byId(id);
        if (node) {
            node.textContent = String(value);
        }
    }

    function updateAvailability(count) {
        var badge = byId('tableAvailabilityBadge');
        if (!badge) {
            return;
        }

        if (count > 0) {
            badge.textContent = 'Р‘Р°Р·Р° РґРѕСЃС‚СѓРїРЅР°';
            badge.classList.add('status-badge-live');
            return;
        }

        badge.textContent = 'РўР°Р±Р»РёС† РЅРµС‚';
        badge.classList.remove('status-badge-live');
    }

    function buildTableCard(tableName) {
        var safeTable = String(tableName || '');
        var href = '/tables/' + encodeURIComponent(safeTable);

        return '<li class="table-link-item" data-table-row data-table-name="' + escapeHtml(safeTable) + '">' +
            '<article class="table-link-card table-link-record">' +
                '<div class="table-link-record-head">' +
                    '<label class="table-selection-check">' +
                        '<input class="table-selection-checkbox" type="checkbox" value="' + escapeHtml(safeTable) + '" aria-label="Выбрать таблицу ' + escapeHtml(safeTable) + '">' +
                    '</label>' +
                    '<a class="table-link-title" href="' + href + '">' + escapeHtml(safeTable) + '</a>' +
                '</div>' +
                '<div class="table-link-actions">' +
                    '<a class="table-link-inline-action" href="' + href + '">РћС‚РєСЂС‹С‚СЊ</a>' +
                '</div>' +
            '</article>' +
        '</li>';
    }

    function renderTableList(tableNames) {
        var list = byId('tableList');
        var emptyState = byId('tableListEmpty');
        if (!list || !emptyState) {
            return;
        }

        if (!Array.isArray(tableNames) || !tableNames.length) {
            list.innerHTML = '';
            list.dataset.hasItems = 'false';
            list.classList.add('is-hidden');
            list.hidden = true;
            emptyState.classList.remove('is-hidden');
            emptyState.hidden = false;
            return;
        }

        list.innerHTML = tableNames.map(buildTableCard).join('');
        list.dataset.hasItems = 'true';
        list.classList.remove('is-hidden');
        list.hidden = false;
        emptyState.classList.add('is-hidden');
        emptyState.hidden = true;
    }

    function getRenderedTableNames() {
        return Array.prototype.slice
            .call(document.querySelectorAll('#tableList [data-table-row][data-table-name]'))
            .map(function (row) { return String(row.getAttribute('data-table-name') || '').trim(); })
            .filter(function (tableName) { return !!tableName; });
    }

    function getSelectionInputs() {
        return Array.prototype.slice.call(document.querySelectorAll('.table-selection-checkbox'));
    }

    function getSelectedTableNames() {
        return getSelectionInputs()
            .filter(function (input) { return input.checked; })
            .map(function (input) { return String(input.value || '').trim(); })
            .filter(function (tableName) { return !!tableName; });
    }

    function refreshSelectionState() {
        var inputs = getSelectionInputs();
        var selectedNames = getSelectedTableNames();
        var hasTables = inputs.length > 0;
        var selectedCount = selectedNames.length;

        var meta = byId('tablesSelectionMeta');
        if (meta) {
            meta.textContent = hasTables ? ('Р’С‹Р±СЂР°РЅРѕ: ' + selectedCount) : 'РўР°Р±Р»РёС† РЅРµС‚';
        }

        var selectAllButton = byId('selectAllTablesButton');
        if (selectAllButton) {
            selectAllButton.disabled = !hasTables;
        }

        var clearButton = byId('clearSelectedTablesButton');
        if (clearButton) {
            clearButton.disabled = !selectedCount;
        }

        var deleteButton = byId('deleteSelectedTablesButton');
        if (deleteButton) {
            deleteButton.disabled = !selectedCount;
            deleteButton.dataset.defaultLabel = selectedCount > 0
                ? ('РЈРґР°Р»РёС‚СЊ РІС‹Р±СЂР°РЅРЅС‹Рµ (' + selectedCount + ')')
                : 'РЈРґР°Р»РёС‚СЊ РІС‹Р±СЂР°РЅРЅС‹Рµ';
            if (!deleteButton.classList.contains('is-loading')) {
                deleteButton.textContent = deleteButton.dataset.defaultLabel;
            }
        }
    }

    function applyTableState(tableNames) {
        var items = Array.isArray(tableNames) ? tableNames : [];
        renderTableList(items);
        updateCount('heroTablesCount', items.length);
        updateCount('sidebarTablesCount', items.length);
        updateAvailability(items.length);
        refreshSelectionState();
    }

    function selectAllTables(isChecked) {
        getSelectionInputs().forEach(function (input) {
            input.checked = !!isChecked;
        });
        refreshSelectionState();
    }

    function confirmDelete(tableNames) {
        var count = tableNames.length;
        var preview = tableNames.slice(0, 5).join(', ');
        var suffix = count > 5 ? '\n\nРџРµСЂРІС‹Рµ РІС‹Р±СЂР°РЅРЅС‹Рµ: ' + preview + '...' : '\n\nР’С‹Р±СЂР°РЅС‹: ' + preview;
        return window.confirm('РЈРґР°Р»РёС‚СЊ РІС‹Р±СЂР°РЅРЅС‹Рµ С‚Р°Р±Р»РёС†С‹ РёР· Р±Р°Р·С‹ РґР°РЅРЅС‹С…?\n\nРљРѕР»РёС‡РµСЃС‚РІРѕ: ' + count + suffix + '\n\nР­С‚Рѕ РґРµР№СЃС‚РІРёРµ РЅРµРѕР±СЂР°С‚РёРјРѕ.');
    }

    async function requestBulkDelete(button) {
        var selectedNames = getSelectedTableNames();
        if (!selectedNames.length) {
            setStatus('РЎРЅР°С‡Р°Р»Р° РѕС‚РјРµС‚СЊС‚Рµ С‚Р°Р±Р»РёС†С‹ РіР°Р»РѕС‡РєР°РјРё.', 'error');
            refreshSelectionState();
            return;
        }

        if (!confirmDelete(selectedNames)) {
            return;
        }

        setStatus('РЈРґР°Р»СЏРµРј РІС‹Р±СЂР°РЅРЅС‹Рµ С‚Р°Р±Р»РёС†С‹...', 'info');
        setButtonBusy(button, true, 'РЈРґР°Р»РµРЅРёРµ...');

        try {
            var result = await fetchJson('/api/tables/delete', {
                method: 'POST',
                headers: {
                    'Accept': 'application/json',
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    table_names: selectedNames
                })
            }, 'РќРµ СѓРґР°Р»РѕСЃСЊ СѓРґР°Р»РёС‚СЊ С‚Р°Р±Р»РёС†С‹.');

            var payload = result.payload;
            if (!payload || payload.ok !== true) {
                throw new Error(payload && payload.message ? payload.message : 'РќРµ СѓРґР°Р»РѕСЃСЊ СѓРґР°Р»РёС‚СЊ С‚Р°Р±Р»РёС†С‹.');
            }

            var remainingTables = Array.isArray(payload.remaining_tables) ? payload.remaining_tables : [];
            applyTableState(remainingTables);
            setStatus(payload.message || 'Р’С‹Р±СЂР°РЅРЅС‹Рµ С‚Р°Р±Р»РёС†С‹ СѓРґР°Р»РµРЅС‹ РёР· Р±Р°Р·С‹ РґР°РЅРЅС‹С….', 'success');
        } catch (error) {
            console.error(error);
            setStatus(error && error.message ? error.message : 'РќРµ СѓРґР°Р»РѕСЃСЊ СѓРґР°Р»РёС‚СЊ С‚Р°Р±Р»РёС†С‹.', 'error');
        } finally {
            setButtonBusy(button, false);
            refreshSelectionState();
        }
    }

    function bindSelectionActions() {
        var selectAllButton = byId('selectAllTablesButton');
        if (selectAllButton) {
            selectAllButton.addEventListener('click', function () {
                selectAllTables(true);
            });
        }

        var clearButton = byId('clearSelectedTablesButton');
        if (clearButton) {
            clearButton.addEventListener('click', function () {
                selectAllTables(false);
            });
        }

        var deleteButton = byId('deleteSelectedTablesButton');
        if (deleteButton) {
            deleteButton.addEventListener('click', function () {
                requestBulkDelete(deleteButton);
            });
        }

        document.addEventListener('change', function (event) {
            var target = event.target;
            if (!(target instanceof Element) || !target.classList.contains('table-selection-checkbox')) {
                return;
            }

            refreshSelectionState();
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        window.fireTables = {
            afterImport: function () {
                setStatus('РРјРїРѕСЂС‚ Р·Р°РІРµСЂС€С‘РЅ. РћР±РЅРѕРІР»СЏРµРј СЃРїРёСЃРѕРє С‚Р°Р±Р»РёС†...', 'success');
                window.setTimeout(function () {
                    window.location.reload();
                }, 900);
            }
        };

        bindSelectionActions();
        applyTableState(getRenderedTableNames());
    });
})();

