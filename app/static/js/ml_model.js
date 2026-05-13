(function (global) {
    // Keep this entry file touched when dependent ML modules change,
    // because the template cache key is derived from ml_model.js mtime.
    // Cache-bust stamp: Poisson compare-series reliability fallback + 4th line refresh (2026-05-13b).
    function boot() {
        if (!global.MlModelRender || typeof global.MlModelRender.init !== 'function') {
            return;
        }
        global.MlModelRender.init();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', boot);
        return;
    }
    boot();
}(window));
