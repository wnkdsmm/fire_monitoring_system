(function (global) {
    "use strict";

    var DATA_NODE_ID = "statistics19922020TextsData";
    var FALLBACK_TEXTS = {
        status: {
            successPrefix: "Операция выполнена:",
            errorPrefix: "Операция не выполнена:",
            logsHint: "Подробности в блоке «Журнал выполнения».",
            readyToRun: "Файл выбран. Можно запускать операцию.",
            defaultDone: "Операция завершена.",
            noFileSelected: "Исходный файл не выбран",
            logsInitial: "Журнал выполнения появится после запуска операции."
        },
        errors: {
            requestFailed: "Не удалось выполнить запрос.",
            refreshLogsFailed: "Не удалось обновить журнал выполнения.",
            chooseSourceFileFirst: "Сначала выберите исходный файл .xlsx.",
            uploadSourceFailed: "Не удалось загрузить исходный файл.",
            sourceNotUploaded: "Исходный файл не был загружен.",
            operationFailed: "Не удалось выполнить операцию.",
            decodeFailed: "Не удалось расшифровать выбранный файл.",
            decodeImportFailed: "Не удалось выполнить расшифровку и загрузку в PostgreSQL.",
            renameHeadersFailed: "Не удалось выполнить подготовку заголовков.",
            splitByYearFailed: "Не удалось разбить файл по годам."
        },
        logs: {
            uploadingSourcePrefix: "Загрузка исходного файла ",
            sourceUploaded: "Исходный файл загружен.",
            sourceSelectedPrefix: "Выбран исходный файл: "
        },
        success: {
            decoded: "данные расшифрованы.",
            decodedAndImported: "данные расшифрованы и загружены в PostgreSQL.",
            headersPrepared: "заголовки подготовлены.",
            splitByYear: "файл разбит по годам."
        },
        details: {
            decodedFilePrefix: "Расшифрованный файл: ",
            reportFilePrefix: "Отчет: ",
            outputFolderPrefix: "Папка результата: ",
            exportedFilesPrefix: "Создано файлов: "
        }
    };

    function getTextsFromDom() {
        var node = global.document && global.document.getElementById
            ? global.document.getElementById(DATA_NODE_ID)
            : null;
        if (!node || !node.textContent) {
            return null;
        }
        try {
            return JSON.parse(node.textContent);
        } catch (_) {
            return null;
        }
    }

    global.Statistics19922020Texts = getTextsFromDom() || FALLBACK_TEXTS;
}(window));
