(() => {
  'use strict';
  const form = document.querySelector('.deficiency-form');
  if (!form) return;
  const boxes = [...form.querySelectorAll('input[name="students"]')];
  const all = document.getElementById('select-all-students');
  const count = document.getElementById('selected-student-count');
  const update = () => {
    const selected = boxes.filter(box => box.checked).length;
    if (count) count.textContent = `${selected.toLocaleString('fa-IR')} نفر انتخاب شده`;
    if (all) { all.checked = boxes.length > 0 && selected === boxes.length; all.indeterminate = selected > 0 && selected < boxes.length; }
  };
  if (all) all.addEventListener('change', () => { boxes.forEach(box => { box.checked = all.checked; }); update(); });
  boxes.forEach(box => box.addEventListener('change', update));
  update();
  const input = document.getElementById('id_record_date');
  const popup = document.getElementById('deficiency-calendar');
  const toggle = document.getElementById('calendar-toggle');
  const grid = document.getElementById('calendar-days');
  const error = document.getElementById('calendar-error');
  const months = ['فروردین','اردیبهشت','خرداد','تیر','مرداد','شهریور','مهر','آبان','آذر','دی','بهمن','اسفند'];
  let shown = null, requestId = 0;
  const digits = value => value.replace(/[۰-۹٠-٩]/g, c => '۰۱۲۳۴۵۶۷۸۹'.includes(c) ? '۰۱۲۳۴۵۶۷۸۹'.indexOf(c) : '٠١٢٣٤٥٦٧٨٩'.indexOf(c));
  const dateValue = (y,m,d) => `${y}/${String(m).padStart(2,'0')}/${String(d).padStart(2,'0')}`;
  const close = () => { popup.hidden = true; toggle.setAttribute('aria-expanded','false'); };
  async function load(year, month) {
    const id = ++requestId;
    error.textContent = '';
    try {
      const url = new URL(popup.dataset.url, location.origin);
      if (year && month) { url.searchParams.set('year',year); url.searchParams.set('month',month); }
      const response = await fetch(url, {headers:{'Accept':'application/json'}});
      if (!response.ok) throw new Error('calendar');
      const data = await response.json();
      if (id !== requestId) return;
      shown = data;
      document.getElementById('calendar-title').textContent = `${months[data.month-1]} ${data.year.toLocaleString('fa-IR',{useGrouping:false})}`;
      grid.replaceChildren();
      for (let i=0; i<data.offset; i++) grid.append(document.createElement('span'));
      for (let day=1; day<=data.days; day++) {
        const button = document.createElement('button');
        const value = dateValue(data.year,data.month,day);
        button.type='button'; button.textContent=day.toLocaleString('fa-IR');
        button.setAttribute('aria-label',`${day} ${months[data.month-1]} ${data.year}`);
        button.setAttribute('aria-pressed', String(value === digits(input.value)));
        button.dataset.today=String(value === data.today);
        button.addEventListener('click', () => { input.value=value; input.dispatchEvent(new Event('change',{bubbles:true})); close(); toggle.focus(); });
        grid.append(button);
      }
      return data;
    } catch (_) { if(id === requestId) error.textContent='تقویم بارگیری نشد. می‌توانید تاریخ را دستی وارد کنید.'; return null; }
  }
  toggle.addEventListener('click', () => {
    if (!popup.hidden) { close(); return; }
    popup.hidden=false; toggle.setAttribute('aria-expanded','true');
    const parts=digits(input.value).trim().split(/[/-]/).map(Number);
    load(parts[0] >= 1200 && parts[0] <= 1600 ? parts[0] : null, parts[1]);
  });
  popup.querySelectorAll('[data-month-step]').forEach(button => button.addEventListener('click', () => {
    if (!shown) return;
    let year=shown.year, month=shown.month + Number(button.dataset.monthStep);
    if(month===0) { month=12; year--; } if(month===13) { month=1; year++; }
    load(year,month);
  }));
  document.getElementById('calendar-today').addEventListener('click', async () => { const data=await load(); if(data) { input.value=data.today; input.dispatchEvent(new Event('change',{bubbles:true})); close(); toggle.focus(); } });
  document.addEventListener('click', event => { if(!popup.contains(event.target) && !toggle.contains(event.target)) close(); });
  document.addEventListener('keydown', event => { if(event.key==='Escape' && !popup.hidden) { close(); toggle.focus(); } });
})();
