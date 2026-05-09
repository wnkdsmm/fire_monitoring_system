(function (global) {
    var uiHelpers = global.FireUiHelpers || {};
    var plotlyHelpers = global.FirePlotlyHelpers || {};
    var apiClient = global.FireApiClient || {};

    function byId(id) {
        return typeof uiHelpers.byId === 'function' ? uiHelpers.byId(id) : document.getElementById(id);
    }

    function setText(nodeOrId, value) {
        if (typeof uiHelpers.setText === 'function') {
            uiHelpers.setText(nodeOrId, value);
            return;
        }
        var node = typeof nodeOrId === 'string' ? byId(nodeOrId) : nodeOrId;
        if (node) {
            node.textContent = value == null ? '' : value;
        }
    }

    function createTimerGroup() {
        var timers = [];
        return {
            clear: function () {
                while (timers.length) {
                    clearTimeout(timers.pop());
                }
            },
            set: function (callback, delay) {
                var timer = setTimeout(callback, delay);
                timers.push(timer);
                return timer;
            },
            push: function (timer) {
                timers.push(timer);
                return timer;
            }
        };
    }

    function createSingleTimer() {
        var timer = null;
        return {
            clear: function () {
                if (timer) {
                    clearTimeout(timer);
                    timer = null;
                }
            },
            set: function (callback, delay) {
                this.clear();
                timer = setTimeout(callback, delay);
                return timer;
            }
        };
    }

    function runProgressSequence(timerGroup, updateProgress, entries) {
        var safeEntries = Array.isArray(entries) ? entries : [];
        if (timerGroup && typeof timerGroup.clear === 'function') {
            timerGroup.clear();
        }
        safeEntries.forEach(function (entry) {
            var safeEntry = entry || {};
            var run = function () {
                updateProgress(safeEntry.activeIndex, safeEntry.options || {});
            };
            if (safeEntry.delay && safeEntry.delay > 0 && timerGroup && typeof timerGroup.set === 'function') {
                timerGroup.set(run, safeEntry.delay);
                return;
            }
            run();
        });
    }

    function setStepProgress(config) {
        var settings = config || {};
        var activeIndex = settings.activeIndex;
        var stepsNode = byId(settings.stepsId);
        var lead = settings.lead || '';
        var message = settings.message || '';
        var isFinished = Boolean(settings.isFinished);
        var isError = Boolean(settings.isError);
        var stepSelector = settings.stepSelector || '.analysis-step';

        setText(settings.leadId, lead);
        setText(settings.messageId, message);

        if (!stepsNode) {
            return;
        }

        Array.prototype.forEach.call(stepsNode.querySelectorAll(stepSelector), function (node, index) {
            node.classList.remove('is-active', 'is-done', 'is-error');
            if (isError && index === activeIndex) {
                node.classList.add('is-error');
                return;
            }
            if (isFinished) {
                if (index <= activeIndex) {
                    node.classList.add('is-done');
                }
                return;
            }
            if (index < activeIndex) {
                node.classList.add('is-done');
                return;
            }
            if (index === activeIndex) {
                node.classList.add('is-active');
            }
        });
    }

    function getErrorMessage(error, fallback) {
        var message = error && typeof error.message === 'string' ? error.message.trim() : '';
        return message || fallback;
    }

    function revealPageContent() {
        if (document && document.body) {
            document.body.removeAttribute('data-page-loading');
        }
    }

    function createTableChecklist(config) {
        var settings = config || {};
        var checkboxName = settings.checkboxName || 'table_names';
        var rootId = settings.rootId || '';
        var menuId = settings.menuId || '';
        var toggleId = settings.toggleId || '';
        var summaryId = settings.summaryId || '';
        var selectedListId = settings.selectedListId || '';
        var itemClassName = settings.itemClassName || 'table-checklist-item';
        var allSelectedLabel = settings.allSelectedLabel || '\u0412\u044b\u0431\u0440\u0430\u043d\u044b \u0432\u0441\u0435 \u0442\u0430\u0431\u043b\u0438\u0446\u044b';
        var selectedPrefix = settings.selectedPrefix || '\u0412\u044b\u0431\u0440\u0430\u043d\u044b: ';
        var singleSelectedPrefix = settings.singleSelectedPrefix || selectedPrefix;
        var selectedListPrefix = settings.selectedListPrefix || '\u0422\u0430\u0431\u043b\u0438\u0446\u044b: ';
        var maxSummaryNames = Number.isFinite(settings.maxSummaryNames) ? settings.maxSummaryNames : 2;
        var esc = typeof uiHelpers.escapeHtml === 'function'
            ? uiHelpers.escapeHtml
            : function (value) {
                return String(value == null ? '' : value)
                    .replace(/&/g, '&amp;')
                    .replace(/</g, '&lt;')
                    .replace(/>/g, '&gt;')
                    .replace(/"/g, '&quot;')
                    .replace(/'/g, '&#39;');
            };

        function normalizeValue(value) {
            return String(value == null ? '' : value).trim();
        }

        function getNode(id) {
            return id ? byId(id) : null;
        }

        function getSelectedValues() {
            if (!menuId) {
                return [];
            }
            return Array.prototype.map.call(
                document.querySelectorAll('#' + menuId + ' input[name="' + checkboxName + '"]:checked'),
                function (node) { return normalizeValue(node.value); }
            ).filter(function (value) { return value.length > 0; });
        }

        function summarizeSelected(values) {
            var list = Array.isArray(values) ? values : [];
            if (!list.length) {
                return allSelectedLabel;
            }
            var safeMax = maxSummaryNames > 0 ? maxSummaryNames : 2;
            if (list.length === 1) {
                return singleSelectedPrefix + list[0];
            }
            var visible = list.slice(0, safeMax).join(', ');
            var extraCount = list.length - safeMax;
            if (extraCount > 0) {
                return selectedPrefix + visible + ' +' + extraCount;
            }
            return selectedPrefix + visible;
        }

        function renderSelectedLabel(values) {
            var labelNode = getNode(selectedListId);
            if (!labelNode) {
                return;
            }
            var list = Array.isArray(values) ? values : [];
            labelNode.textContent = list.length ? (selectedListPrefix + list.join(', ')) : allSelectedLabel;
        }

        function renderChecklist(options, selectedValues) {
            var container = getNode(menuId);
            var summaryNode = getNode(summaryId);
            if (!container) {
                return;
            }

            var normalizedSelected = (Array.isArray(selectedValues) ? selectedValues : [])
                .map(normalizeValue)
                .filter(function (value) { return value.length > 0; });
            var selectedSet = new Set(normalizedSelected);
            var safeOptions = Array.isArray(options)
                ? options.filter(function (option) {
                    var optionValue = normalizeValue(option && option.value);
                    return optionValue && optionValue !== 'all';
                })
                : [];

            container.innerHTML = safeOptions.map(function (option) {
                var value = normalizeValue(option.value);
                var checked = selectedSet.has(value) ? ' checked' : '';
                return ''
                    + '<label class="' + esc(itemClassName) + '">'
                    + '<input type="checkbox" name="' + esc(checkboxName) + '" value="' + esc(value) + '"' + checked + '>'
                    + '<span>' + esc(option.label || value) + '</span>'
                    + '</label>';
            }).join('');

            if (summaryNode) {
                summaryNode.textContent = summarizeSelected(normalizedSelected);
            }
            renderSelectedLabel(normalizedSelected);
        }

        function syncSummary() {
            var summaryNode = getNode(summaryId);
            var selectedValues = getSelectedValues();
            if (summaryNode) {
                summaryNode.textContent = summarizeSelected(selectedValues);
            }
            renderSelectedLabel(selectedValues);
            return selectedValues;
        }

        function setOpen(isOpen) {
            var root = getNode(rootId);
            var menu = getNode(menuId);
            var toggle = getNode(toggleId);
            if (!root || !menu || !toggle) {
                return;
            }
            root.classList.toggle('is-open', !!isOpen);
            menu.classList.toggle('is-hidden', !isOpen);
            toggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
        }

        return {
            getSelectedValues: getSelectedValues,
            renderChecklist: renderChecklist,
            renderSelectedLabel: renderSelectedLabel,
            setOpen: setOpen,
            summarizeSelected: summarizeSelected,
            syncSummary: syncSummary
        };
    }

    global.FireUi = {
        applyToneClass: uiHelpers.applyToneClass,
        byId: byId,
        createJobId: uiHelpers.createJobId,
        createApiError: apiClient.createApiError,
        createSingleTimer: createSingleTimer,
        createTimerGroup: createTimerGroup,
        escapeHtml: uiHelpers.escapeHtml,
        apiCall: apiClient.apiCall,
        fetchJson: apiClient.apiCall,
        getApiErrorMessage: apiClient.getApiErrorMessage,
        getErrorMessage: getErrorMessage,
        normalizeCssColor: plotlyHelpers.normalizeCssColor,
        normalizePercent: plotlyHelpers.normalizePercent,
        renderListItems: uiHelpers.renderListItems,
        renderMetricCards: uiHelpers.renderMetricCards,
        renderPlotlyFigure: plotlyHelpers.renderPlotlyFigure,
        renderPlotlyInContainer: plotlyHelpers.renderPlotlyInContainer,
        createTableChecklist: createTableChecklist,
        runProgressSequence: runProgressSequence,
        revealPageContent: revealPageContent,
        setHref: uiHelpers.setHref,
        setHidden: uiHelpers.setHidden,
        setSectionHidden: uiHelpers.setSectionHidden,
        setSelectOptions: uiHelpers.setSelectOptions,
        setStepProgress: setStepProgress,
        setText: uiHelpers.setText,
        setValue: uiHelpers.setValue
    };
}(window));
