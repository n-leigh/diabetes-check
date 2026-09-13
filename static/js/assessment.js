/**
 * assessment.js - DiaBeates assessment form scripts
 * Strict CSP compliant: no inline scripts, event listeners attached via DOM.
 */
(function () {
  'use strict';

  // Stop propagation on tooltip/info icons
  document.querySelectorAll('.js-stop-propagation').forEach((el) => {
    el.addEventListener('click', (e) => e.stopPropagation());
  });

  const modal = document.getElementById('bmiModal');
  const openBtn = document.getElementById('openBmiCalcBtn');
  const closeBtn = document.getElementById('closeBmiModalBtn');
  const cancelBtn = document.getElementById('cancelBmiBtn');
  const applyBtn = document.getElementById('applyBmiBtn');

  const tabMetric = document.getElementById('tabMetric');
  const tabImperial = document.getElementById('tabImperial');
  const panelMetric = document.getElementById('panelMetric');
  const panelImperial = document.getElementById('panelImperial');

  const metricHeight = document.getElementById('bmiMetricHeight');
  const metricWeight = document.getElementById('bmiMetricWeight');
  const impFt = document.getElementById('bmiImpFt');
  const impIn = document.getElementById('bmiImpIn');
  const impLbs = document.getElementById('bmiImpLbs');

  const previewBox = document.getElementById('bmiPreviewBox');
  const previewNum = document.getElementById('bmiPreviewNum');
  const previewCat = document.getElementById('bmiPreviewCategory');
  const errorMsg = document.getElementById('bmiModalError');

  const targetBmiInput = document.getElementById('BMI');

  let currentUnit = 'metric';

  function setTab(unit) {
    currentUnit = unit;
    if (unit === 'metric') {
      tabMetric.setAttribute('aria-selected', 'true');
      tabMetric.classList.add('bg-white', 'text-teal-700', 'shadow-xs');
      tabMetric.classList.remove('text-slate-600');

      tabImperial.setAttribute('aria-selected', 'false');
      tabImperial.classList.remove('bg-white', 'text-teal-700', 'shadow-xs');
      tabImperial.classList.add('text-slate-600');

      panelMetric.classList.remove('hidden');
      panelImperial.classList.add('hidden');
      if (metricHeight) metricHeight.focus();
    } else {
      tabImperial.setAttribute('aria-selected', 'true');
      tabImperial.classList.add('bg-white', 'text-teal-700', 'shadow-xs');
      tabImperial.classList.remove('text-slate-600');

      tabMetric.setAttribute('aria-selected', 'false');
      tabMetric.classList.remove('bg-white', 'text-teal-700', 'shadow-xs');
      tabMetric.classList.add('text-slate-600');

      panelImperial.classList.remove('hidden');
      panelMetric.classList.add('hidden');
      if (impFt) impFt.focus();
    }
    updateCalculation();
  }

  if (tabMetric && tabImperial) {
    tabMetric.addEventListener('click', () => setTab('metric'));
    tabImperial.addEventListener('click', () => setTab('imperial'));
  }

  function calculateBmi() {
    if (currentUnit === 'metric') {
      const h = parseFloat(metricHeight.value);
      const w = parseFloat(metricWeight.value);
      if (!h || h <= 0 || !w || w <= 0) return null;
      const hm = h / 100;
      return w / (hm * hm);
    } else {
      const ft = parseFloat(impFt.value) || 0;
      const inches = parseFloat(impIn.value) || 0;
      const totalIn = ft * 12 + inches;
      const lbs = parseFloat(impLbs.value);
      if (totalIn <= 0 || !lbs || lbs <= 0) return null;
      const hm = totalIn * 0.0254;
      const wkg = lbs * 0.45359237;
      return wkg / (hm * hm);
    }
  }

  function getBmiCategory(bmi) {
    if (bmi < 18.5) return { label: 'Underweight (< 18.5)', color: 'text-amber-600' };
    if (bmi < 25.0) return { label: 'Normal weight (18.5 \u2013 24.9)', color: 'text-teal-600' };
    if (bmi < 30.0) return { label: 'Overweight (25.0 \u2013 29.9)', color: 'text-amber-600' };
    return { label: 'Obese (\u2265 30.0)', color: 'text-rose-600' };
  }

  function updateCalculation() {
    if (!errorMsg || !previewBox || !previewNum || !previewCat) return;
    errorMsg.classList.add('hidden');
    errorMsg.textContent = '';
    const bmi = calculateBmi();
    if (bmi !== null && !isNaN(bmi) && isFinite(bmi) && bmi >= 5 && bmi <= 120) {
      const cat = getBmiCategory(bmi);
      previewNum.textContent = bmi.toFixed(1);
      previewCat.textContent = cat.label;
      previewCat.className = 'text-xs font-semibold ' + cat.color;
      previewBox.classList.remove('hidden');
    } else {
      previewBox.classList.add('hidden');
    }
  }

  [metricHeight, metricWeight, impFt, impIn, impLbs].forEach(input => {
    if (input) {
      input.addEventListener('input', updateCalculation);
    }
  });

  function openModal() {
    if (!modal) return;
    if (typeof modal.showModal === 'function') {
      modal.showModal();
    } else {
      modal.setAttribute('open', '');
    }
    updateCalculation();
    if (currentUnit === 'metric' && metricHeight) {
      metricHeight.focus();
    } else if (impFt) {
      impFt.focus();
    }
  }

  function closeModal() {
    if (!modal) return;
    if (typeof modal.close === 'function') {
      modal.close();
    } else {
      modal.removeAttribute('open');
    }
    if (openBtn) {
      openBtn.focus();
    }
  }

  if (openBtn) openBtn.addEventListener('click', openModal);
  if (closeBtn) closeBtn.addEventListener('click', closeModal);
  if (cancelBtn) cancelBtn.addEventListener('click', closeModal);

  if (modal) {
    modal.addEventListener('click', (event) => {
      if (event.target === modal) {
        closeModal();
      }
    });
    modal.addEventListener('cancel', () => {
      if (openBtn) {
        setTimeout(() => openBtn.focus(), 0);
      }
    });
  }

  if (applyBtn) {
    applyBtn.addEventListener('click', () => {
      const bmi = calculateBmi();
      if (bmi === null || isNaN(bmi) || !isFinite(bmi) || bmi <= 0) {
        if (errorMsg) {
          errorMsg.textContent = 'Please enter valid height and weight values.';
          errorMsg.classList.remove('hidden');
        }
        return;
      }
      if (targetBmiInput) {
        targetBmiInput.value = bmi.toFixed(1);
        targetBmiInput.dispatchEvent(new Event('input', { bubbles: true }));
        targetBmiInput.dispatchEvent(new Event('change', { bubbles: true }));
      }
      closeModal();
      if (targetBmiInput) {
        targetBmiInput.focus();
      }
    });
  }

  function setupThirtyDayLimitWarning(inputId, warningId, capBtnId) {
    const input = document.getElementById(inputId);
    const warning = document.getElementById(warningId);
    const capBtn = document.getElementById(capBtnId);
    if (!input || !warning) return;

    function checkValue() {
      const raw = input.value.trim();
      const val = parseFloat(raw);
      if (raw !== '' && !isNaN(val) && val > 30) {
        warning.classList.remove('hidden');
        input.classList.add('border-amber-400', 'ring-2', 'ring-amber-400/50');
      } else {
        warning.classList.add('hidden');
        input.classList.remove('border-amber-400', 'ring-2', 'ring-amber-400/50');
      }
    }

    input.addEventListener('input', checkValue);
    input.addEventListener('change', checkValue);

    if (capBtn) {
      capBtn.addEventListener('click', () => {
        input.value = 30;
        checkValue();
        input.focus();
      });
    }

    checkValue();
  }

  setupThirtyDayLimitWarning('PhysHlth', 'physhlth-warning', 'capPhysHlthBtn');
  setupThirtyDayLimitWarning('MentHlth', 'menthlth-warning', 'capMentHlthBtn');
})();

