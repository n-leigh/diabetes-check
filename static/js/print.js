/**
 * print.js - DiaBeates print triggers
 * Strict CSP compliant: handles print dialog triggering via event listeners.
 */
(function () {
  'use strict';
  const printBtn = document.getElementById('printTriggerBtn');
  if (printBtn) {
    printBtn.addEventListener('click', function () {
      window.print();
    });
  }

  const urlParams = new URLSearchParams(window.location.search);
  if (urlParams.get('auto') === '1') {
    setTimeout(function() {
      window.print();
    }, 500);
  }
})();

