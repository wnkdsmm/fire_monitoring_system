(function (global) {
    "use strict";

    var LOG_REFRESH_INTERVAL_MS = 2000;
    var JOB_STORAGE_KEY = "fire-monitor-statistics19922020-job-id";
    var shared = global.FireUi || {};
    var fetchJson = typeof shared.fetchJson === "function" ? shared.fetchJson : fallbackFetchJson;
    var getApiErrorMessage = typeof shared.getApiErrorMessage === "function"
        ? shared.getApiErrorMessage
        : function (_, fallback) { return fallback || "Request failed."; };
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
            var message = (payload && payload.message) || fallback || "Request failed.";
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
            label.textContent = fileName || "No source file selected";
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
                "Could not refresh execution logs."
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
            throw new Error("Select a source .xlsx file first.");
        }

        var nextJobId = createJobId();
        setCurrentJobId(nextJobId);
        replaceLogLines(["Uploading source file " + selectedFile.name + "..."]);

        var uploadData = new FormData();
        uploadData.append("file", selectedFile);
        uploadData.append("job_id", nextJobId);

        var uploadResult = await fetchJson(
            "/upload",
            { method: "POST", body: uploadData },
            "Could not upload the source file."
        );
        var payload = uploadResult.payload || {};
        var resolvedJobId = payload.job_id || nextJobId;
        setCurrentJobId(resolvedJobId);
        if (payload.status !== "uploaded") {
            throw new Error(String(payload.message || "Source file was not uploaded."));
        }

        if (fileInput) {
            fileInput.value = "";
        }
        setSelectedFileLabel(payload.filename || selectedFile.name);
        appendLogLine("Source file uploaded.");
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
        throw new Error("Select a source .xlsx file first.");
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

    function buildSuccessMessage(settings, payload) {
        var endpoint = String(settings.endpoint || "");
        var files = payload && payload.files ? payload.files : {};
        var logsHint = "Details are available in the Execution logs panel.";

        if (endpoint === "/statistics19922020/decode") {
            var decoded = files.decoded_file ? (" Decoded file: " + files.decoded_file + ".") : "";
            var report = files.report_file ? (" Report: " + files.report_file + ".") : "";
            return "Decoding completed." + decoded + report + " " + logsHint;
        }

        if (endpoint === "/statistics19922020/decode-and-import" || endpoint === "/statistics19922020/decode_import") {
            var importData = payload && payload.import ? payload.import : {};
            var outputFolder = importData.output_folder ? (" Output folder: " + importData.output_folder + ".") : "";
            return "Decoding and PostgreSQL load completed." + outputFolder + " " + logsHint;
        }

        if (endpoint === "/statistics19922020/run_rename_headers") {
            return "Header preparation completed. " + logsHint;
        }

        if (endpoint === "/statistics19922020/run_split_xlsx_by_year") {
            var exported = payload && payload.exported_files && payload.exported_files.length
                ? (" Created files: " + payload.exported_files.length + ".")
                : "";
            var targetDir = payload && payload.output_dir ? (" Output folder: " + payload.output_dir + ".") : "";
            return "Year split completed." + exported + targetDir + " " + logsHint;
        }

        return String(payload && payload.message ? payload.message : "Operation completed.") + " " + logsHint;
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
                settings.errorMessage || "Operation failed."
            );
            var payload = response.payload || {};
            var resolvedJobId = payload.job_id || jobId || null;
            if (resolvedJobId) {
                setCurrentJobId(resolvedJobId);
                await refreshLogs(resolvedJobId);
            }

            if (isErrorStatus(payload)) {
                setStatus((payload.message || settings.errorMessage || "Operation failed.") + " Check the Execution logs panel.", "error");
                return;
            }

            setStatus(buildSuccessMessage(settings, payload), "success");
        } catch (error) {
            var fallback = settings.errorMessage || "Operation failed.";
            var message = getApiErrorMessage(error && error.payload, error && error.message ? error.message : fallback);
            appendLogLine(message);
            setStatus(message + " Check the Execution logs panel.", "error");
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
                replaceLogLines(["Source file selected: " + selectedFile.name]);
                setStatus("Source file selected. Choose the required operation. Execution details will appear in logs.", "info");
            });
        }

        if (decodeButton) {
            decodeButton.addEventListener("click", function () {
                runAction({
                    endpoint: "/statistics19922020/decode",
                    uploadMode: "required",
                    errorMessage: "Could not decode the selected file."
                });
            });
        }

        if (decodeImportButton) {
            decodeImportButton.addEventListener("click", function () {
                runAction({
                    endpoint: "/statistics19922020/decode-and-import",
                    uploadMode: "required",
                    errorMessage: "Could not decode and load data into PostgreSQL."
                });
            });
        }

        if (renameHeadersButton) {
            renameHeadersButton.addEventListener("click", function () {
                runAction({
                    endpoint: "/statistics19922020/run_rename_headers",
                    uploadMode: "if-selected",
                    errorMessage: "Could not complete header preparation."
                });
            });
        }

        if (splitByYearButton) {
            splitByYearButton.addEventListener("click", function () {
                runAction({
                    endpoint: "/statistics19922020/run_split_xlsx_by_year",
                    uploadMode: "if-selected",
                    errorMessage: "Could not split the file by year."
                });
            });
        }
    }

    function initializePage() {
        if (!byId("statistics19922020Logs")) {
            return;
        }
        setSelectedFileLabel("No source file selected");
        if (getCurrentJobId()) {
            refreshLogs();
        } else {
            replaceLogLines(["Execution logs will appear after you start an operation."]);
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
