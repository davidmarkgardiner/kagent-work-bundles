(() => {
  const controls = document.querySelector('.delivery-controls');
  if (!controls) return;
  const items = [...document.querySelectorAll('.calendar-item')];
  const buttons = [...controls.querySelectorAll('[data-quarter-filter]')];
  const status = document.querySelector('#delivery-status');
  const track = document.querySelector('#delivery-track');
  const result = document.querySelector('.delivery-filter-result');
  const empty = document.querySelector('.delivery-empty');
  const scroller = document.querySelector('.calendar-scroll');
  let quarter = 'all';
  let printing = false;
  function apply() {
    let count = 0;
    items.forEach(item => {
      const cell = item.closest('[data-quarter]');
      item.hidden = !printing && !((quarter === 'all' || cell.dataset.quarter === quarter) && (status.value === 'all' || item.dataset.state === status.value) && (track.value === 'all' || item.dataset.track === track.value));
      if (!item.hidden) count++;
    });
    document.querySelectorAll('[data-quarter]').forEach(cell => { cell.hidden = !printing && quarter !== 'all' && cell.dataset.quarter !== quarter; });
    document.querySelectorAll('[data-quarter-head]').forEach(cell => { cell.hidden = !printing && quarter !== 'all' && cell.dataset.quarterHead !== quarter; });
    document.querySelectorAll('[data-track-row]').forEach(row => { row.hidden = !printing && track.value !== 'all' && row.dataset.trackRow !== track.value; });
    buttons.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.quarterFilter === quarter)));
    result.textContent = `Showing ${count} of ${items.length} outcomes`;
    empty.hidden = count !== 0;
  }
  buttons.forEach(button => button.addEventListener('click', () => { quarter = button.dataset.quarterFilter; apply(); scroller.scrollLeft = 0; }));
  status.addEventListener('change', apply);
  track.addEventListener('change', apply);
  document.querySelectorAll('[data-scroll]').forEach(button => button.addEventListener('click', () => { scroller.scrollBy({left: Number(button.dataset.scroll) * Math.max(180, scroller.clientWidth * .7), behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth'}); }));
  controls.hidden = false;
  document.querySelector('.calendar-navigation').hidden = false;
  apply();
  let opened = [];
  addEventListener('beforeprint', () => { printing = true; apply(); opened = [...document.querySelectorAll('details')].filter(item => !item.open); opened.forEach(item => { item.open = true; }); });
  addEventListener('afterprint', () => { opened.forEach(item => { item.open = false; }); printing = false; apply(); });
})();
