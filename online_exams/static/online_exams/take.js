(() => {
  const form = document.getElementById('answer-form');
  const config = JSON.parse(document.getElementById('exam-config').textContent);
  const csrf = form.querySelector('[name=csrfmiddlewaretoken]').value;
  const status = document.getElementById('save-status');
  const button = document.getElementById('submit-exam');
  const timer = document.getElementById('exam-timer');
  const pending = new Map();
  const storageKey = 'rsp-exam-pending-' + config.participation;
  let clock = Date.parse(config.serverNow), measuredAt = performance.now();
  const deadline = Date.parse(config.deadline);
  let sending = false, retry = null, finished = false, submitting = false;
  const now = () => clock + performance.now() - measuredAt;
  function persist() {
    try { sessionStorage.setItem(storageKey, JSON.stringify([...pending])); } catch { /* storage may be disabled */ }
  }
  try {
    for (const [number, choice] of JSON.parse(sessionStorage.getItem(storageKey) || '[]')) {
      if (!Number.isInteger(number) || !form.querySelector(`[data-question="${number}"]`)) continue;
      if (choice !== null && ![1, 2, 3, 4].includes(choice)) continue;
      pending.set(number, choice);
      form.querySelectorAll(`[name=q${number}]`).forEach(i => { i.checked = Number(i.value) === choice; });
    }
  } catch { /* malformed local data is ignored */ }
  function finish() {
    if (finished) return;
    finished = true;
    form.querySelectorAll('input[type=radio], [data-clear]').forEach(i => { i.disabled = true; });
    try { sessionStorage.removeItem(storageKey); } catch { /* storage may be disabled */ }
    status.textContent = 'آزمون پایان یافت؛ پاسخ‌های ذخیره‌شده تصحیح می‌شوند.';
    window.location.replace(form.dataset.resultUrl);
  }
  async function flush() {
    if (sending || finished) return;
    clearTimeout(retry); sending = true;
    try {
      while (pending.size && !finished) {
        const [number, choice] = pending.entries().next().value;
        status.textContent = `در حال ذخیره… (${pending.size} پاسخ)`;
        const response = await fetch(form.dataset.saveUrl, {method: 'POST',
          headers: {'X-CSRFToken': csrf, 'Content-Type': 'application/json'},
          body: JSON.stringify({number, choice}), signal: AbortSignal.timeout(10000)});
        if (!response.ok) throw new Error();
        const result = await response.json();
        clock = Date.parse(result.serverNow); measuredAt = performance.now();
        if (result.finished) { finish(); return; }
        if (!result.saved) throw new Error();
        if (pending.get(number) === choice) pending.delete(number);
        persist();
      }
      if (!finished) status.textContent = 'همه پاسخ‌ها روی سرور ذخیره شدند ✓';
    } catch {
      status.textContent = 'ذخیره تأیید نشده؛ اتصال را بررسی کنید. تلاش مجدد خودکار انجام می‌شود.';
      if (!finished) retry = setTimeout(flush, 3000);
    } finally { sending = false; }
  }
  function enqueue(fieldset, choice) {
    if (now() >= deadline) { finish(); return; }
    pending.set(Number(fieldset.dataset.question), choice); persist(); flush();
  }
  form.querySelectorAll('[data-question]').forEach(fieldset => {
    fieldset.querySelectorAll('input[type=radio]').forEach(input => input.addEventListener('change', () => {
      enqueue(fieldset, Number(input.value));
    }));
    fieldset.querySelector('[data-clear]').addEventListener('click', () => {
      fieldset.querySelectorAll('input').forEach(i => { i.checked = false; }); enqueue(fieldset, null);
    });
  });
  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (submitting || finished) return;
    if (!window.confirm('آزمون پایان یابد؟ پس از ثبت، تغییر پاسخ‌ها ممکن نیست.')) return;
    submitting = true; button.disabled = true;
    await flush();
    // Another save may already be running. Never submit ahead of it.
    if (sending || pending.size) {
      status.textContent = 'هنوز پاسخ ذخیره‌نشده دارید. پس از ذخیره دوباره پایان آزمون را بزنید.';
      submitting = false; button.disabled = false; return;
    }
    if (!finished) HTMLFormElement.prototype.submit.call(form);
  });
  window.addEventListener('online', flush);
  window.addEventListener('beforeunload', event => {
    if (pending.size && !finished) { event.preventDefault(); event.returnValue = ''; }
  });
  function tick() {
    const seconds = Math.max(0, Math.ceil((deadline - now()) / 1000));
    timer.textContent = `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`;
    if (!seconds) finish();
  }
  tick(); setInterval(tick, 500); if (pending.size) flush();
})();
