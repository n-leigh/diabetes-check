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

  const modal = document.getElementById('feedbackModal');
  const openButton = document.getElementById('openFeedbackBtn');
  const closeButton = document.getElementById('closeFeedbackBtn');
  const cancelButton = document.getElementById('cancelFeedbackBtn');
  const form = document.getElementById('feedbackForm');
  const submitButton = document.getElementById('submitFeedbackBtn');
  const successMessage = document.getElementById('feedbackSuccess');
  const errorMessage = document.getElementById('feedbackError');
  if (!modal || !openButton || !closeButton || !cancelButton || !form || !submitButton) return;

  let previousFocus = null;
  const closeModal = () => {
    modal.classList.add('hidden');
    modal.classList.remove('flex');
    document.body.classList.remove('overflow-hidden');
    if (previousFocus) previousFocus.focus();
  };
  const openModal = () => {
    previousFocus = document.activeElement;
    modal.classList.remove('hidden');
    modal.classList.add('flex');
    document.body.classList.add('overflow-hidden');
    document.getElementById('feedbackMessage').focus();
  };
  const showError = (message) => {
    errorMessage.textContent = message;
    errorMessage.classList.remove('hidden');
  };

  openButton.addEventListener('click', openModal);
  closeButton.addEventListener('click', closeModal);
  cancelButton.addEventListener('click', closeModal);
  modal.addEventListener('click', (event) => {
    if (event.target === modal) closeModal();
  });
  document.addEventListener('keydown', (event) => {
    if (!modal.classList.contains('hidden') && event.key === 'Escape') closeModal();
  });
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    errorMessage.classList.add('hidden');
    successMessage.classList.add('hidden');
    submitButton.disabled = true;
    submitButton.textContent = 'Submitting...';
    try {
      const response = await fetch('/api/feedback', {
        method: 'POST',
        body: new FormData(form),
        headers: { Accept: 'application/json' }
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || 'We could not save your feedback. Please try again.');
      form.reset();
      successMessage.classList.remove('hidden');
      window.setTimeout(closeModal, 2000);
    } catch (error) {
      showError(error.message);
    } finally {
      submitButton.disabled = false;
      submitButton.textContent = 'Submit Feedback';
    }
  });
});
