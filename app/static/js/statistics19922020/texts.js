(function (global) {
    "use strict";

    global.Statistics19922020Texts = {
        status: {
            successPrefix: "Операция выполнена:",
            errorPrefix: "Операция не выполнена:",
            logsHint: "Подробности в блоке «Логи выполнения».",
            readyToRun: "Операция готова к запуску: файл выбран.",
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
}(window));
