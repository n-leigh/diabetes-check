/**
 * result.js - Client-side report link generator for DiaBeates
 * Strict CSP compliant: derives keys and encrypts via WebCrypto purely in browser.
 */
(function () {
  'use strict';

  function bytesToBase64Url(bytes) {
    let binary = '';
    for (let i = 0; i < bytes.length; i++) {
      binary += String.fromCharCode(bytes[i]);
    }
    return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  }

  function utf8ToBytes(str) {
    return new TextEncoder().encode(str);
  }

  async function encryptV1(plaintext, passphrase) {
    const salt = crypto.getRandomValues(new Uint8Array(16));
    const iv = crypto.getRandomValues(new Uint8Array(12));

    const baseKey = await crypto.subtle.importKey(
      'raw',
      utf8ToBytes(passphrase),
      'PBKDF2',
      false,
      ['deriveKey']
    );

    const aesKey = await crypto.subtle.deriveKey(
      {
        name: 'PBKDF2',
        salt: salt,
        iterations: 310000,
        hash: 'SHA-256'
      },
      baseKey,
      { name: 'AES-GCM', length: 256 },
      false,
      ['encrypt']
    );

    const ciphertextBuffer = await crypto.subtle.decrypt
      ? await crypto.subtle.encrypt(
          { name: 'AES-GCM', iv: iv, tagLength: 128 },
          aesKey,
          utf8ToBytes(plaintext)
        )
      : null;

    const ciphertextBytes = new Uint8Array(ciphertextBuffer);

    return (
      'v1.' +
      bytesToBase64Url(salt) +
      '.' +
      bytesToBase64Url(iv) +
      '.' +
      bytesToBase64Url(ciphertextBytes)
    );
  }

  const openShareBtn = document.getElementById('openShareReportBtn');
  const shareModal = document.getElementById('shareReportModal');
  const closeShareBtn = document.getElementById('closeShareReportBtn');
  const cancelShareBtn = document.getElementById('cancelShareReportBtn');

  const tabUnencrypted = document.getElementById('tabShareUnencrypted');
  const tabEncrypted = document.getElementById('tabShareEncrypted');
  const panelUnencrypted = document.getElementById('panelShareUnencrypted');
  const panelEncrypted = document.getElementById('panelShareEncrypted');

  const unencryptedLinkInput = document.getElementById('unencryptedReportLink');
  const copyUnencryptedBtn = document.getElementById('copyUnencryptedLinkBtn');

  const encryptedPassphraseInput = document.getElementById('encryptedPassphraseInput');
  const generateEncryptedBtn = document.getElementById('generateEncryptedLinkBtn');
  const encryptedLinkContainer = document.getElementById('encryptedLinkContainer');
  const encryptedLinkInput = document.getElementById('encryptedReportLink');
  const copyEncryptedBtn = document.getElementById('copyEncryptedLinkBtn');
  const encryptError = document.getElementById('encryptErrorMsg');

  const reportDataEl = document.getElementById('assessmentReportData');
  let reportJson = null;
  if (reportDataEl) {
    try {
      reportJson = JSON.parse(reportDataEl.textContent);
    } catch (e) {
      reportJson = null;
    }
  }

  function setShareTab(type) {
    if (type === 'unencrypted') {
      tabUnencrypted.setAttribute('aria-selected', 'true');
      tabUnencrypted.classList.add('bg-white', 'text-teal-700', 'shadow-xs');
      tabUnencrypted.classList.remove('text-slate-600');

      tabEncrypted.setAttribute('aria-selected', 'false');
      tabEncrypted.classList.remove('bg-white', 'text-teal-700', 'shadow-xs');
      tabEncrypted.classList.add('text-slate-600');

      panelUnencrypted.classList.remove('hidden');
      panelEncrypted.classList.add('hidden');
    } else {
      tabEncrypted.setAttribute('aria-selected', 'true');
      tabEncrypted.classList.add('bg-white', 'text-teal-700', 'shadow-xs');
      tabEncrypted.classList.remove('text-slate-600');

      tabUnencrypted.setAttribute('aria-selected', 'false');
      tabUnencrypted.classList.remove('bg-white', 'text-teal-700', 'shadow-xs');
      tabUnencrypted.classList.add('text-slate-600');

      panelEncrypted.classList.remove('hidden');
      panelUnencrypted.classList.add('hidden');
      if (encryptedPassphraseInput) encryptedPassphraseInput.focus();
    }
  }

  if (openShareBtn && shareModal && reportJson) {
    const rawPlaintext = JSON.stringify(reportJson);
    const base64UrlUnencrypted = bytesToBase64Url(utf8ToBytes(rawPlaintext));
    const baseUrl = window.location.origin + '/report';
    const unencryptedUrl = baseUrl + '#report=' + base64UrlUnencrypted;
    if (unencryptedLinkInput) {
      unencryptedLinkInput.value = unencryptedUrl;
    }

    const focusableSelectors = 'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])';
    let firstFocusable, lastFocusable;

    const updateFocusable = () => {
      const focusableElements = shareModal.querySelectorAll(focusableSelectors);
      const visibleFocusable = Array.from(focusableElements).filter(el => el.offsetWidth > 0 || el.offsetHeight > 0);
      firstFocusable = visibleFocusable[0];
      lastFocusable = visibleFocusable[visibleFocusable.length - 1];
    };

    const handleTabKey = (e) => {
      if (e.key !== 'Tab') return;
      updateFocusable();
      if (!firstFocusable || !lastFocusable) return;
      if (e.shiftKey) {
        if (document.activeElement === firstFocusable) {
          lastFocusable.focus();
          e.preventDefault();
        }
      } else {
        if (document.activeElement === lastFocusable) {
          firstFocusable.focus();
          e.preventDefault();
        }
      }
    };

    const openModal = () => {
      shareModal.hidden = false;
      document.body.classList.add('overflow-hidden');
      shareModal.addEventListener('keydown', handleTabKey);
      requestAnimationFrame(() => {
        shareModal.classList.add('is-open');
        updateFocusable();
        if (firstFocusable) firstFocusable.focus();
      });
    };

    const closeModal = () => {
      shareModal.classList.remove('is-open');
      shareModal.removeEventListener('keydown', handleTabKey);
      setTimeout(() => {
        shareModal.hidden = true;
        document.body.classList.remove('overflow-hidden');
        openShareBtn.focus();
      }, 200);
    };

    openShareBtn.addEventListener('click', openModal);
    if (closeShareBtn) closeShareBtn.addEventListener('click', closeModal);
    if (cancelShareBtn) cancelShareBtn.addEventListener('click', closeModal);

    shareModal.addEventListener('click', (e) => {
      if (e.target === shareModal) closeModal();
    });

    document.addEventListener('keydown', (e) => {
      if (!shareModal.hidden && e.key === 'Escape') {
        e.preventDefault();
        closeModal();
      }
    });

    if (tabUnencrypted && tabEncrypted) {
      tabUnencrypted.addEventListener('click', () => setShareTab('unencrypted'));
      tabEncrypted.addEventListener('click', () => setShareTab('encrypted'));
    }

    if (copyUnencryptedBtn && unencryptedLinkInput) {
      copyUnencryptedBtn.addEventListener('click', () => {
        navigator.clipboard.writeText(unencryptedLinkInput.value).then(() => {
          copyUnencryptedBtn.textContent = 'Copied!';
          setTimeout(() => { copyUnencryptedBtn.textContent = 'Copy Link'; }, 2000);
        });
      });
    }

    if (generateEncryptedBtn && encryptedPassphraseInput) {
      generateEncryptedBtn.addEventListener('click', async () => {
        const pass = encryptedPassphraseInput.value.trim();
        if (!pass) {
          if (encryptError) {
            encryptError.textContent = 'Please enter a passphrase to encrypt your report.';
            encryptError.classList.remove('hidden');
          }
          return;
        }

        if (encryptError) encryptError.classList.add('hidden');
        generateEncryptedBtn.disabled = true;
        generateEncryptedBtn.textContent = 'Encrypting...';

        try {
          const fragment = await encryptV1(rawPlaintext, pass);
          const encryptedUrl = baseUrl + '#encrypted=' + fragment;
          if (encryptedLinkInput) encryptedLinkInput.value = encryptedUrl;
          if (encryptedLinkContainer) encryptedLinkContainer.classList.remove('hidden');
          generateEncryptedBtn.textContent = 'Re-encrypt with New Key';
          generateEncryptedBtn.disabled = false;
        } catch (err) {
          if (encryptError) {
            encryptError.textContent = 'Encryption failed: ' + err.message;
            encryptError.classList.remove('hidden');
          }
          generateEncryptedBtn.disabled = false;
          generateEncryptedBtn.textContent = 'Generate Encrypted Link';
        }
      });
    }

    if (copyEncryptedBtn && encryptedLinkInput) {
      copyEncryptedBtn.addEventListener('click', () => {
        navigator.clipboard.writeText(encryptedLinkInput.value).then(() => {
          copyEncryptedBtn.textContent = 'Copied!';
          setTimeout(() => { copyEncryptedBtn.textContent = 'Copy Link'; }, 2000);
        });
      });
    }
  }
})();

