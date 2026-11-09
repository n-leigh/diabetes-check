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

  const setupPasswordToggle = (passwordInput, passwordToggle) => {
    if (!passwordInput || !passwordToggle) return;
    const showIcon = passwordToggle.querySelector('[data-password-icon="show"]');
    const hideIcon = passwordToggle.querySelector('[data-password-icon="hide"]');
    passwordToggle.addEventListener('click', () => {
      const isVisible = passwordInput.type === 'text';
      passwordInput.type = isVisible ? 'password' : 'text';
      passwordToggle.setAttribute('aria-label', isVisible ? 'Show password' : 'Hide password');
      passwordToggle.setAttribute('aria-pressed', String(!isVisible));
      if (showIcon) showIcon.classList.toggle('hidden', !isVisible);
      if (hideIcon) hideIcon.classList.toggle('hidden', isVisible);
      passwordInput.focus();
    });
  };

  setupPasswordToggle(document.getElementById('loginPassword'), document.getElementById('loginPasswordToggle'));
  setupPasswordToggle(document.getElementById('registerPassword'), document.getElementById('registerPasswordToggle'));
  setupPasswordToggle(document.getElementById('confirmPassword'), document.getElementById('confirmPasswordToggle'));

  const registerPassword = document.getElementById('registerPassword');
  const confirmPassword = document.getElementById('confirmPassword');
  const passwordStrengthMessage = document.getElementById('passwordStrengthMessage');
  const confirmPasswordMessage = document.getElementById('confirmPasswordMessage');
  if (registerPassword && confirmPassword && passwordStrengthMessage && confirmPasswordMessage) {
    const updatePasswordMessages = () => {
      const password = registerPassword.value;
      const confirmation = confirmPassword.value;
      const passwordTooShort = password.length > 0 && password.length < 8;
      const passwordsDoNotMatch = confirmation.length > 0 && password !== confirmation;

      passwordStrengthMessage.hidden = !passwordTooShort;
      confirmPasswordMessage.hidden = !passwordsDoNotMatch;
      confirmPassword.setCustomValidity(passwordsDoNotMatch ? 'Passwords do not match.' : '');
      registerPassword.classList.toggle('password-input-warning', passwordTooShort);
      confirmPassword.classList.toggle('password-input-warning', passwordsDoNotMatch);
    };

    registerPassword.addEventListener('input', updatePasswordMessages);
    confirmPassword.addEventListener('input', updatePasswordMessages);
    updatePasswordMessages();
  }

  document.addEventListener('submit', (event) => {
    const form = event.target instanceof HTMLFormElement ? event.target : null;
    if (!form) return;
    const message = form.dataset.confirmMessage;
    if (!message) return;
    if (!window.confirm(message)) {
      event.preventDefault();
    }
  });
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
