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

  // Form Validation Logic
  const form = document.querySelector('form[action="/predict"]');
  const topErrorBanner = document.getElementById('formTopErrorBanner');
  const closeTopErrorBtn = document.getElementById('closeFormTopErrorBannerBtn');

  if (closeTopErrorBtn && topErrorBanner) {
    closeTopErrorBtn.addEventListener('click', () => {
      topErrorBanner.classList.add('hidden');
      topErrorBanner.classList.remove('flex');
    });
  }

  const validationRules = [
    { id: 'BMI', required: true, min: 10.0, max: 80.0, msg: "Please enter your BMI (10.0 to 80.0)." },
    { id: 'Age', required: true, msg: "Please select your age range." },
    { id: 'GenHlth', required: true, msg: "Please rate your general health." },
    { id: 'Sex', required: true, msg: "Please select your biological sex." },
    { id: 'DiabetesDuration', required: true, msg: "Please select how long you've had diabetes." },
    { id: 'PhysHlth', required: true, min: 0, max: 30, msg: "Please enter days of poor physical health (0 to 30)." },
    { id: 'MentHlth', required: true, min: 0, max: 30, msg: "Please enter days of poor mental health (0 to 30)." },
    { id: 'LabHbA1c', required: false, min: 3.0, max: 20.0, msg: "Please enter a valid HbA1c (3.0 to 20.0)." },
    { id: 'LabSystolicBP', required: false, min: 60, max: 250, msg: "Please enter a valid Systolic BP (60 to 250)." },
    { id: 'LabLDL', required: false, min: 20, max: 400, msg: "Please enter a valid LDL cholesterol (20 to 400)." }
  ];

  function clearErrorState(input, errorEl) {
    input.classList.remove('border-rose-400', 'bg-rose-50/50', 'ring-2', 'ring-rose-400/50', 'border-teal-400');
    input.setAttribute('aria-invalid', 'false');
    if (errorEl) {
      errorEl.textContent = '';
      errorEl.classList.add('hidden');
    }
  }

  function setErrorState(input, errorEl, msg) {
    input.classList.add('border-rose-400', 'bg-rose-50/50');
    input.classList.remove('border-teal-400');
    input.setAttribute('aria-invalid', 'true');
    if (errorEl) {
      errorEl.textContent = msg;
      errorEl.classList.remove('hidden');
    }
  }

  validationRules.forEach(rule => {
    const input = document.getElementById(rule.id);
    if (input) {
      input.addEventListener('input', () => {
        const errorEl = document.getElementById(rule.id.toLowerCase() + '-error');
        clearErrorState(input, errorEl);
      });
      input.addEventListener('change', () => {
        const errorEl = document.getElementById(rule.id.toLowerCase() + '-error');
        clearErrorState(input, errorEl);
      });
    }
  });

  if (form) {
    form.addEventListener('submit', (e) => {
      let isValid = true;
      let firstInvalidInput = null;

      validationRules.forEach(rule => {
        const input = document.getElementById(rule.id);
        if (!input) return;
        const errorEl = document.getElementById(rule.id.toLowerCase() + '-error');
        
        let val = input.value.trim();
        let hasError = false;

        if (val === '') {
          if (rule.required) {
            hasError = true;
          }
        } else {
          let numVal = parseFloat(val);
          if (isNaN(numVal)) {
            hasError = true;
          } else if (rule.min !== undefined && numVal < rule.min) {
            hasError = true;
          } else if (rule.max !== undefined && numVal > rule.max) {
            hasError = true;
          }
        }

        if (hasError) {
          setErrorState(input, errorEl, rule.msg);
          isValid = false;
          if (!firstInvalidInput) {
            firstInvalidInput = input;
          }
        } else {
          clearErrorState(input, errorEl);
        }
      });

      if (!isValid) {
        e.preventDefault();
        if (topErrorBanner) {
          topErrorBanner.classList.remove('hidden');
          topErrorBanner.classList.add('flex');
        }
        if (firstInvalidInput) {
          firstInvalidInput.scrollIntoView({ behavior: 'smooth', block: 'center' });
          firstInvalidInput.focus({ preventScroll: true });
        }
      }
    });
  }

})();
