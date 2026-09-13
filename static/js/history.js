/**
 * history.js - DiaBeates history controls
 * Strict CSP compliant: handles delete confirmation, export, and clear-history dialogs.
 */
(function () {
  'use strict';

  // 1. Delete Single Assessment Modal
  const deleteModal = document.getElementById('deleteConfirmModal');
  if (deleteModal) {
    const dialog = deleteModal.querySelector('[role="dialog"]');
    const form = document.getElementById('deleteAssessmentForm');
    const targetLabel = document.getElementById('deleteTargetLabel');
    const cancelBtn = document.getElementById('cancelDeleteBtn');
    const closeXBtn = document.getElementById('cancelDeleteXBtn');
    const confirmBtn = document.getElementById('confirmDeleteSubmitBtn');
    const triggers = document.querySelectorAll('.js-delete-trigger');

    let activeTrigger = null;
    let isClosing = false;

    const openModal = (id, index, date, trigger) => {
      activeTrigger = trigger;
      if (trigger) trigger.setAttribute('aria-expanded', 'true');

      if (form) {
        form.action = `/history/${encodeURIComponent(id)}/delete`;
        form.setAttribute('action', `/history/${encodeURIComponent(id)}/delete`);
      }
      if (targetLabel) {
        targetLabel.textContent = index ? `Assessment #${index}${date ? ' (' + date + ')' : ''}` : 'this assessment';
      }

      deleteModal.hidden = false;
      document.body.classList.add('overflow-hidden');

      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          deleteModal.classList.add('is-open');
          if (cancelBtn) cancelBtn.focus();
        });
      });
    };

    const closeModal = () => {
      if (isClosing || deleteModal.hidden) return;
      isClosing = true;

      deleteModal.classList.remove('is-open');

      const finalizeClose = () => {
        deleteModal.hidden = true;
        document.body.classList.remove('overflow-hidden');
        isClosing = false;
        if (activeTrigger) {
          activeTrigger.setAttribute('aria-expanded', 'false');
          activeTrigger.focus();
          activeTrigger = null;
        }
      };

      const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      if (prefersReducedMotion) {
        finalizeClose();
      } else {
        setTimeout(finalizeClose, 200);
      }
    };

    triggers.forEach(trigger => {
      trigger.addEventListener('click', (e) => {
        e.preventDefault();
        const id = trigger.getAttribute('data-id');
        const index = trigger.getAttribute('data-index');
        const date = trigger.getAttribute('data-date');
        openModal(id, index, date, trigger);
      });
    });

    if (cancelBtn) cancelBtn.addEventListener('click', closeModal);
    if (closeXBtn) closeXBtn.addEventListener('click', closeModal);

    deleteModal.addEventListener('click', (e) => {
      if (e.target === deleteModal) {
        closeModal();
      }
    });

    document.addEventListener('keydown', (e) => {
      if (deleteModal.hidden) return;
      if (e.key === 'Escape') {
        e.preventDefault();
        closeModal();
      }
    });

    if (form && confirmBtn) {
      form.addEventListener('submit', () => {
        confirmBtn.disabled = true;
        confirmBtn.classList.add('opacity-75', 'cursor-not-allowed');
      });
    }
  }

  // 2. Clear All History Confirmation Modal
  const clearModal = document.getElementById('clearConfirmModal');
  const openClearBtn = document.getElementById('openClearHistoryBtn');
  if (clearModal && openClearBtn) {
    const cancelClearBtn = document.getElementById('cancelClearBtn');
    const closeClearXBtn = document.getElementById('cancelClearXBtn');
    const clearForm = document.getElementById('clearHistoryForm');
    const confirmClearSubmitBtn = document.getElementById('confirmClearSubmitBtn');

    const openClear = () => {
      clearModal.hidden = false;
      document.body.classList.add('overflow-hidden');
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          clearModal.classList.add('is-open');
          if (cancelClearBtn) cancelClearBtn.focus();
        });
      });
    };

    const closeClear = () => {
      clearModal.classList.remove('is-open');
      setTimeout(() => {
        clearModal.hidden = true;
        document.body.classList.remove('overflow-hidden');
        openClearBtn.focus();
      }, 200);
    };

    openClearBtn.addEventListener('click', openClear);
    if (cancelClearBtn) cancelClearBtn.addEventListener('click', closeClear);
    if (closeClearXBtn) closeClearXBtn.addEventListener('click', closeClear);

    clearModal.addEventListener('click', (e) => {
      if (e.target === clearModal) closeClear();
    });

    document.addEventListener('keydown', (e) => {
      if (!clearModal.hidden && e.key === 'Escape') {
        e.preventDefault();
        closeClear();
      }
    });

    if (clearForm && confirmClearSubmitBtn) {
      clearForm.addEventListener('submit', () => {
        confirmClearSubmitBtn.disabled = true;
        confirmClearSubmitBtn.classList.add('opacity-75', 'cursor-not-allowed');
      });
    }
  }
})();

