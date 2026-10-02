document.addEventListener('DOMContentLoaded', () => {
  const currentYearEl = document.getElementById('currentYear');
  if (currentYearEl) {
    currentYearEl.textContent = new Date().getFullYear();
  }

  // Mobile menu toggle
  const menuBtn = document.getElementById('menuBtn');
  const mobileMenu = document.getElementById('mobileMenu');
  if (menuBtn && mobileMenu) {
    menuBtn.addEventListener('click', () => {
      mobileMenu.classList.toggle('hidden');
    });
  }
});

(function () {
  const modal = document.getElementById('disclaimerModal');
  if (!modal) return;
  const dialog = modal.querySelector('[role="dialog"]');
  const closeButton = document.getElementById('disclaimerClose');
  const cancelButton = document.getElementById('disclaimerCancel');
  const agreeButton = document.getElementById('disclaimerAgree');
  const acceptanceKey = 'diabeates:intended-use-accepted';
  let pendingDestination = '/assessment';
  let previousFocus = null;

  const hasAccepted = () => {
    try {
      return sessionStorage.getItem(acceptanceKey) === '1';
    } catch (error) {
      return false;
    }
  };

  const setAccepted = () => {
    try {
      sessionStorage.setItem(acceptanceKey, '1');
    } catch (error) {
      // Continue to the assessment if storage is unavailable.
    }
  };

  const closeModal = () => {
    modal.hidden = true;
    document.body.classList.remove('overflow-hidden');
    if (previousFocus) previousFocus.focus();
  };

  const openModal = (destination, trigger) => {
    pendingDestination = destination;
    previousFocus = trigger;
    modal.hidden = false;
    document.body.classList.add('overflow-hidden');
    dialog.focus();
  };

  document.addEventListener('click', (event) => {
    const anchor = event.target.closest('a[href]');
    if (!anchor || event.defaultPrevented || anchor.target && anchor.target !== '_self') return;
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;

    const url = new URL(anchor.href, window.location.href);
    if (url.origin !== window.location.origin || url.pathname !== '/assessment' || url.pathname === window.location.pathname) return;
    if (hasAccepted()) return;

    event.preventDefault();
    openModal(anchor.href, anchor);
  });

  if (closeButton) closeButton.addEventListener('click', closeModal);
  if (cancelButton) cancelButton.addEventListener('click', closeModal);
  modal.addEventListener('click', (event) => {
    if (event.target === modal) closeModal();
  });
  document.addEventListener('keydown', (event) => {
    if (!modal.hidden && event.key === 'Escape') closeModal();
  });
  if (agreeButton) {
    agreeButton.addEventListener('click', () => {
      setAccepted();
      closeModal();
      window.location.assign(pendingDestination);
    });
  }
}());


