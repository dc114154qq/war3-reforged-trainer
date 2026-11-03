/* Classic ES5 script: remains usable when the application module cannot be parsed. */
(function () {
  var painted = false;
  var failed = false;
  var pending = [];
  var failureMessage = '';

  function flush() {
    var api = window.pywebview && window.pywebview.api;
    if (!api || typeof api.report_frontend_state !== 'function') return;
    var reports = pending;
    pending = [];
    reports.forEach(function (r) {
      try {
        var result = api.report_frontend_state(r.stage, r.details);
        if (result && result.catch) result.catch(function () {});
      } catch (_) { /* The native watchdog still reports an unavailable bridge. */ }
    });
  }

  function send(stage, details) {
    details.userAgent = navigator.userAgent;
    details.url = location.href;
    pending.push({ stage: stage, details: details });
    flush();
  }

  function showFailure() {
    var panel = document.getElementById('startup-status');
    if (!panel) return;
    panel.style.display = 'block';
    panel.setAttribute('role', 'alert');
    document.getElementById('startup-title').textContent = '界面未能正常显示 / Interface could not load';
    document.getElementById('startup-detail').textContent = failureMessage +
      '\n\n请查看错误弹窗和启动日志。若窗口空白或黑屏，请关闭后用“兼容显示模式”启动文件重试。' +
      '\nPlease check the error dialog and startup log. For a blank/black window, close it and try the safe-render launcher.';
  }

  window.__war3Startup = {
    ready: function () {
      if (failed || painted) return;
      painted = true;
      var panel = document.getElementById('startup-status');
      if (panel) panel.style.display = 'none';
      send('ready', { page: document.querySelector('[data-testid="stage"]').getAttribute('data-page') });
    },
    fail: function (message, stack) {
      if (failed) return;
      failed = true;
      failureMessage = String(message || 'Unknown frontend error');
      showFailure();
      send('failed', { message: failureMessage, stack: String(stack || '') });
    }
  };
  window.addEventListener('pywebviewready', flush);
  document.addEventListener('DOMContentLoaded', function () { if (failed) showFailure(); });
  window.addEventListener('error', function (event) {
    var target = event.target;
    var resource = target && (target.tagName === 'SCRIPT' || target.tagName === 'LINK');
    var source = resource ? (target.src || target.href || '') : (event.filename || '');
    var text = resource ? '界面资源加载失败 / Interface resource failed: ' + source :
      (event.message || 'Unknown script error');
    if (!painted || resource) window.__war3Startup.fail(text, event.error && event.error.stack);
    else send('runtime_error', { message: text, source: source, stack: String(event.error && event.error.stack || '') });
  }, true);
  window.addEventListener('unhandledrejection', function (event) {
    var error = event.reason;
    if (!painted) window.__war3Startup.fail(error && error.message || String(error), error && error.stack);
    else send('runtime_error', { message: String(error && error.message || error), stack: String(error && error.stack || '') });
  });
})();
