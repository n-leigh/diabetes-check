/**
 * Refresh the ownership-scoped history page when Flask reports a change.
 * The browser never connects to Supabase or receives database credentials.
 */
(function () {
  'use strict';

  const status = document.getElementById('historyLiveStatus');
  const view = window.DIABEATES_HISTORY_VIEW || 'active';
  const signatureUrl = `/history/signature?view=${encodeURIComponent(view)}`;
  let lastSignature = null;
  let checking = false;

  async function checkForChanges() {
    if (checking || document.hidden) return;
    checking = true;
    try {
      const response = await fetch(signatureUrl, {
        headers: { 'Accept': 'application/json' },
        credentials: 'same-origin',
        cache: 'no-store'
      });
      if (!response.ok) return;
      const signature = await response.json();
      const current = `${signature.count}:${signature.latest_id}`;
      if (lastSignature === null) {
        lastSignature = current;
      } else if (current !== lastSignature) {
        if (status) status.textContent = 'Your history was updated. Refreshing.';
        window.location.reload();
      }
    } catch (error) {
      // A temporary network error is safe; the next interval retries.
    } finally {
      checking = false;
    }
  }

  checkForChanges();
  window.setInterval(checkForChanges, 10000);
})();
