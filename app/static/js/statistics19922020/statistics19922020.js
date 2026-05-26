(function (global) {
    "use strict";

    var LOG_REFRESH_INTERVAL_MS = 2000;
    var JOB_STORAGE_KEY = "fire-monitor-statistics19922020-job-id";
    var TEXTS = global.Statistics19922020Texts || {};
    var STATUS_TEXTS = TEXTS.status || {};
    var ERROR_TEXTS = TEXTS.errors || {};
    var LOG_TEXTS = TEXTS.logs || {};
    var SUCCESS_TEXTS = TEXTS.success || {};
    var DETAIL_TEXTS = TEXTS.details || {};
    var STATUS_SUCCESS_PREFIX = STATUS_TEXTS.successPrefix || "Операция выполнена:";
    var STATUS_ERROR_PREFIX = STATUS_TEXTS.errorPrefix || "Операция не выполнена:";
    var STATUS_LOGS_HINT = STATUS_TEXTS.logsHint || "Подробности в блоке «Журнал выполнения».";
    var shared = global.FireUi || {};
    var fetchJson = typeof shared.fetchJson === "function" ? shared.fetchJson : fallbackFetchJson;
    var getApiErrorMessage = typeof shared.getApiErrorMessage === "function"
        ? shared.getApiErrorMessage
        : function (_, fallback) { return fallback || ERROR_TEXTS.requestFailed || "Не удалось выполнить запрос."; };
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
            var message = (payload && payload.message) || fallback || ERROR_TEXTS.requestFailed || "Не удалось выполнить запрос.";
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
            label.textContent = fileName || STATUS_TEXTS.noFileSelected || "Исходный файл не выбран";
        }
    }

    function setBusyState(isBusy) {
        var busyValue = isBusy ? "true" : "false";
        var statusNode = byId("statistics19922020Status");
        var logsNode = byId("statistics19922020Logs");
        if (statusNode) {
            statusNode.setAttribute("aria-busy", busyValue);
        }
        if (logsNode) {
            logsNode.setAttribute("aria-busy", busyValue);
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
                ERROR_TEXTS.refreshLogsFailed || "Не удалось обновить журнал выполнения."
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
            throw new Error(ERROR_TEXTS.chooseSourceFileFirst || "Сначала выберите исходный файл .xlsx.");
        }

        var nextJobId = createJobId();
        setCurrentJobId(nextJobId);
        replaceLogLines([(LOG_TEXTS.uploadingSourcePrefix || "Загрузка исходного файла ") + selectedFile.name + "..."]);

        var uploadData = new FormData();
        uploadData.append("file", selectedFile);
        uploadData.append("job_id", nextJobId);

        var uploadResult = await fetchJson(
            "/upload",
            { method: "POST", body: uploadData },
            ERROR_TEXTS.uploadSourceFailed || "Не удалось загрузить исходный файл."
        );
        var payload = uploadResult.payload || {};
        var resolvedJobId = payload.job_id || nextJobId;
        setCurrentJobId(resolvedJobId);
        if (payload.status !== "uploaded") {
            throw new Error(String(payload.message || ERROR_TEXTS.sourceNotUploaded || "Исходный файл не был загружен."));
        }

        if (fileInput) {
            fileInput.value = "";
        }
        setSelectedFileLabel(payload.filename || selectedFile.name);
        appendLogLine(LOG_TEXTS.sourceUploaded || "Исходный файл загружен.");
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
        throw new Error(ERROR_TEXTS.chooseSourceFileFirst || "Сначала выберите исходный файл .xlsx.");
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

    function joinMessageParts(parts) {
        return parts.filter(Boolean).join(" ");
    }

    function buildCompletedMessage(mainText, details) {
        return joinMessageParts([STATUS_SUCCESS_PREFIX, mainText, details, STATUS_LOGS_HINT]);
    }

    function buildFailureMessage(message) {
        return joinMessageParts([STATUS_ERROR_PREFIX, message || ERROR_TEXTS.operationFailed || "Не удалось выполнить операцию.", STATUS_LOGS_HINT]);
    }

    function buildSuccessMessage(settings, payload) {
        var endpoint = String(settings.endpoint || "");
        var files = payload && payload.files ? payload.files : {};

        if (endpoint === "/statistics19922020/decode") {
            var decoded = files.decoded_file ? ((DETAIL_TEXTS.decodedFilePrefix || "Расшифрованный файл: ") + files.decoded_file + ".") : "";
            var report = files.report_file ? ((DETAIL_TEXTS.reportFilePrefix || "Отчет: ") + files.report_file + ".") : "";
            return buildCompletedMessage(SUCCESS_TEXTS.decoded || "данные расшифрованы.", joinMessageParts([decoded, report]));
        }

        if (endpoint === "/statistics19922020/decode-and-import" || endpoint === "/statistics19922020/decode_import" || endpoint === "/statistics19922020/decode-stat-and-import") {
            var importData = payload && payload.import ? payload.import : {};
            var outputFolder = importData.output_folder ? ((DETAIL_TEXTS.outputFolderPrefix || "Папка результата: ") + importData.output_folder + ".") : "";
            return buildCompletedMessage(SUCCESS_TEXTS.decodedAndImported || "данные расшифрованы и загружены в PostgreSQL.", outputFolder);
        }

        if (endpoint === "/statistics19922020/run_rename_headers") {
            return buildCompletedMessage(SUCCESS_TEXTS.headersPrepared || "заголовки подготовлены.");
        }

        if (endpoint === "/statistics19922020/run_split_xlsx_by_year") {
            var exported = payload && payload.exported_files && payload.exported_files.length
                ? ((DETAIL_TEXTS.exportedFilesPrefix || "Создано файлов: ") + payload.exported_files.length + ".")
                : "";
            var targetDir = payload && payload.output_dir ? ((DETAIL_TEXTS.outputFolderPrefix || "Папка результата: ") + payload.output_dir + ".") : "";
            return buildCompletedMessage(SUCCESS_TEXTS.splitByYear || "файл разбит по годам.", joinMessageParts([exported, targetDir]));
        }

        return joinMessageParts([String(payload && payload.message ? payload.message : STATUS_TEXTS.defaultDone || "Операция завершена."), STATUS_LOGS_HINT]);
    }

    async function runAction(options) {
        var settings = options || {};
        var endpoint = String(settings.endpoint || "");
        if (!endpoint) {
            return;
        }

        setActionButtonsDisabled(true);
        setBusyState(true);
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
                settings.errorMessage || ERROR_TEXTS.operationFailed || "Не удалось выполнить операцию."
            );
            var payload = response.payload || {};
            var resolvedJobId = payload.job_id || jobId || null;
            if (resolvedJobId) {
                setCurrentJobId(resolvedJobId);
                await refreshLogs(resolvedJobId);
            }

            if (isErrorStatus(payload)) {
                setStatus(buildFailureMessage(payload.message || settings.errorMessage), "error");
                return;
            }

            setStatus(buildSuccessMessage(settings, payload), "success");
        } catch (error) {
            var fallback = settings.errorMessage || ERROR_TEXTS.operationFailed || "Не удалось выполнить операцию.";
            var message = getApiErrorMessage(error && error.payload, error && error.message ? error.message : fallback);
            appendLogLine(message);
            setStatus(buildFailureMessage(message), "error");
        } finally {
            setActionButtonsDisabled(false);
            setBusyState(false);
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
                replaceLogLines([(LOG_TEXTS.sourceSelectedPrefix || "Выбран исходный файл: ") + selectedFile.name]);
                setStatus(joinMessageParts([STATUS_TEXTS.readyToRun || "Файл выбран. Можно запускать операцию.", STATUS_LOGS_HINT]), "info");
            });
        }

        if (decodeButton) {
            decodeButton.addEventListener("click", function () {
                runAction({
                    endpoint: "/statistics19922020/decode-and-import",
                    uploadMode: "required",
                    errorMessage: ERROR_TEXTS.decodeFailed || "Не удалось выполнить декодирование выбранного файла."
                });
            });
        }

        if (decodeImportButton) {
            decodeImportButton.addEventListener("click", function () {
                runAction({
                    endpoint: "/statistics19922020/decode-stat-and-import",
                    uploadMode: "required",
                    errorMessage: ERROR_TEXTS.decodeImportFailed || "Не удалось выполнить расшифровку и загрузку в PostgreSQL."
                });
            });
        }

        if (renameHeadersButton) {
            renameHeadersButton.addEventListener("click", function () {
                runAction({
                    endpoint: "/statistics19922020/run_rename_headers",
                    uploadMode: "if-selected",
                    errorMessage: ERROR_TEXTS.renameHeadersFailed || "Не удалось выполнить подготовку заголовков."
                });
            });
        }

        if (splitByYearButton) {
            splitByYearButton.addEventListener("click", function () {
                runAction({
                    endpoint: "/statistics19922020/run_split_xlsx_by_year",
                    uploadMode: "if-selected",
                    errorMessage: ERROR_TEXTS.splitByYearFailed || "Не удалось разбить файл по годам."
                });
            });
        }
    }

    function initializePage() {
        if (!byId("statistics19922020Logs")) {
            return;
        }
        setSelectedFileLabel(STATUS_TEXTS.noFileSelected || "Исходный файл не выбран");
        if (getCurrentJobId()) {
            refreshLogs();
        } else {
            replaceLogLines([STATUS_TEXTS.logsInitial || "Журнал выполнения появится после запуска операции."]);
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

