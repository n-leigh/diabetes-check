/**
 * result.js - DiaBeates results presentation scripts
 * Strict CSP compliant: sets indicator marker positions dynamically.
 */
document.addEventListener('DOMContentLoaded', () => {
  'use strict';
  document.querySelectorAll('.segment-marker[data-pos]').forEach((el) => {
    const pos = parseFloat(el.getAttribute('data-pos'));
    if (!isNaN(pos)) {
      el.style.left = pos + '%';
    }
  });
});
