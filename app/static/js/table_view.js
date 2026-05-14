(function () {
    const shared = window.FireUi || {};
    const byId = typeof shared.byId === 'function'
        ? shared.byId
        : (id) => document.getElementById(id);
    const escapeHtml = typeof shared.escapeHtml === 'function'
        ? shared.escapeHtml
        : (value) => String(value ?? '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    const fetchJson = typeof shared.fetchJson === 'function'
        ? shared.fetchJson
        : async (url, options, defaultMessage) => {
            const response = await fetch(url, options);
            let payload = null;
            try {
                payload = await response.json();
            } catch (_error) {
                payload = null;
            }

            if (!response.ok) {
                const message = payload?.message || defaultMessage || 'Не удалось выполнить запрос.';
                throw new Error(message);
            }

            return { payload };
        };
    const root = document.querySelector('[data-table-name]') || byId('page-content');
    const tableName = root?.dataset.tableName;
    if (!root || !tableName) {
        return;
    }

    let form = byId('tablePaginationForm');
    const pageInput = byId('tablePageInput');
    let pageSizeSelect = byId('tablePageSize');
    let prevLink = byId('tablePrevLink');
    let nextLink = byId('tableNextLink');
    const pageCount = byId('tablePageCount');
    const pageStatus = byId('tablePageStatus');
    const pageSizeValue = byId('tablePageSizeValue');
    const tableHead = byId('tableDataHead');
    const tableBody = byId('tableDataBody');
    const tableElement = byId('tableDataTable');
    const tableDataShell = byId('tableDataShell');
    const tableTopScroll = byId('tableTopScroll');
    const tableTopScrollInner = byId('tableTopScrollInner');
    const tableColumnsList = byId('tableColumnsList');
    const tableColumnsMeta = byId('tableColumnsMeta');
    const tableColumnsSelectAllButton = byId('tableColumnsSelectAllButton');
    const tableColumnsClearButton = byId('tableColumnsClearButton');
    const sidebarTotalRows = byId('sidebarTotalRows');
    const sidebarPageNumber = byId('sidebarPageNumber');
    const sidebarShownRows = byId('sidebarShownRows');
    const heroTotalRows = byId('tableHeroTotalRows');
    const heroRange = byId('tableHeroRange');
    const heroPage = byId('tableHeroPage');
    const summaryLead = byId('tableSummaryLead');
    const summaryScopeNote = byId('tableSummaryScopeNote');
    const summaryCards = byId('tableSummaryCards');
    const criteriaLead = byId('tableCriteriaLead');
    const criteriaGroups = byId('tableCriteriaGroups');
    const inlineError = byId('tableInlineError');
    const inlineErrorMessage = byId('tableInlineErrorMessage');
    let inlineRetryButton = byId('tableInlineRetryButton');

    let isLoading = false;
    const POPSTATE_HANDLER_KEY = '__tableViewPopstateHandler__';
    const CELL_TRUNCATE_LIMIT = 40;
    let syncingTopScroll = false;
    let syncingBottomScroll = false;
    let currentColumns = [];
    let hiddenColumnIndexes = new Set();

    function replaceElementForFreshListeners(element) {
        if (!element) {
            return element;
        }
        const cloned = element.cloneNode(true);
        element.replaceWith(cloned);
        return cloned;
    }

    function formatInteger(value) {
        const numericValue = Number(value ?? 0);
        if (!Number.isFinite(numericValue)) {
            return '0';
        }
        return new Intl.NumberFormat('ru-RU').format(numericValue);
    }

    function buildPageUrl(page, pageSize) {
        const params = new URLSearchParams();
        params.set('page', String(page));
        params.set('page_size', String(pageSize));
        return `/tables/${encodeURIComponent(tableName)}?${params.toString()}`;
    }

    function buildApiUrl(page, pageSize) {
        const params = new URLSearchParams();
        params.set('page', String(page));
        params.set('page_size', String(pageSize));
        return `/api/tables/${encodeURIComponent(tableName)}/page?${params.toString()}`;
    }

    function setLinkState(link, enabled, page, pageSize) {
        if (!link) {
            return;
        }

        link.dataset.pageTarget = String(page);
        link.href = buildPageUrl(page, pageSize);
        link.classList.toggle('is-disabled', !enabled);
        link.setAttribute('aria-disabled', enabled ? 'false' : 'true');
        link.tabIndex = enabled ? 0 : -1;
    }

    function renderTableHead(columns) {
        if (!tableHead) {
            return;
        }

        const safeColumns = Array.isArray(columns) ? columns : [];
        tableHead.innerHTML = `<tr>${safeColumns.map((column, index) => `<th data-col-index="${index}">${escapeHtml(column)}</th>`).join('')}</tr>`;
        root.dataset.columnsCount = String(safeColumns.length);
        syncColumnsState(safeColumns);
        renderColumnsList();

        const useStackMobile = safeColumns.length <= 5;
        tableElement?.classList.toggle('table-stack-mobile', useStackMobile);
        tableElement?.classList.toggle('table-sticky-first', !useStackMobile);
        applyColumnVisibility();
        syncTopScrollbarGeometry();
    }

    function syncColumnsState(columns) {
        const safeColumns = Array.isArray(columns) ? columns.map((column) => String(column ?? '')) : [];
        const nextHidden = new Set();
        hiddenColumnIndexes.forEach((index) => {
            if (index >= 0 && index < safeColumns.length) {
                nextHidden.add(index);
            }
        });
        currentColumns = safeColumns;
        hiddenColumnIndexes = nextHidden;
    }

    function renderColumnsList() {
        if (!tableColumnsList) {
            return;
        }

        tableColumnsList.innerHTML = currentColumns
            .map((column, index) => {
                const isHidden = hiddenColumnIndexes.has(index);
                const stateClass = isHidden ? ' is-inactive' : '';
                const title = isHidden ? 'Показать колонку' : 'Скрыть колонку';
                return `<button type="button" class="table-columns-chip${stateClass}" data-column-index="${index}" title="${title}"><span>${escapeHtml(column)}</span></button>`;
            })
            .join('');

        refreshColumnSelectionState();
    }

    function refreshColumnSelectionState() {
        const totalCount = currentColumns.length;
        const hiddenCount = hiddenColumnIndexes.size;
        const visibleCount = Math.max(totalCount - hiddenCount, 0);

        if (tableColumnsMeta) {
            tableColumnsMeta.textContent = `Показано: ${visibleCount} / ${totalCount}`;
        }
        if (tableColumnsSelectAllButton) {
            tableColumnsSelectAllButton.disabled = totalCount === 0 || hiddenCount === 0;
        }
        if (tableColumnsClearButton) {
            tableColumnsClearButton.disabled = totalCount === 0 || visibleCount === 0;
        }
    }

    function applyColumnVisibility() {
        if (!tableElement || !currentColumns.length) {
            return;
        }

        tableElement.querySelectorAll('[data-col-index]').forEach((node) => {
            const index = Number(node.getAttribute('data-col-index'));
            if (!Number.isFinite(index)) {
                return;
            }
            node.classList.toggle('is-column-hidden', hiddenColumnIndexes.has(index));
        });

        syncTopScrollbarGeometry();
    }

    function normalizeCellText(value) {
        const raw = value == null ? '' : String(value);
        const compact = raw.replace(/\s+/g, ' ').trim();
        if (compact.length <= CELL_TRUNCATE_LIMIT) {
            return { displayValue: compact, fullValue: compact, isTruncated: false };
        }

        return {
            displayValue: `${compact.slice(0, CELL_TRUNCATE_LIMIT)}...`,
            fullValue: compact,
            isTruncated: true,
        };
    }

    function renderTableRows(columns, rows) {
        if (!tableBody) {
            return;
        }

        const safeColumns = Array.isArray(columns) ? columns : [];
        const safeRows = Array.isArray(rows) ? rows : [];
        const useStackMobile = safeColumns.length <= 5;

        if (!safeRows.length) {
            tableBody.innerHTML = `<tr class="table-empty-row"><td colspan="${Math.max(safeColumns.length, 1)}">В выбранной таблице нет строк для показа.</td></tr>`;
            return;
        }

        tableBody.innerHTML = safeRows.map((row) => {
            const safeCells = Array.isArray(row) ? row : [];
            const cellsHtml = safeCells.map((value, index) => {
                const label = useStackMobile ? ` data-label="${escapeHtml(safeColumns[index] ?? '')}"` : '';
                const normalized = normalizeCellText(value);
                const title = normalized.isTruncated ? ` title="${escapeHtml(normalized.fullValue)}"` : '';
                return `<td data-col-index="${index}"${label}${title}>${escapeHtml(normalized.displayValue)}</td>`;
            }).join('');
            return `<tr>${cellsHtml}</tr>`;
        }).join('');

        applyColumnVisibility();
    }

    function normalizeExistingRows() {
        if (!tableBody) {
            return;
        }

        const headerColumns = Array.from(tableHead?.querySelectorAll('th') || []).map((cell) => String(cell.textContent ?? '').trim());
        if (headerColumns.length) {
            syncColumnsState(headerColumns);
            renderColumnsList();
            tableHead?.querySelectorAll('th').forEach((cell, index) => {
                cell.setAttribute('data-col-index', String(index));
            });
        }

        tableBody.querySelectorAll('tr').forEach((row) => {
            if (row.classList.contains('table-empty-row')) {
                return;
            }
            const cells = row.querySelectorAll('td');
            cells.forEach((cell, index) => {
                cell.setAttribute('data-col-index', String(index));
                const normalized = normalizeCellText(cell.textContent ?? '');
                cell.textContent = normalized.displayValue;
                if (normalized.isTruncated) {
                    cell.title = normalized.fullValue;
                } else {
                    cell.removeAttribute('title');
                }
            });
        });

        applyColumnVisibility();
        syncTopScrollbarGeometry();
    }

    function syncTopScrollbarGeometry() {
        if (!tableTopScrollInner || !tableDataShell || !tableElement) {
            return;
        }

        const shellScrollWidth = tableDataShell.scrollWidth || 0;
        const tableScrollWidth = tableElement.scrollWidth || 0;
        const visibleWidth = tableDataShell.clientWidth || 0;
        const fullWidth = Math.max(shellScrollWidth, tableScrollWidth);
        const hasHorizontalOverflow = fullWidth - visibleWidth > 1;
        const topInnerWidth = hasHorizontalOverflow ? fullWidth : visibleWidth;
        tableTopScrollInner.style.width = `${Math.max(topInnerWidth, 0)}px`;
        tableTopScroll.scrollLeft = tableDataShell.scrollLeft;
    }

    function renderStatCards(container, items) {
        if (!container) {
            return;
        }

        const safeItems = Array.isArray(items) ? items : [];
        container.innerHTML = safeItems.map((item) => `
            <article class="stat-card">
                <span class="stat-label">${escapeHtml(item?.label ?? '')}</span>
                <strong class="stat-value">${escapeHtml(item?.value ?? '')}</strong>
                <span class="stat-foot">${escapeHtml(item?.meta ?? '')}</span>
            </article>
        `).join('');
    }

    function updateSummary(summary) {
        const safeSummary = summary && typeof summary === 'object' ? summary : {};

        if (summaryLead) {
            summaryLead.textContent = safeSummary.lead || '';
        }
        if (summaryScopeNote) {
            summaryScopeNote.textContent = safeSummary.scope_note || '';
        }
        if (criteriaLead) {
            criteriaLead.textContent = safeSummary.criteria_lead || '';
        }

        renderStatCards(summaryCards, safeSummary.cards || []);
        renderStatCards(criteriaGroups, safeSummary.groups || []);
    }

    function updatePagination(pagination) {
        if (!pagination || typeof pagination !== 'object') {
            return;
        }

        const displayedRows = Number(pagination.displayed_rows ?? 0);
        const totalRows = Number(pagination.total_rows ?? 0);
        const page = Number(pagination.page ?? 1);
        const totalPages = Number(pagination.total_pages ?? 1);
        const pageSize = Number(pagination.page_size ?? 100);
        const rangeText = displayedRows ? `${pagination.page_row_start}-${pagination.page_row_end}` : '0';

        if (pageInput) {
            pageInput.value = String(page);
            pageInput.max = String(Math.max(totalPages, 1));
        }
        if (pageSizeSelect) {
            pageSizeSelect.value = String(pageSize);
        }
        if (pageCount) {
            pageCount.textContent = `${page} / ${totalPages}`;
        }
        if (pageStatus) {
            pageStatus.textContent = displayedRows
                ? `Показаны строки ${pagination.page_row_start}-${pagination.page_row_end} из ${formatInteger(totalRows)}`
                : 'В таблице пока нет строк';
        }
        if (pageSizeValue) {
            pageSizeValue.textContent = String(pageSize);
        }
        if (sidebarTotalRows) {
            sidebarTotalRows.textContent = formatInteger(totalRows);
        }
        if (sidebarPageNumber) {
            sidebarPageNumber.textContent = `${page} / ${totalPages}`;
        }
        if (sidebarShownRows) {
            sidebarShownRows.textContent = rangeText;
        }
        if (heroTotalRows) {
            heroTotalRows.textContent = formatInteger(totalRows);
        }
        if (heroRange) {
            heroRange.textContent = rangeText;
        }
        if (heroPage) {
            heroPage.textContent = `${page} / ${totalPages}`;
        }

        setLinkState(prevLink, Boolean(pagination.has_previous), Math.max(page - 1, 1), pageSize);
        setLinkState(nextLink, Boolean(pagination.has_next), Math.min(page + 1, totalPages), pageSize);
    }

    function setLoadingState(loading) {
        isLoading = loading;

        if (form) {
            form.classList.toggle('is-loading', loading);
        }
        if (pageInput) {
            pageInput.disabled = loading;
        }
        if (pageSizeSelect) {
            pageSizeSelect.disabled = loading;
        }
    }

    function hideInlineError() {
        if (inlineError) {
            inlineError.classList.add('is-hidden');
        }
        if (inlineErrorMessage) {
            inlineErrorMessage.textContent = '';
        }
    }

    function showInlineError(message) {
        if (inlineErrorMessage) {
            inlineErrorMessage.textContent = message || 'Не удалось загрузить страницу таблицы.';
        }
        if (inlineError) {
            inlineError.classList.remove('is-hidden');
        }
    }

    async function loadPage(targetPage, targetPageSize, options = {}) {
        if (isLoading) {
            return;
        }

        const updateHistory = options.updateHistory !== false;
        setLoadingState(true);
        hideInlineError();

        try {
            const result = await fetchJson(buildApiUrl(targetPage, targetPageSize), {
                headers: {
                    'Accept': 'application/json',
                },
            }, 'Не удалось загрузить страницу таблицы.');
            const payload = result.payload;

            if (!payload?.ok) {
                throw new Error(payload?.message || 'Не удалось загрузить страницу таблицы.');
            }

            renderTableHead(payload.columns || []);
            renderTableRows(payload.columns || [], payload.rows || []);
            updatePagination(payload.pagination || {});
            updateSummary(payload.table_summary || {});

            if (updateHistory) {
                const safePagination = payload.pagination || {};
                const nextUrl = buildPageUrl(safePagination.page || targetPage, safePagination.page_size || targetPageSize);
                window.history.pushState(
                    {
                        page: safePagination.page || targetPage,
                        pageSize: safePagination.page_size || targetPageSize,
                    },
                    '',
                    nextUrl,
                );
            }
        } catch (error) {
            showInlineError(error instanceof Error ? error.message : 'Не удалось загрузить страницу таблицы.');
        } finally {
            setLoadingState(false);
        }
    }

    form = replaceElementForFreshListeners(form);
    form?.addEventListener('submit', (event) => {
        event.preventDefault();
        const targetPage = Math.max(Number(pageInput?.value || 1), 1);
        const targetPageSize = Number(pageSizeSelect?.value || 100);
        loadPage(targetPage, targetPageSize);
    });

    pageSizeSelect = replaceElementForFreshListeners(pageSizeSelect);
    pageSizeSelect?.addEventListener('change', () => {
        if (pageInput) {
            pageInput.value = '1';
        }
        if (form?.requestSubmit) {
            form.requestSubmit();
        } else {
            form?.dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }));
        }
    });

    prevLink = replaceElementForFreshListeners(prevLink);
    nextLink = replaceElementForFreshListeners(nextLink);
    [prevLink, nextLink].forEach((link) => {
        link?.addEventListener('click', (event) => {
            if (link.classList.contains('is-disabled')) {
                event.preventDefault();
                return;
            }

            event.preventDefault();
            const targetPage = Math.max(Number(link.dataset.pageTarget || pageInput?.value || 1), 1);
            const targetPageSize = Number(pageSizeSelect?.value || 100);
            loadPage(targetPage, targetPageSize);
        });
    });

    function handlePopState() {
        const params = new URLSearchParams(window.location.search);
        const targetPage = Math.max(Number(params.get('page') || 1), 1);
        const targetPageSize = Number(params.get('page_size') || pageSizeSelect?.value || 100);
        loadPage(targetPage, targetPageSize, { updateHistory: false });
    }
    const previousPopstateHandler = window[POPSTATE_HANDLER_KEY];
    if (typeof previousPopstateHandler === 'function') {
        window.removeEventListener('popstate', previousPopstateHandler);
    }
    window[POPSTATE_HANDLER_KEY] = handlePopState;
    window.addEventListener('popstate', handlePopState);

    inlineRetryButton = replaceElementForFreshListeners(inlineRetryButton);
    inlineRetryButton?.addEventListener('click', () => {
        const targetPage = Math.max(Number(pageInput?.value || 1), 1);
        const targetPageSize = Number(pageSizeSelect?.value || 100);
        loadPage(targetPage, targetPageSize);
    });

    tableTopScroll?.addEventListener('scroll', () => {
        if (!tableDataShell || syncingBottomScroll) {
            return;
        }
        syncingTopScroll = true;
        tableDataShell.scrollLeft = tableTopScroll.scrollLeft;
        syncingTopScroll = false;
    });

    tableDataShell?.addEventListener('scroll', () => {
        if (!tableTopScroll || syncingTopScroll) {
            return;
        }
        syncingBottomScroll = true;
        tableTopScroll.scrollLeft = tableDataShell.scrollLeft;
        syncingBottomScroll = false;
    });

    tableColumnsList?.addEventListener('click', (event) => {
        const target = event.target instanceof Element ? event.target.closest('[data-column-index]') : null;
        if (!target) {
            return;
        }

        const columnIndex = Number(target.getAttribute('data-column-index'));
        if (!Number.isFinite(columnIndex) || columnIndex < 0 || columnIndex >= currentColumns.length) {
            return;
        }

        if (hiddenColumnIndexes.has(columnIndex)) {
            hiddenColumnIndexes.delete(columnIndex);
        } else {
            hiddenColumnIndexes.add(columnIndex);
        }

        renderColumnsList();
        applyColumnVisibility();
    });

    tableColumnsSelectAllButton?.addEventListener('click', () => {
        hiddenColumnIndexes.clear();
        renderColumnsList();
        applyColumnVisibility();
    });

    tableColumnsClearButton?.addEventListener('click', () => {
        hiddenColumnIndexes = new Set(currentColumns.map((_column, index) => index));
        renderColumnsList();
        applyColumnVisibility();
    });

    window.addEventListener('resize', () => {
        syncTopScrollbarGeometry();
        window.requestAnimationFrame(syncTopScrollbarGeometry);
    });
    if (typeof ResizeObserver === 'function' && tableDataShell && tableElement) {
        const geometryObserver = new ResizeObserver(() => {
            syncTopScrollbarGeometry();
            window.requestAnimationFrame(syncTopScrollbarGeometry);
        });
        geometryObserver.observe(tableDataShell);
        geometryObserver.observe(tableElement);
    }
    window.addEventListener('load', () => {
        syncTopScrollbarGeometry();
        window.requestAnimationFrame(syncTopScrollbarGeometry);
    });
    normalizeExistingRows();
    syncTopScrollbarGeometry();
    window.requestAnimationFrame(syncTopScrollbarGeometry);
})();
