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
})();

