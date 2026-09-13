/**
 * app.js - DiaBeates core client scripts
 * Strict CSP compliant: no inline execution, zero external network dependencies.
 */
(function () {
  'use strict';

  // 1. Mobile Menu Toggle
  const menuBtn = document.getElementById('menuBtn');
  const mobileMenu = document.getElementById('mobileMenu');
  if (menuBtn && mobileMenu) {
    menuBtn.addEventListener('click', function () {
      mobileMenu.classList.toggle('hidden');
    });
  }

  // 2. Copyright Year
  const yearEl = document.getElementById('currentYear');
  if (yearEl) {
    yearEl.textContent = new Date().getFullYear();
  }

  // 3. Intended Use / Clinical Disclaimer Modal
  const modal = document.getElementById('disclaimerModal');
  if (modal) {
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
      } catch (e) {
        return false;
      }
    };

    const setAccepted = () => {
      try {
        sessionStorage.setItem(acceptanceKey, '1');
      } catch (e) {
        // Storage disabled; proceed anyway
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
      if (dialog) dialog.focus();
    };

    document.addEventListener('click', (event) => {
      const anchor = event.target.closest('a[href]');
      if (!anchor || event.defaultPrevented || (anchor.target && anchor.target !== '_self')) return;
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
  }

  // 4. Page Transitions
  (function () {
    const body = document.body;
    let isLeaving = false;
    let revealTimer;
    let leaveFailSafeTimer;
    const TRANSITION_FLAG = 'diabeates:page-transition';
    const TRANSITION_PATH_KEY = 'diabeates:page-transition:path';
    const TRANSITION_DURATION_MS = 380;
    const EXIT_DURATION_MS = TRANSITION_DURATION_MS;
    const ENTER_DURATION_MS = TRANSITION_DURATION_MS;
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    const getPathFromUrl = (url) => {
      try {
        return new URL(url, window.location.href).pathname;
      } catch (e) {
        return window.location.pathname;
      }
    };

    const getTransitionFlag = () => {
      try {
        return sessionStorage.getItem(TRANSITION_FLAG) === '1';
      } catch (e) {
        return false;
      }
    };

    const getTransitionPath = () => {
      try {
        return sessionStorage.getItem(TRANSITION_PATH_KEY);
      } catch (e) {
        return null;
      }
    };

    const setTransitionState = (targetPath) => {
      try {
        sessionStorage.setItem(TRANSITION_FLAG, '1');
        sessionStorage.setItem(TRANSITION_PATH_KEY, targetPath);
      } catch (e) {}
    };

    const clearTransitionState = () => {
      try {
        sessionStorage.removeItem(TRANSITION_FLAG);
        sessionStorage.removeItem(TRANSITION_PATH_KEY);
      } catch (e) {}
    };

    const runEnterAnimation = () => {
      if (prefersReducedMotion) return;
      window.clearTimeout(revealTimer);
      body.classList.remove('is-transitioning');
      body.classList.add('is-revealing');
      revealTimer = window.setTimeout(() => {
        body.classList.remove('is-revealing');
      }, ENTER_DURATION_MS);
    };

    const clearTransitionClasses = () => {
      window.clearTimeout(revealTimer);
      window.clearTimeout(leaveFailSafeTimer);
      isLeaving = false;
      body.classList.remove('is-transitioning');
      body.classList.remove('is-revealing');
    };

    const shouldHandleLink = (anchor, event) => {
      if (!anchor || isLeaving) return false;
      if (event.defaultPrevented) return false;
      if (anchor.target && anchor.target !== '_self') return false;
      if (anchor.hasAttribute('download')) return false;
      if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return false;

      const href = anchor.getAttribute('href');
      if (!href || href.startsWith('#') || href.startsWith('javascript:')) return false;

      const url = new URL(anchor.href, window.location.href);
      if (url.origin !== window.location.origin) return false;
      if (url.href === window.location.href) return false;
      return true;
    };

    const shouldHandleForm = (form, event) => {
      if (!form || isLeaving) return false;
      if (event.defaultPrevented) return false;
      if (form.target && form.target !== '_self') return false;

      const method = (form.method || 'get').toLowerCase();
      if (method === 'dialog') return false;

      const action = form.getAttribute('action') || window.location.href;
      if (action.startsWith('javascript:')) return false;

      const url = new URL(form.action || window.location.href, window.location.href);
      if (url.origin !== window.location.origin) return false;
      return true;
    };

    const startTransition = (navigate, targetUrl) => {
      isLeaving = true;
      setTransitionState(getPathFromUrl(targetUrl));
      body.classList.remove('is-revealing');
      body.classList.add('is-transitioning');

      window.clearTimeout(leaveFailSafeTimer);
      leaveFailSafeTimer = window.setTimeout(() => {
        if (document.visibilityState === 'visible') {
          clearTransitionState();
          clearTransitionClasses();
        }
      }, EXIT_DURATION_MS + 1200);

      window.setTimeout(() => {
        navigate();
      }, EXIT_DURATION_MS);
    };

    clearTransitionClasses();

    const shouldRunEnter = getTransitionFlag();
    const expectedPath = getTransitionPath();
    const currentPath = window.location.pathname;
    if (shouldRunEnter && expectedPath === currentPath) {
      clearTransitionState();
      runEnterAnimation();
    } else {
      clearTransitionState();
    }

    window.addEventListener('pageshow', (event) => {
      clearTransitionClasses();
      if (event.persisted) {
        runEnterAnimation();
      }
    });

    document.addEventListener('click', (event) => {
      const anchor = event.target.closest('a[href]');
      if (!shouldHandleLink(anchor, event)) return;
      if (prefersReducedMotion) return;

      event.preventDefault();
      startTransition(() => {
        window.location.assign(anchor.href);
      }, anchor.href);
    });

    document.addEventListener('submit', (event) => {
      const form = event.target;
      if (!shouldHandleForm(form, event)) return;
      if (prefersReducedMotion) return;

      event.preventDefault();
      const destination = form.action || window.location.href;
      startTransition(() => {
        form.submit();
      }, destination);
    });
  })();
})();

