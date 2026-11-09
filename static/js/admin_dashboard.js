document.addEventListener('DOMContentLoaded', () => {
  const chart = document.querySelector('.admin-chart-figure');
  const tooltip = document.getElementById('adminChartTooltip');
  if (!chart || !tooltip) return;

  const date = tooltip.querySelector('.admin-chart-tooltip-date');
  const value = tooltip.querySelector('.admin-chart-tooltip-value');
  const note = tooltip.querySelector('.admin-chart-tooltip-note');
  const bars = chart.querySelectorAll('.admin-chart-bar-group');

  const hideTooltip = () => {
    tooltip.classList.remove('is-visible');
    tooltip.setAttribute('aria-hidden', 'true');
  };

  const showTooltip = (bar) => {
    const barBounds = bar.getBoundingClientRect();
    const chartBounds = chart.getBoundingClientRect();
    date.textContent = bar.dataset.tooltipDate || '';
    value.textContent = bar.dataset.tooltipValue || '';
    note.textContent = bar.dataset.tooltipNote || '';
    note.hidden = !bar.dataset.tooltipNote;
    tooltip.style.left = `${barBounds.left - chartBounds.left + (barBounds.width / 2)}px`;
    tooltip.style.top = `${barBounds.top - chartBounds.top}px`;
    tooltip.classList.add('is-visible');
    tooltip.setAttribute('aria-hidden', 'false');
  };

  bars.forEach((bar) => {
    bar.addEventListener('mouseenter', () => showTooltip(bar));
    bar.addEventListener('mouseleave', hideTooltip);
    bar.addEventListener('focus', () => showTooltip(bar));
    bar.addEventListener('blur', hideTooltip);
  });

  window.addEventListener('resize', hideTooltip);
});
