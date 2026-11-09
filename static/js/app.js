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
      passwordStrengthMessage.classList.toggle('hidden', !passwordTooShort);
      confirmPasswordMessage.classList.toggle('hidden', !passwordsDoNotMatch);
      confirmPassword.setCustomValidity(passwordsDoNotMatch ? 'Passwords do not match.' : '');
      registerPassword.classList.toggle('password-input-warning', passwordTooShort);
      confirmPassword.classList.toggle('password-input-warning', passwordsDoNotMatch);
    };

    registerPassword.addEventListener('input', updatePasswordMessages);
    confirmPassword.addEventListener('input', updatePasswordMessages);
    updatePasswordMessages();
  }

  let pendingConfirmation = null;
  let confirmationDialog = null;

  const getConfirmationDialog = () => {
    if (confirmationDialog) return confirmationDialog;
    if (!window.HTMLDialogElement || typeof HTMLDialogElement.prototype.showModal !== 'function') {
      return null;
    }

    const dialog = document.createElement('dialog');
    dialog.className = 'action-confirm-dialog';
    dialog.setAttribute('aria-modal', 'true');
    dialog.setAttribute('aria-labelledby', 'action-confirm-title');
    dialog.setAttribute('aria-describedby', 'action-confirm-message');

    const panel = document.createElement('div');
    panel.className = 'action-confirm-panel';

    const header = document.createElement('header');
    header.className = 'action-confirm-header';

    const heading = document.createElement('h2');
    heading.id = 'action-confirm-title';
    heading.textContent = 'Please confirm';

    const closeButton = document.createElement('button');
    closeButton.className = 'action-confirm-close';
    closeButton.type = 'button';
    closeButton.setAttribute('aria-label', 'Close confirmation');
    closeButton.textContent = '×';
    closeButton.addEventListener('click', () => dialog.close('cancel'));

    header.append(heading, closeButton);

    const content = document.createElement('div');
    content.className = 'action-confirm-content';

    const message = document.createElement('p');
    message.id = 'action-confirm-message';
    content.append(message);

    const footer = document.createElement('footer');
    footer.className = 'action-confirm-footer';

    const cancelButton = document.createElement('button');
    cancelButton.className = 'btn-secondary';
    cancelButton.type = 'button';
    cancelButton.textContent = 'Cancel';
    cancelButton.addEventListener('click', () => dialog.close('cancel'));

    const confirmButton = document.createElement('button');
    confirmButton.className = 'btn-primary';
    confirmButton.type = 'button';
    confirmButton.textContent = 'Confirm';
    confirmButton.addEventListener('click', () => {
      const current = pendingConfirmation;
      dialog.close('confirm');
      if (!current) return;
      current.form.dataset.confirmed = 'true';
      current.form.requestSubmit(current.submitter || undefined);
    });

    footer.append(cancelButton, confirmButton);
    panel.append(header, content, footer);
    dialog.append(panel);
    dialog.addEventListener('click', (event) => {
      if (event.target === dialog) dialog.close('cancel');
    });
    dialog.addEventListener('close', () => {
      const current = pendingConfirmation;
      pendingConfirmation = null;
      if (current && current.submitter) current.submitter.focus();
    });

    document.body.append(dialog);
    confirmationDialog = { dialog, message, confirmButton, cancelButton };
    return confirmationDialog;
  };

  document.addEventListener('submit', (event) => {
    const form = event.target instanceof HTMLFormElement ? event.target : null;
    if (!form) return;
    const message = form.dataset.confirmMessage;
    if (!message) return;
    if (form.dataset.confirmed === 'true') {
      delete form.dataset.confirmed;
      return;
    }

    event.preventDefault();
    const confirmation = getConfirmationDialog();
    if (!confirmation) {
      if (window.confirm(message)) form.requestSubmit(event.submitter || undefined);
      return;
    }

    pendingConfirmation = { form, submitter: event.submitter };
    confirmation.message.textContent = message;
    confirmation.confirmButton.textContent = form.dataset.confirmLabel || 'Confirm';
    confirmation.confirmButton.classList.toggle(
      'action-confirm-danger',
      form.dataset.confirmVariant === 'danger'
    );
    confirmation.dialog.showModal();
    confirmation.cancelButton.focus();
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
