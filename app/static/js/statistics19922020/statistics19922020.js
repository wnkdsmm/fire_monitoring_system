(function (global) {
    "use strict";

    var LOG_REFRESH_INTERVAL_MS = 2000;
    var JOB_STORAGE_KEY = "fire-monitor-statistics19922020-job-id";
    var shared = global.FireUi || {};
    var fetchJson = typeof shared.fetchJson === "function" ? shared.fetchJson : fallbackFetchJson;
    var getApiErrorMessage = typeof shared.getApiErrorMessage === "function"
        ? shared.getApiErrorMessage
        : function (_, fallback) { return fallback || "Ошибка запроса"; };
    var createJobId = typeof shared.createJobId === "function"
        ? shared.createJobId
        : function () { return String(Date.now()); };
    var logsRefreshTimer = typeof shared.createSingleTimer === "function"
        ? shared.createSingleTimer()
        : createLocalSingleTimer();

    var currentJobId = null;
    var logsPollingStarted = false;

    function createLocalSingleTimer() {
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

    async function fallbackFetchJson(url, init, fallback) {
        var response = await fetch(url, init || {});
        var payload = {};
        try {
            payload = await response.json();
        } catch (_) {
            payload = {};
        }
        if (!response.ok) {
            var message = (payload && payload.message) || fallback || "Ошибка запроса";
            var error = new Error(message);
            error.payload = payload;
            throw error;
        }
        return { payload: payload };
    }

    function byId(id) {
        return document.getElementById(id);
    }

    function createLogLine(text) {
        var line = document.createElement("div");
        line.textContent = text;
        return line;
    }

    function replaceLogLines(items) {
        var logBox = byId("statistics19922020Logs");
        if (!logBox) {
            return;
        }
        var nodes = (Array.isArray(items) ? items : []).map(function (item) {
            return createLogLine(String(item == null ? "" : item));
        });
        logBox.replaceChildren.apply(logBox, nodes);
    }

    function appendLogLine(text) {
        var logBox = byId("statistics19922020Logs");
        if (!logBox) {
            return;
        }
        logBox.appendChild(createLogLine(text));
        logBox.scrollTop = logBox.scrollHeight;
    }

    function setStatus(text, tone) {
        var statusNode = byId("statistics19922020Status");
        if (!statusNode) {
            return;
        }
        statusNode.hidden = false;
        statusNode.dataset.tone = tone || "info";
        statusNode.textContent = String(text || "");
    }

    function clearStatus() {
        var statusNode = byId("statistics19922020Status");
        if (!statusNode) {
            return;
        }
        statusNode.hidden = true;
        statusNode.dataset.tone = "info";
        statusNode.textContent = "";
    }

    function setSelectedFileLabel(fileName) {
        var label = byId("statistics19922020SelectedFile");
        if (label) {
            label.textContent = fileName || "Файл не выбран";
        }
    }

    function setCurrentJobId(jobId) {
        currentJobId = jobId || null;
        if (!global.sessionStorage) {
            return;
        }
        if (currentJobId) {
            global.sessionStorage.setItem(JOB_STORAGE_KEY, currentJobId);
        } else {
            global.sessionStorage.removeItem(JOB_STORAGE_KEY);
        }
    }

    function getCurrentJobId() {
        if (currentJobId) {
            return currentJobId;
        }
        if (!global.sessionStorage) {
            return null;
        }
        var stored = global.sessionStorage.getItem(JOB_STORAGE_KEY);
        if (stored) {
            currentJobId = stored;
            return stored;
        }
        return null;
    }

    function getSelectedFile() {
        var input = byId("statistics19922020FileInput");
        return input && input.files ? input.files[0] : null;
    }

    function setActionButtonsDisabled(isDisabled) {
        var buttons = document.querySelectorAll("[data-stat-action]");
        Array.prototype.forEach.call(buttons, function (button) {
            button.disabled = !!isDisabled;
        });
    }

    async function refreshLogs(jobId) {
        var resolvedJobId = jobId || getCurrentJobId();
        if (!resolvedJobId) {
            return;
        }
        try {
            var result = await fetchJson(
                "/logs?job_id=" + encodeURIComponent(resolvedJobId),
                { headers: { "Accept": "application/json" } },
                "Не удалось обновить логи."
            );
            var payload = result.payload || {};
            var logs = Array.isArray(payload.logs) ? payload.logs : [];
            replaceLogLines(logs);
            var logBox = byId("statistics19922020Logs");
            if (logBox) {
                logBox.scrollTop = logBox.scrollHeight;
            }
        } catch (error) {
            console.error("Failed to refresh statistics logs", error);
        }
    }

    function startLogsPolling() {
        if (logsPollingStarted) {
            return;
        }
        logsPollingStarted = true;

        var pollLogs = async function () {
            await refreshLogs();
            logsRefreshTimer.clear();
            logsRefreshTimer.set(pollLogs, LOG_REFRESH_INTERVAL_MS);
        };
        logsRefreshTimer.clear();
        logsRefreshTimer.set(pollLogs, LOG_REFRESH_INTERVAL_MS);
    }

    async function uploadSelectedFile() {
        var fileInput = byId("statistics19922020FileInput");
        var selectedFile = getSelectedFile();
        if (!selectedFile) {
            throw new Error("Сначала выберите XLSX файл.");
        }

        var nextJobId = createJobId();
        setCurrentJobId(nextJobId);
        replaceLogLines(["Загрузка файла " + selectedFile.name + "..."]);

        var uploadData = new FormData();
        uploadData.append("file", selectedFile);
        uploadData.append("job_id", nextJobId);

        var uploadResult = await fetchJson(
            "/upload",
            { method: "POST", body: uploadData },
            "Ошибка при загрузке файла."
        );
        var payload = uploadResult.payload || {};
        var resolvedJobId = payload.job_id || nextJobId;
        setCurrentJobId(resolvedJobId);
        if (payload.status !== "uploaded") {
            throw new Error(String(payload.message || "Файл не загружен."));
        }

        if (fileInput) {
            fileInput.value = "";
        }
        setSelectedFileLabel(payload.filename || selectedFile.name);
        appendLogLine("Файл загружен.");
        await refreshLogs(resolvedJobId);
        return resolvedJobId;
    }

    async function ensureUploadedFile() {
        if (getSelectedFile()) {
            return uploadSelectedFile();
        }
        var jobId = getCurrentJobId();
        if (jobId) {
            return jobId;
        }
        throw new Error("Сначала выберите XLSX файл.");
    }

    async function maybeUploadSelectedFile() {
        if (getSelectedFile()) {
            return uploadSelectedFile();
        }
        return getCurrentJobId();
    }

    function isErrorStatus(payload) {
        if (!payload || typeof payload !== "object") {
            return false;
        }
        var status = String(payload.status || "").trim().toLowerCase();
        return status === "error" || status === "failed";
    }

    async function runAction(options) {
        var settings = options || {};
        var endpoint = String(settings.endpoint || "");
        if (!endpoint) {
            return;
        }

        setActionButtonsDisabled(true);
        clearStatus();

        try {
            var jobId = null;
            if (settings.uploadMode === "required") {
                jobId = await ensureUploadedFile();
            } else if (settings.uploadMode === "if-selected") {
                jobId = await maybeUploadSelectedFile();
            } else {
                jobId = getCurrentJobId();
            }

            var formData = new FormData();
            if (jobId) {
                formData.append("job_id", jobId);
            }
            if (settings.outputDir) {
                formData.append("output_dir", settings.outputDir);
            }
            if (settings.outputFolder) {
                formData.append("output_folder", settings.outputFolder);
            }
            if (settings.baseDir) {
                formData.append("base_dir", settings.baseDir);
            }

            var response = await fetchJson(
                endpoint,
                { method: "POST", body: formData },
                settings.errorMessage || "Ошибка выполнения операции."
            );
            var payload = response.payload || {};
            var resolvedJobId = payload.job_id || jobId || null;
            if (resolvedJobId) {
                setCurrentJobId(resolvedJobId);
                await refreshLogs(resolvedJobId);
            }

            if (isErrorStatus(payload)) {
                setStatus(payload.message || settings.errorMessage || "Операция завершилась с ошибкой.", "error");
                return;
            }

            setStatus(settings.successMessage || String(payload.status || "Операция выполнена."), "success");
        } catch (error) {
            var fallback = settings.errorMessage || "Ошибка выполнения операции.";
            var message = getApiErrorMessage(error && error.payload, error && error.message ? error.message : fallback);
            appendLogLine(message);
            setStatus(message, "error");
        } finally {
            setActionButtonsDisabled(false);
        }
    }

    function bindUiEvents() {
        var fileInput = byId("statistics19922020FileInput");
        var pickFileButton = byId("statistics19922020PickFileButton");
        var decodeButton = byId("statistics19922020DecodeButton");
        var decodeImportButton = byId("statistics19922020DecodeImportButton");
        var renameHeadersButton = byId("statistics19922020RenameHeadersButton");
        var splitByYearButton = byId("statistics19922020SplitByYearButton");

        if (pickFileButton && fileInput) {
            pickFileButton.addEventListener("click", function () {
                fileInput.click();
            });
        }

        if (fileInput) {
            fileInput.addEventListener("change", function () {
                var selectedFile = getSelectedFile();
                if (!selectedFile) {
                    return;
                }
                setCurrentJobId(null);
                setSelectedFileLabel(selectedFile.name);
                replaceLogLines(["Файл выбран: " + selectedFile.name]);
                setStatus("Файл выбран. Запустите нужную операцию.", "info");
            });
        }

        if (decodeButton) {
            decodeButton.addEventListener("click", function () {
                runAction({
                    endpoint: "/statistics19922020/decode",
                    uploadMode: "required",
                    errorMessage: "Ошибка при расшифровке файла.",
                    successMessage: "Расшифровка завершена."
                });
            });
        }

        if (decodeImportButton) {
            decodeImportButton.addEventListener("click", function () {
                runAction({
                    endpoint: "/statistics19922020/decode_import",
                    uploadMode: "required",
                    errorMessage: "Ошибка при расшифровке и импорте.",
                    successMessage: "Расшифровка и импорт завершены."
                });
            });
        }

        if (renameHeadersButton) {
            renameHeadersButton.addEventListener("click", function () {
                runAction({
                    endpoint: "/statistics19922020/run_rename_headers",
                    uploadMode: "if-selected",
                    errorMessage: "Ошибка при выполнении rename_headers_2019_2023.py.",
                    successMessage: "Скрипт rename_headers_2019_2023.py завершен."
                });
            });
        }

        if (splitByYearButton) {
            splitByYearButton.addEventListener("click", function () {
                runAction({
                    endpoint: "/statistics19922020/run_split_xlsx_by_year",
                    uploadMode: "if-selected",
                    errorMessage: "Ошибка при выполнении split_xlsx_by_year.py.",
                    successMessage: "Скрипт split_xlsx_by_year.py завершен."
                });
            });
        }
    }

    function initializePage() {
        if (!byId("statistics19922020Logs")) {
            return;
        }
        setSelectedFileLabel("Файл не выбран");
        if (getCurrentJobId()) {
            refreshLogs();
        } else {
            replaceLogLines(["Логи появятся после запуска операции."]);
        }
        startLogsPolling();
        bindUiEvents();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initializePage, { once: true });
    } else {
        initializePage();
    }
}(window));
