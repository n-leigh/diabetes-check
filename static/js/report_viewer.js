/**
 * report_viewer.js - DiaBeates client-side report viewer
 * Decodes and decrypts clinical assessment reports purely from window.location.hash.
 * Zero server communication, strict DOM-safe rendering (textContent only).
 */
(function () {
  'use strict';

  // Base64url utilities
  function base64UrlToBytes(str) {
    let base64 = str.replace(/-/g, '+').replace(/_/g, '/');
    while (base64.length % 4) {
      base64 += '=';
    }
    const binary = atob(base64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) {
      bytes[i] = binary.charCodeAt(i);
    }
    return bytes;
  }

  function bytesToUtf8(bytes) {
    return new TextDecoder('utf-8').decode(bytes);
  }

  // Cryptographic Decryption
  async function decryptV1(saltBytes, ivBytes, ciphertextBytes, passphrase) {
    const enc = new TextEncoder();
    const passphraseBytes = enc.encode(passphrase);

    const baseKey = await crypto.subtle.importKey(
      'raw',
      passphraseBytes,
      'PBKDF2',
      false,
      ['deriveKey']
    );

    const aesKey = await crypto.subtle.deriveKey(
      {
        name: 'PBKDF2',
        salt: saltBytes,
        iterations: 310000,
        hash: 'SHA-256'
      },
      baseKey,
      { name: 'AES-GCM', length: 256 },
      false,
      ['decrypt']
    );

    const decryptedBuffer = await crypto.subtle.decrypt(
      {
        name: 'AES-GCM',
        iv: ivBytes,
        tagLength: 128
      },
      aesKey,
      ciphertextBytes
    );

    return bytesToUtf8(new Uint8Array(decryptedBuffer));
  }

  // Schema Validator
  const VALID_CATEGORIES = ['cardiovascular', 'neuropathy_mobility', 'general_burden', 'retinopathy'];
  const VALID_TIERS = ['Low', 'Moderate', 'High'];

  function validateReportPayload(data) {
    if (!data || typeof data !== 'object') {
      throw new Error('Report data must be a valid JSON object.');
    }
    if (data.v !== 1 && data.v !== '1') {
      throw new Error('Unsupported report format version.');
    }
    if (!data.created_at || typeof data.created_at !== 'string') {
      throw new Error('Invalid or missing assessment timestamp.');
    }

    if (!data.rule_results || typeof data.rule_results !== 'object') {
      throw new Error('Missing rule_results in assessment report.');
    }
    for (const cat of VALID_CATEGORIES) {
      const res = data.rule_results[cat];
      if (!res || typeof res !== 'object') {
        throw new Error(`Missing assessment data for complication: ${cat}`);
      }
      if (typeof res.percentage !== 'number' || res.percentage < 0 || res.percentage > 100) {
        throw new Error(`Invalid risk percentage for: ${cat}`);
      }
      if (!VALID_TIERS.includes(res.label)) {
        throw new Error(`Invalid risk label for: ${cat}`);
      }
    }

    if (!data.model_confidences || typeof data.model_confidences !== 'object') {
      throw new Error('Missing model probabilities.');
    }
    for (const cat of VALID_CATEGORIES) {
      const prob = data.model_confidences[cat];
      if (typeof prob !== 'number' || prob < 0 || prob > 100) {
        throw new Error(`Invalid model probability for: ${cat}`);
      }
    }

    if (!data.recommendations || typeof data.recommendations !== 'object') {
      throw new Error('Missing recommendations structure.');
    }
    if (!VALID_TIERS.includes(data.recommendations.overall_tier)) {
      throw new Error('Invalid overall tier in recommendations.');
    }
    if (!Array.isArray(data.recommendations.steps)) {
      throw new Error('Recommendations steps must be an array.');
    }

    return true;
  }

  // DOM Rendering via Safe Element APIs
  function getTierClasses(tier) {
    if (tier === 'Low') {
      return {
        bg: 'bg-emerald-50',
        text: 'text-emerald-700',
        border: 'border-emerald-200',
        badge: 'bg-emerald-100 text-emerald-800 border-emerald-200'
      };
    }
    if (tier === 'Moderate') {
      return {
        bg: 'bg-amber-50',
        text: 'text-amber-800',
        border: 'border-amber-200',
        badge: 'bg-amber-100 text-amber-800 border-amber-200'
      };
    }
    return {
      bg: 'bg-red-50',
      text: 'text-red-700',
      border: 'border-red-200',
      badge: 'bg-red-100 text-red-700 border-red-200'
    };
  }

  function getMlTierClasses(mlLabel) {
    if (!mlLabel || mlLabel.toLowerCase().includes('lower')) {
      return {
        bg: 'bg-emerald-50',
        border: 'border-emerald-200',
        text: 'text-emerald-700',
        sub: 'text-emerald-600',
        head: 'text-emerald-500'
      };
    }
    if (mlLabel.toLowerCase().includes('moderate')) {
      return {
        bg: 'bg-amber-50',
        border: 'border-amber-200',
        text: 'text-amber-800',
        sub: 'text-amber-700',
        head: 'text-amber-600'
      };
    }
    // Higher Estimated Risk
    return {
      bg: 'bg-red-50',
      border: 'border-red-200',
      text: 'text-red-700',
      sub: 'text-red-600',
      head: 'text-red-500'
    };
  }

  // Maps an ML category label string → canonical tier ('Low' | 'Moderate' | 'High')
  function mlLabelToTier(mlLabel) {
    if (!mlLabel) return null;
    const l = mlLabel.toLowerCase();
    if (l.includes('lower')) return 'Low';
    if (l.includes('moderate')) return 'Moderate';
    if (l.includes('higher')) return 'High';
    return null;
  }

  const DOMAIN_LABELS = {
    cardiovascular: 'Cardiovascular Risk (ASCVD)',
    general_burden: 'Kidney / Multisystem Risk (CKD)',
    neuropathy_mobility: 'Neuropathy & Mobility Deficit',
    retinopathy: 'Diabetic Retinopathy & Vision'
  };

  function renderReport(data) {
    const root = document.getElementById('reportRoot');
    if (!root) return;

    // Clear root
    while (root.firstChild) {
      root.removeChild(root.firstChild);
    }

    const container = document.createElement('div');
    container.className = 'max-w-4xl mx-auto space-y-8';

    // Header card
    const headerCard = document.createElement('div');
    headerCard.className = 'bg-white rounded-3xl border border-slate-200 p-6 sm:p-8 shadow-sm';

    const headerTop = document.createElement('div');
    headerTop.className = 'flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-100 pb-6 mb-6';

    const titleDiv = document.createElement('div');
    const badge = document.createElement('span');
    badge.className = 'inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-teal-50 text-teal-700 border border-teal-200 mb-2';
    badge.textContent = 'Decentralized Offline Report';
    const title = document.createElement('h1');
    title.className = 'text-2xl sm:text-3xl font-bold font-display text-slate-900';
    title.textContent = 'Clinical Screening Summary';
    titleDiv.appendChild(badge);
    titleDiv.appendChild(title);

    const metaDiv = document.createElement('div');
    metaDiv.className = 'text-left sm:text-right text-xs text-slate-500 space-y-1';
    const dateP = document.createElement('p');
    dateP.textContent = 'Assessment Date: ' + new Date(data.created_at).toLocaleString();
    const modeP = document.createElement('p');
    modeP.className = 'text-teal-600 font-medium';
    modeP.textContent = 'Processed locally by client';
    metaDiv.appendChild(dateP);
    metaDiv.appendChild(modeP);

    headerTop.appendChild(titleDiv);
    headerTop.appendChild(metaDiv);
    headerCard.appendChild(headerTop);

    // Patient Summary if provided
    if (data.patient_summary) {
      const summaryBox = document.createElement('div');
      summaryBox.className = 'bg-slate-50 rounded-2xl p-4 border border-slate-100 text-sm text-slate-700';
      const sumTitle = document.createElement('div');
      sumTitle.className = 'font-semibold text-xs text-slate-500 uppercase tracking-wider mb-2';
      sumTitle.textContent = 'Reported Profile';
      summaryBox.appendChild(sumTitle);

      const pDesc = document.createElement('p');
      pDesc.textContent = data.patient_summary;
      summaryBox.appendChild(pDesc);
      headerCard.appendChild(summaryBox);
    }

    container.appendChild(headerCard);

    // Complication Results Grid
    const compGrid = document.createElement('div');
    compGrid.className = 'grid sm:grid-cols-2 gap-6';

    for (const cat of VALID_CATEGORIES) {
      const rule = data.rule_results[cat];
      const mlProb = data.model_confidences[cat];
      const mlLabel = data.model_results ? data.model_results[cat] : null;

      // Badge driven by ML model classification; fall back to rule label if unavailable
      const mlTier = mlLabelToTier(mlLabel);
      const badgeTier = mlTier || rule.label;
      const tierStyles = getTierClasses(badgeTier);

      const card = document.createElement('div');
      card.className = 'bg-white rounded-3xl border border-slate-200 p-6 shadow-sm flex flex-col justify-between';

      const cardTop = document.createElement('div');
      const cardHeader = document.createElement('div');
      cardHeader.className = 'flex items-start justify-between mb-4';

      const domainName = document.createElement('h2');
      domainName.className = 'font-display font-bold text-lg text-slate-900';
      domainName.textContent = DOMAIN_LABELS[cat] || cat;

      const tierBadge = document.createElement('span');
      tierBadge.className = 'px-3 py-1 rounded-full text-xs font-semibold ' + tierStyles.badge;
      tierBadge.textContent = badgeTier + ' Risk';

      cardHeader.appendChild(domainName);
      cardHeader.appendChild(tierBadge);
      cardTop.appendChild(cardHeader);

      // Rule Matrix Score
      const ruleBox = document.createElement('div');
      ruleBox.className = 'bg-slate-50 rounded-2xl p-4 border border-slate-100 mb-4';
      const ruleLabel = document.createElement('div');
      ruleLabel.className = 'text-xs text-slate-500 font-medium mb-1';
      ruleLabel.textContent = 'Clinical Rule Matrix Screening';
      const ruleScore = document.createElement('div');
      ruleScore.className = 'text-xl font-bold font-display ' + tierStyles.text;
      ruleScore.textContent = rule.percentage + '% of maximum guideline score';
      ruleBox.appendChild(ruleLabel);
      ruleBox.appendChild(ruleScore);
      cardTop.appendChild(ruleBox);

      // Calibrated ML Model Score
      const mlTierStyles = getMlTierClasses(mlLabel);
      const mlBox = document.createElement('div');
      mlBox.className = mlTierStyles.bg + ' rounded-2xl p-4 border ' + mlTierStyles.border + ' mb-4';
      const mlHead = document.createElement('div');
      mlHead.className = 'text-xs font-medium mb-1 ' + mlTierStyles.head;
      mlHead.textContent = 'Calibrated ML Model Prediction';
      const mlScore = document.createElement('div');
      mlScore.className = 'text-xl font-bold font-display ' + mlTierStyles.text;
      mlScore.textContent = mlProb.toFixed(1) + '% probability';
      const mlSub = document.createElement('div');
      mlSub.className = 'text-xs mt-1 font-medium ' + mlTierStyles.sub;
      mlSub.textContent = mlLabel ? 'Category: ' + mlLabel : 'CDC NHANES Trained Model';
      mlBox.appendChild(mlHead);
      mlBox.appendChild(mlScore);
      mlBox.appendChild(mlSub);
      cardTop.appendChild(mlBox);

      // Risk drivers
      const drivers = data.patient_drivers ? data.patient_drivers[cat] : null;
      if (drivers && drivers.length > 0) {
        const drvContainer = document.createElement('div');
        drvContainer.className = 'mt-3 space-y-2';
        const drvTitle = document.createElement('div');
        drvTitle.className = 'text-xs font-semibold text-slate-600 uppercase tracking-wider';
        drvTitle.textContent = 'Key Contributing Factors';
        drvContainer.appendChild(drvTitle);

        drivers.forEach(d => {
          const dItem = document.createElement('div');
          dItem.className = 'text-xs p-2.5 rounded-xl bg-slate-50 border border-slate-100 text-slate-700';
          const dHead = document.createElement('div');
          dHead.className = 'font-semibold text-slate-800 mb-0.5';
          dHead.textContent = d.factor + ' (' + d.impact + ')';
          const dDetail = document.createElement('div');
          dDetail.className = 'text-slate-600';
          dDetail.textContent = d.detail;
          dItem.appendChild(dHead);
          dItem.appendChild(dDetail);
          drvContainer.appendChild(dItem);
        });
        cardTop.appendChild(drvContainer);
      }

      card.appendChild(cardTop);
      compGrid.appendChild(card);
    }
    container.appendChild(compGrid);

    // Recommendations Section
    if (data.recommendations) {
      const recCard = document.createElement('div');
      recCard.className = 'bg-white rounded-3xl border border-slate-200 p-6 sm:p-8 shadow-sm';
      const recHeader = document.createElement('div');
      recHeader.className = 'mb-4';
      const recTitle = document.createElement('h2');
      recTitle.className = 'text-xl font-bold font-display text-slate-900';
      recTitle.textContent = 'Clinical Recommendations & Actions';
      const recHeadline = document.createElement('p');
      recHeadline.className = 'text-sm text-slate-600 mt-1';
      recHeadline.textContent = data.recommendations.headline;
      recHeader.appendChild(recTitle);
      recHeader.appendChild(recHeadline);
      recCard.appendChild(recHeader);

      const stepList = document.createElement('div');
      stepList.className = 'space-y-3';
      data.recommendations.steps.forEach(step => {
        const item = document.createElement('div');
        item.className = 'bg-slate-50 rounded-2xl p-4 border border-slate-100 text-sm';
        const itemTitle = document.createElement('div');
        itemTitle.className = 'font-bold text-slate-800 mb-1';
        itemTitle.textContent = step.title;
        const itemDesc = document.createElement('div');
        itemDesc.className = 'text-slate-600 leading-relaxed';
        itemDesc.textContent = step.description;
        item.appendChild(itemTitle);
        item.appendChild(itemDesc);
        stepList.appendChild(item);
      });
      recCard.appendChild(stepList);
      container.appendChild(recCard);
    }

    // Static Medical Disclaimer
    const disc = document.createElement('div');
    disc.className = 'bg-amber-50 border border-amber-200 rounded-2xl p-5 text-xs text-amber-900 leading-relaxed';
    disc.textContent = 'Non-Diagnostic Clinical Screening Notice: DiaBeates is an evidence-aligned health screening tool designed for educational and informational use. Predictions and risk estimates are not medical diagnoses. Consult a licensed physician for clinical diagnosis and therapy.';
    container.appendChild(disc);

    root.appendChild(container);
  }

  function showError(msg) {
    const errorBox = document.getElementById('reportErrorBox');
    const errorText = document.getElementById('reportErrorText');
    const loadingBox = document.getElementById('reportLoadingBox');
    const promptModal = document.getElementById('passphrasePromptModal');

    if (loadingBox) loadingBox.classList.add('hidden');
    if (promptModal) promptModal.classList.add('hidden');
    if (errorBox && errorText) {
      errorText.textContent = msg;
      errorBox.classList.remove('hidden');
    }
  }

  async function processHash() {
    const hash = window.location.hash.substring(1);
    const loadingBox = document.getElementById('reportLoadingBox');
    const promptModal = document.getElementById('passphrasePromptModal');
    const passphraseInput = document.getElementById('reportPassphraseInput');
    const decryptSubmitBtn = document.getElementById('decryptSubmitBtn');

    if (!hash) {
      showError('No report parameter found in URL fragment. Link may be incomplete.');
      return;
    }

    if (hash.startsWith('report=')) {
      if (loadingBox) loadingBox.classList.remove('hidden');
      try {
        const rawBase64 = hash.substring(7);
        const jsonBytes = base64UrlToBytes(rawBase64);
        const jsonStr = bytesToUtf8(jsonBytes);
        const data = JSON.parse(jsonStr);
        validateReportPayload(data);
        if (loadingBox) loadingBox.classList.add('hidden');
        renderReport(data);
      } catch (err) {
        showError('Unable to parse or validate unencrypted report: ' + err.message);
      }
      return;
    }

    if (hash.startsWith('encrypted=')) {
      const payload = hash.substring(10);
      const parts = payload.split('.');
      if (parts.length !== 4 || parts[0] !== 'v1') {
        showError('Malformed encrypted report fragment format. Expected: #encrypted=v1.<salt>.<iv>.<ciphertext>');
        return;
      }

      let saltBytes, ivBytes, ciphertextBytes;
      try {
        saltBytes = base64UrlToBytes(parts[1]);
        ivBytes = base64UrlToBytes(parts[2]);
        ciphertextBytes = base64UrlToBytes(parts[3]);
      } catch (e) {
        showError('Failed to decode base64url components from encrypted report fragment.');
        return;
      }

      // Show passphrase modal
      if (loadingBox) loadingBox.classList.add('hidden');
      if (promptModal) {
        promptModal.classList.remove('hidden');
        if (passphraseInput) passphraseInput.focus();

        const handleDecrypt = async () => {
          const pass = passphraseInput ? passphraseInput.value : '';
          if (!pass) {
            const errEl = document.getElementById('passphraseError');
            if (errEl) {
              errEl.textContent = 'Please enter a passphrase.';
              errEl.classList.remove('hidden');
            }
            return;
          }

          if (decryptSubmitBtn) {
            decryptSubmitBtn.disabled = true;
            decryptSubmitBtn.textContent = 'Decrypting...';
          }

          try {
            const plaintext = await decryptV1(saltBytes, ivBytes, ciphertextBytes, pass);
            const data = JSON.parse(plaintext);
            validateReportPayload(data);
            promptModal.classList.add('hidden');
            renderReport(data);
          } catch (err) {
            const errEl = document.getElementById('passphraseError');
            if (errEl) {
              errEl.textContent = 'Decryption failed. Incorrect passphrase or altered ciphertext.';
              errEl.classList.remove('hidden');
            }
            if (decryptSubmitBtn) {
              decryptSubmitBtn.disabled = false;
              decryptSubmitBtn.textContent = 'Unlock Report';
            }
          }
        };

        if (decryptSubmitBtn) {
          decryptSubmitBtn.addEventListener('click', handleDecrypt);
        }
        if (passphraseInput) {
          passphraseInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') handleDecrypt();
          });
        }
      }
      return;
    }

    showError('Unknown URL fragment format. Expected #report= or #encrypted=');
  }

  window.addEventListener('DOMContentLoaded', processHash);
})();

