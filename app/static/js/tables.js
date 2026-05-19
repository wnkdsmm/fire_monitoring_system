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
            badge.textContent = 'База доступна';
            badge.classList.add('status-badge-live');
            return;
        }

        badge.textContent = 'Таблиц нет';
        badge.classList.remove('status-badge-live');
    }

    function buildTableCard(tableName) {
        var safeTable = String(tableName || '');
        var href = '/tables/' + encodeURIComponent(safeTable);

        return '<li class="table-link-item" data-table-row data-table-name="' + escapeHtml(safeTable) + '">' +
            '<article class="table-link-card table-link-record" data-href="' + href + '">' +
                '<div class="table-link-record-head">' +
                    '<label class="table-selection-check">' +
                        '<input class="table-selection-checkbox" type="checkbox" value="' + escapeHtml(safeTable) + '" aria-label="Выбрать таблицу ' + escapeHtml(safeTable) + '">' +
                    '</label>' +
                    '<span class="table-link-title">' + escapeHtml(safeTable) + '</span>' +
                '</div>' +
                
                    
                
            '</article>' +
        '</li>';
    }

    function sortTableNames(tableNames) {
        var collator = new Intl.Collator('ru', { numeric: true, sensitivity: 'base' });
        return (Array.isArray(tableNames) ? tableNames.slice() : [])
            .map(function (name) { return String(name || '').trim(); })
            .filter(function (name) { return name.length > 0; })
            .sort(function (left, right) { return collator.compare(left, right); });
    }

    function renderTableList(tableNames) {
        var list = byId('tableList');
        var emptyState = byId('tableListEmpty');
        if (!list || !emptyState) {
            return;
        }

        var sortedNames = sortTableNames(tableNames);
        if (!sortedNames.length) {
            list.innerHTML = '';
            list.dataset.hasItems = 'false';
            list.classList.add('is-hidden');
            list.hidden = true;
            emptyState.classList.remove('is-hidden');
            emptyState.hidden = false;
            return;
        }

        list.innerHTML = sortedNames.map(buildTableCard).join('');
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

    function isVisibleRow(row) {
        return !!(row && row.offsetParent !== null);
    }

    function getVisibleSelectionInputs() {
        return getSelectionInputs().filter(function (input) {
            var row = input.closest('[data-table-row]');
            return isVisibleRow(row);
        });
    }

    function isClearTableName(tableName) {
        return String(tableName || '').toLowerCase().indexOf('clean_') === 0;
    }

    function refreshTypeStats() {
        var rows = Array.prototype.slice.call(document.querySelectorAll('#tableList [data-table-row][data-table-name]'));
        var cleanCount = 0;
        var baseCount = 0;

        rows.forEach(function (row) {
            var tableName = String(row.getAttribute('data-table-name') || '').trim();
            if (!tableName) {
                return;
            }
            if (isClearTableName(tableName)) {
                cleanCount += 1;
            } else {
                baseCount += 1;
            }
        });

        updateCount('cleanTablesCount', cleanCount);
        updateCount('baseTablesCount', baseCount);
    }

    function applyClearTablesFilter() {
        var searchInput = byId('tableSearchInput');
        var toggle = byId('toggleClearTables');
        var showClearTables = !toggle || !!toggle.checked;
        var query = String(searchInput && searchInput.value ? searchInput.value : '').trim().toLowerCase();
        var rows = Array.prototype.slice.call(document.querySelectorAll('#tableList [data-table-row][data-table-name]'));

        if (query && toggle && !showClearTables) {
            var hasMatchInBase = rows.some(function (row) {
                var tableName = String(row.getAttribute('data-table-name') || '').trim();
                return !isClearTableName(tableName) && tableName.toLowerCase().indexOf(query) !== -1;
            });
            var hasMatchInClean = rows.some(function (row) {
                var tableName = String(row.getAttribute('data-table-name') || '').trim();
                return isClearTableName(tableName) && tableName.toLowerCase().indexOf(query) !== -1;
            });
            if (!hasMatchInBase && hasMatchInClean) {
                toggle.checked = true;
                showClearTables = true;
            }
        }

        rows.forEach(function (row) {
            var tableName = String(row.getAttribute('data-table-name') || '').trim();
            var matchesQuery = !query || tableName.toLowerCase().indexOf(query) !== -1;
            var shouldHide = !matchesQuery || (!showClearTables && isClearTableName(tableName));
            row.hidden = shouldHide;
        });

        if (toggle) {
            var label = toggle.closest('label');
            var textNode = label ? label.querySelector('span') : null;
            if (textNode) {
                textNode.textContent = showClearTables
                    ? 'Очищенные таблицы: показывать'
                    : 'Очищенные таблицы: не показывать';
            }
        }
    }

    function getSelectedTableNames() {
        return getVisibleSelectionInputs()
            .filter(function (input) { return input.checked; })
            .map(function (input) { return String(input.value || '').trim(); })
            .filter(function (tableName) { return !!tableName; });
    }

    function refreshSelectionState() {
        var inputs = getVisibleSelectionInputs();
        var selectedNames = getSelectedTableNames();
        var hasTables = inputs.length > 0;
        var selectedCount = selectedNames.length;

        var meta = byId('tablesSelectionMeta');
        if (meta) {
            meta.textContent = hasTables ? ('Выбрано: ' + selectedCount) : 'Таблиц нет';
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
                ? ('Удалить выбранные (' + selectedCount + ')')
                : 'Удалить выбранные';
            if (!deleteButton.classList.contains('is-loading')) {
                deleteButton.textContent = deleteButton.dataset.defaultLabel;
            }
        }
    }

    function applyTableState(tableNames) {
        var items = sortTableNames(tableNames);
        renderTableList(items);
        updateCount('heroTablesCount', items.length);
        updateCount('sidebarTablesCount', items.length);
        updateAvailability(items.length);
        refreshTypeStats();
        refreshSelectionState();
    }

    function selectAllTables(isChecked) {
        getVisibleSelectionInputs().forEach(function (input) {
            input.checked = !!isChecked;
        });
        refreshSelectionState();
    }

    function confirmDelete(tableNames) {
        var count = tableNames.length;
        var preview = tableNames.slice(0, 5).join(', ');
        var suffix = count > 5 ? '\n\nПервые выбранные: ' + preview + '...' : '\n\nВыбраны: ' + preview;
        return window.confirm('Удалить выбранные таблицы из базы данных?\n\nКоличество: ' + count + suffix + '\n\nЭто действие необратимо.');
    }

    async function requestBulkDelete(button) {
        var selectedNames = getSelectedTableNames();
        if (!selectedNames.length) {
            setStatus('Сначала отметьте таблицы галочками.', 'error');
            refreshSelectionState();
            return;
        }

        if (!confirmDelete(selectedNames)) {
            return;
        }

        setStatus('Удаляем выбранные таблицы...', 'info');
        setButtonBusy(button, true, 'Удаление...');

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
            }, 'Не удалось удалить таблицы.');

            var payload = result.payload;
            if (!payload || payload.ok !== true) {
                throw new Error(payload && payload.message ? payload.message : 'Не удалось удалить таблицы.');
            }

            var remainingTables = Array.isArray(payload.remaining_tables) ? payload.remaining_tables : [];
            applyTableState(remainingTables);
            setStatus(payload.message || 'Выбранные таблицы удалены из базы данных.', 'success');
        } catch (error) {
            console.error(error);
            setStatus(error && error.message ? error.message : 'Не удалось удалить таблицы.', 'error');
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

        var tableList = byId('tableList');
        if (tableList) {
            tableList.addEventListener('click', function (event) {
                var target = event.target;
                if (!(target instanceof Element)) {
                    return;
                }
                if (target.closest('.table-selection-check') || target.classList.contains('table-selection-checkbox')) {
                    return;
                }
                var card = target.closest('.table-link-card[data-href]');
                if (!card) {
                    return;
                }
                var href = card.getAttribute('data-href');
                if (href) {
                    window.location.href = href;
                }
            });
        }

        var toggle = byId('toggleClearTables');
        if (toggle) {
            toggle.addEventListener('change', function () {
                var scrollTop = window.scrollY || window.pageYOffset || 0;
                applyClearTablesFilter();
                refreshSelectionState();
                window.scrollTo(0, scrollTop);
            });
        }

        var searchInput = byId('tableSearchInput');
        if (searchInput) {
            searchInput.addEventListener('input', function () {
                var scrollTop = window.scrollY || window.pageYOffset || 0;
                applyClearTablesFilter();
                refreshSelectionState();
                window.scrollTo(0, scrollTop);
            });
        }
    }

    document.addEventListener('DOMContentLoaded', function () {
        window.fireTables = {
            afterImport: function () {
                setStatus('Импорт завершён. Обновляем список таблиц...', 'success');
                window.setTimeout(function () {
                    window.location.reload();
                }, 900);
            }
        };

        bindSelectionActions();
        applyTableState(getRenderedTableNames());
        applyClearTablesFilter();
        refreshTypeStats();
        refreshSelectionState();
    });
})();
