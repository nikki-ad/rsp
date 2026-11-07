(() => {
  const groups = [...document.querySelectorAll('[data-group]')];
  const students = [...document.querySelectorAll('input[name="students"]')];
  function refresh() {
    for (const group of groups) {
      const items = [...group.querySelectorAll('input[name="students"]')];
      const checked = items.filter(i => i.checked).length;
      const toggle = group.querySelector('[data-select-group]');
      toggle.checked = items.length > 0 && checked === items.length;
      toggle.indeterminate = checked > 0 && checked < items.length;
    }
    document.getElementById('selected-count').textContent =
      `تعداد انتخاب‌شده: ${new Set(students.filter(i => i.checked).map(i => i.value)).size}`;
  }
  function sync(value, checked) {
    students.filter(i => i.value === value).forEach(i => { i.checked = checked; });
  }
  groups.forEach(group => group.querySelector('[data-select-group]').addEventListener('change', event => {
    group.querySelectorAll('input[name="students"]').forEach(i => sync(i.value, event.target.checked));
    refresh();
  }));
  students.forEach(i => i.addEventListener('change', () => { sync(i.value, i.checked); refresh(); }));
  document.getElementById('student-search')?.addEventListener('input', event => {
    const term = event.target.value.trim();
    groups.forEach(group => {
      const groupMatch = group.querySelector('summary').textContent.includes(term);
      const labels = [...group.querySelectorAll('[data-student-label]')];
      labels.forEach(label => { label.hidden = !!term && !groupMatch && !label.textContent.includes(term); });
      group.hidden = !!term && labels.every(label => label.hidden);
      if (term && !group.hidden) group.querySelector('details').open = true;
    });
  });
  const mode = document.getElementById('id_mode');
  const pdf = document.getElementById('id_question_pdf');
  function togglePDF() { if (pdf) pdf.closest('.exam-field').hidden = mode.value !== 'pdf'; }
  mode?.addEventListener('change', togglePDF);
  togglePDF(); refresh();
})();
