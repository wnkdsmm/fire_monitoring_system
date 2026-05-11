(function (global) {
    "use strict";

    var DATA_NODE_ID = "statistics19922020TextsData";
    var FALLBACK_TEXTS = {
        status: {},
        errors: {},
        logs: {},
        success: {},
        details: {}
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
