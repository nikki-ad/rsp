(() => {
  const form = document.querySelector('[data-preview-url]');
  const csrf = form.querySelector('[name=csrfmiddlewaretoken]').value;
  document.querySelectorAll('.exam-editor').forEach(input => {
    const toolbar = document.createElement('div'); toolbar.className = 'exam-toolbar';
    const preview = document.createElement('div'); preview.className = 'exam-preview';
    const actions = [
      ['پررنگ', '**متن**'], ['مورب', '__متن__'], ['کسر', '\\(\\frac{1}{2}\\)'],
      ['توان', '\\(x^{2}\\)'], ['رادیکال', '\\(\\sqrt{x}\\)'],
      ['فرمول', '\\(x + y = 3\\)'], ['فهرست', '\n• متن\n• متن']
    ];
    actions.forEach(([label, snippet]) => {
      const button = document.createElement('button'); button.type = 'button'; button.textContent = label;
      button.addEventListener('click', () => {
        const selected = input.value.slice(input.selectionStart, input.selectionEnd);
        let value = snippet;
        if (selected && (label === 'پررنگ' || label === 'مورب')) value = snippet.replace('متن', selected);
        input.setRangeText(value, input.selectionStart, input.selectionEnd, 'select'); input.focus();
      }); toolbar.append(button);
    });
    const render = document.createElement('button'); render.type = 'button'; render.textContent = 'پیش‌نمایش';
    render.addEventListener('click', async () => {
      render.disabled = true;
      try {
        const response = await fetch(form.dataset.previewUrl, {method: 'POST',
          headers: {'X-CSRFToken': csrf, 'Content-Type': 'application/json'},
          body: JSON.stringify({text: input.value})});
        if (!response.ok) throw new Error();
        // Only server-escaped text and whitelisted native MathML enter this preview.
        preview.innerHTML = (await response.json()).html;
      } catch { preview.textContent = 'پیش‌نمایش دریافت نشد. دوباره تلاش کنید.'; }
      finally { render.disabled = false; }
    }); toolbar.append(render); input.before(toolbar); input.after(preview);
  });
})();
