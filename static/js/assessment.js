/**
 * assessment.js - DiaBeates 3-step wizard and BMI calculator
 * Strict CSP compliant: no inline scripts, no inline event handlers.
 */
document.addEventListener('DOMContentLoaded', () => {
  'use strict';

  // 1. Wizard Step Navigation Logic
  let currentStep = 1;

  function updateProgressBar(step) {
    const bar = document.getElementById('stepProgressBar');
    const label = document.getElementById('stepProgressLabel');
    const pct = document.getElementById('stepPercentLabel');
    if (!bar || !label || !pct) return;

    if (step === 1) {
      bar.style.width = '33.33%';
      label.textContent = 'Step 1 of 3: About you';
      pct.textContent = '33%';
    } else if (step === 2) {
      bar.style.width = '66.66%';
      label.textContent = 'Step 2 of 3: Your health';
      pct.textContent = '66%';
    } else if (step === 3) {
      bar.style.width = '100%';
      label.textContent = 'Step 3 of 3: Lab results (optional)';
      pct.textContent = '100%';
    }
  }

  function goToStep(step) {
    const alertBox = document.getElementById('stepAlert');
    if (alertBox) alertBox.classList.add('hidden');

    const s1 = document.getElementById('step1Container');
    const s2 = document.getElementById('step2Container');
    const s3 = document.getElementById('step3Container');

    if (s1) s1.classList.toggle('hidden', step !== 1);
    if (s2) s2.classList.toggle('hidden', step !== 2);
    if (s3) s3.classList.toggle('hidden', step !== 3);
    currentStep = step;
    updateProgressBar(step);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  function showError(msg) {
    const alertBox = document.getElementById('stepAlert');
    if (alertBox) {
      alertBox.textContent = msg;
      alertBox.classList.remove('hidden');
      alertBox.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }

  function nextStep(fromStep) {
    const alertBox = document.getElementById('stepAlert');
    if (alertBox) {
      alertBox.classList.add('hidden');
      alertBox.textContent = '';
    }

    if (fromStep === 1) {
      const age = document.getElementById('Age');
      const sex = document.getElementById('Sex');
      const bmi = document.getElementById('BMI');
      const genHlth = document.getElementById('GenHlth');

      if (!age || !age.value) {
        showError('Please choose your age.');
        if (age) age.focus();
        return;
      }
      if (!sex || sex.value === '') {
        showError('Please select your sex assigned at birth.');
        if (sex) sex.focus();
        return;
      }
      if (!bmi || !bmi.value || parseFloat(bmi.value) <= 0) {
        showError('Please enter your BMI or tap "Don\'t know your BMI?" to calculate it.');
        if (bmi) bmi.focus();
        return;
      }
      if (!genHlth || !genHlth.value) {
        showError('Please rate your general health.');
        if (genHlth) genHlth.focus();
        return;
      }
      goToStep(2);
    }
  }

  // Hook step navigation buttons
  const step1NextBtn = document.getElementById('step1NextBtn');
  if (step1NextBtn) {
    step1NextBtn.addEventListener('click', () => nextStep(1));
  }

  const step2BackBtn = document.getElementById('step2BackBtn');
  if (step2BackBtn) {
    step2BackBtn.addEventListener('click', () => goToStep(1));
  }

  const step2NextBtn = document.getElementById('step2NextBtn');
  if (step2NextBtn) {
    step2NextBtn.addEventListener('click', () => goToStep(3));
  }

  const step3BackBtn = document.getElementById('step3BackBtn');
  if (step3BackBtn) {
    step3BackBtn.addEventListener('click', () => goToStep(2));
  }

  // 2. Choice Tile Toggle Handler
  function updateTile(checkbox) {
    const tile = checkbox.closest('.choice-tile');
    if (!tile) return;
    const checkIcon = tile.querySelector('.check-icon');
    if (checkbox.checked) {
      tile.classList.add('is-selected');
      if (checkIcon) checkIcon.classList.remove('hidden');
    } else {
      tile.classList.remove('is-selected');
      if (checkIcon) checkIcon.classList.add('hidden');
    }
  }

  document.querySelectorAll('.choice-tile input[type="checkbox"]').forEach(cb => {
    updateTile(cb);
    cb.addEventListener('change', () => updateTile(cb));
  });

  // Slider displays
  const physHlth = document.getElementById('PhysHlth');
  const physDisplay = document.getElementById('physHlthValDisplay');
  if (physHlth && physDisplay) {
    physHlth.addEventListener('input', () => {
      physDisplay.textContent = physHlth.value + ' days';
    });
  }

  const mentHlth = document.getElementById('MentHlth');
  const mentDisplay = document.getElementById('mentHlthValDisplay');
  if (mentHlth && mentDisplay) {
    mentHlth.addEventListener('input', () => {
      mentDisplay.textContent = mentHlth.value + ' days';
    });
  }

  // 3. Labs Collapsible Toggle Handler
  const hasLabsToggle = document.getElementById('hasLabsToggle');
  const labsPanel = document.getElementById('labsInputsPanel');
  if (hasLabsToggle && labsPanel) {
    hasLabsToggle.addEventListener('change', () => {
      labsPanel.classList.toggle('hidden', !hasLabsToggle.checked);
    });

    const preHbA1c = document.getElementById('LabHbA1c');
    const preBP = document.getElementById('LabSystolicBP');
    const preLDL = document.getElementById('LabLDL');
    if ((preHbA1c && preHbA1c.value.trim() !== '') ||
        (preBP && preBP.value.trim() !== '') ||
        (preLDL && preLDL.value.trim() !== '')) {
      hasLabsToggle.checked = true;
      labsPanel.classList.remove('hidden');
    }
  }

  // 4. BMI Modal & Live Calculator Logic
  (function initBmi() {
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
    const onPageCat = document.getElementById('onPageBmiCategory');

    function updateHeightInputs() {
      if (!heightUnit) return;
      const usesFtIn = heightUnit.value === 'ftin';
      if (cmHeightGroup) cmHeightGroup.classList.toggle('hidden', usesFtIn);
      if (feetInchesGroup) feetInchesGroup.classList.toggle('hidden', !usesFtIn);
      updateCalculation();
      if (usesFtIn && heightFt) heightFt.focus();
      else if (heightCm) heightCm.focus();
    }

    if (heightUnit) heightUnit.addEventListener('change', updateHeightInputs);
    if (weightUnit) weightUnit.addEventListener('change', updateCalculation);

    function calculateBmi() {
      if (!heightUnit || !weightUnit || !weight) return null;
      let heightMeters;
      if (heightUnit.value === 'cm') {
        const cm = parseFloat(heightCm ? heightCm.value : 0);
        if (!cm || cm <= 0) return null;
        heightMeters = cm / 100;
      } else {
        const ft = parseFloat(heightFt ? heightFt.value : 0) || 0;
        const inches = parseFloat(heightIn ? heightIn.value : 0) || 0;
        const totalIn = ft * 12 + inches;
        if (totalIn <= 0) return null;
        heightMeters = totalIn * 0.0254;
      }

      const rawWeight = parseFloat(weight.value);
      if (!rawWeight || rawWeight <= 0) return null;
      const weightKg = weightUnit.value === 'lbs' ? rawWeight * 0.45359237 : rawWeight;
      return weightKg / (heightMeters * heightMeters);
    }

    function getBmiCategory(bmi) {
      if (bmi < 18.5) return { label: 'Underweight (< 18.5)', color: 'text-[#a86a0a]' };
      if (bmi < 25.0) return { label: 'Normal weight (18.5 – 24.9)', color: 'text-[#2f7d4a]' };
      if (bmi < 30.0) return { label: 'Overweight (25.0 – 29.9)', color: 'text-[#a86a0a]' };
      return { label: 'Above ideal weight (≥ 30.0)', color: 'text-[#b03a2e]' };
    }

    function updateCalculation() {
      if (errorMsg) {
        errorMsg.classList.add('hidden');
        errorMsg.textContent = '';
      }
      const bmi = calculateBmi();
      if (previewBox && previewNum && previewCat) {
        if (bmi !== null && !isNaN(bmi) && isFinite(bmi) && bmi >= 5 && bmi <= 120) {
          const cat = getBmiCategory(bmi);
          previewNum.textContent = bmi.toFixed(1);
          previewCat.textContent = cat.label;
          previewCat.className = 'text-[15px] font-bold ' + cat.color;
          previewBox.classList.remove('hidden');
        } else {
          previewBox.classList.add('hidden');
        }
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
      if (heightUnit && heightUnit.value === 'cm' && heightCm) {
        heightCm.focus();
      } else if (heightFt) {
        heightFt.focus();
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
        if (bmi === null || isNaN(bmi) || !isFinite(bmi) || bmi < 10 || bmi > 80) {
          if (errorMsg) {
            errorMsg.textContent = 'Please enter valid height and weight values to get a BMI between 10 and 80.';
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

    // On-page BMI category indicator
    function updateOnPageCategory() {
      if (!onPageCat || !targetBmiInput) return;
      const val = parseFloat(targetBmiInput.value);
      if (!isNaN(val) && val >= 10 && val <= 80) {
        const cat = getBmiCategory(val);
        onPageCat.textContent = '(' + cat.label + ')';
        onPageCat.className = 'text-[16px] font-bold ' + cat.color;
      } else {
        onPageCat.textContent = '';
      }
    }

    if (targetBmiInput) {
      targetBmiInput.addEventListener('input', updateOnPageCategory);
      targetBmiInput.addEventListener('change', updateOnPageCategory);
      updateOnPageCategory();
    }

    // 30-Day Limit Warnings
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

  // 5. Submit Button Loading State
  const assessmentForm = document.getElementById('assessmentForm');
  const submitBtn = document.getElementById('submitBtn');
  if (assessmentForm && submitBtn) {
    assessmentForm.addEventListener('submit', function () {
      submitBtn.disabled = true;
      submitBtn.textContent = 'Checking your results...';
      submitBtn.classList.add('opacity-75');
    });
  }
});
