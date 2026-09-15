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

  const heightUnit = document.getElementById('bmiHeightUnit');
  const weightUnit = document.getElementById('bmiWeightUnit');
  const cmHeightGroup = document.getElementById('bmiCmHeightGroup');
  const feetInchesGroup = document.getElementById('bmiFeetInchesGroup');
  const heightCm = document.getElementById('bmiHeightCm');
  const heightFt = document.getElementById('bmiHeightFt');
  const heightIn = document.getElementById('bmiHeightIn');
  const weight = document.getElementById('bmiWeight');

  const previewBox = document.getElementById('bmiPreviewBox');
  const previewNum = document.getElementById('bmiPreviewNum');
  const previewCat = document.getElementById('bmiPreviewCategory');
  const errorMsg = document.getElementById('bmiModalError');

  const targetBmiInput = document.getElementById('BMI');

  function updateHeightInputs() {
    const usesFeetAndInches = heightUnit.value === 'ftin';
    cmHeightGroup.classList.toggle('hidden', usesFeetAndInches);
    feetInchesGroup.classList.toggle('hidden', !usesFeetAndInches);
    updateCalculation();
    if (usesFeetAndInches) heightFt.focus();
    else heightCm.focus();
  }

  if (heightUnit) heightUnit.addEventListener('change', updateHeightInputs);
  if (weightUnit) weightUnit.addEventListener('change', updateCalculation);

  function calculateBmi() {
    let heightMeters;
    if (heightUnit.value === 'cm') {
      const centimeters = parseFloat(heightCm.value);
      if (!centimeters || centimeters <= 0) return null;
      heightMeters = centimeters / 100;
    } else {
      const feet = parseFloat(heightFt.value) || 0;
      const inches = parseFloat(heightIn.value) || 0;
      const totalInches = feet * 12 + inches;
      if (totalInches <= 0) return null;
      heightMeters = totalInches * 0.0254;
    }

    const enteredWeight = parseFloat(weight.value);
    if (!enteredWeight || enteredWeight <= 0) return null;
    const weightKg = weightUnit.value === 'lbs' ? enteredWeight * 0.45359237 : enteredWeight;
    return weightKg / (heightMeters * heightMeters);
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

  [heightCm, heightFt, heightIn, weight].forEach(input => {
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
    if (heightUnit.value === 'cm' && heightCm) heightCm.focus();
    else if (heightFt) heightFt.focus();
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

