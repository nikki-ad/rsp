document.addEventListener('DOMContentLoaded', () => {
    const source = document.getElementById('report-student-choices');
    const input = document.getElementById('id_student_search');
    const selected = document.getElementById('id_student');
    if (!source || !input || !selected) return;
    const students = JSON.parse(source.textContent);
    const list = document.createElement('div');
    list.id = 'report-student-results';
    list.setAttribute('role', 'listbox');
    list.style.cssText = 'max-height:260px;overflow-y:auto;display:none;border:1px solid #aaa;border-radius:8px;padding:8px';
    input.after(list);
    const status = document.createElement('small');
    status.setAttribute('aria-live', 'polite');
    list.after(status);
    input.setAttribute('role', 'combobox');
    input.setAttribute('aria-autocomplete', 'list');
    input.setAttribute('aria-controls', list.id);
    input.setAttribute('aria-expanded', 'false');
    const normalize = value => value.toLocaleLowerCase('fa').replace(/ي|ى/g, 'ی').replace(/ك/g, 'ک').replace(/[\u064B-\u065F\u0670\u200c\u200f]/g, '').replace(/\s+/g, ' ').trim();
    let active = -1;
    let matches = [];
    function close() {
        list.style.display = 'none';
        input.setAttribute('aria-expanded', 'false');
        input.removeAttribute('aria-activedescendant');
        active = -1;
    }
    function choose(student) {
        selected.value = student.id;
        input.value = student.label;
        status.textContent = 'انتخاب شد: ' + student.label;
        close();
    }
    const initial = students.find(student => student.id === selected.value);
    if (initial) choose(initial);
    function search() {
        const terms = normalize(input.value).split(' ').filter(Boolean);
        matches = terms.length ? students.filter(student => terms.every(term => normalize(student.label).includes(term))) : [];
        list.replaceChildren();
        active = -1;
        input.removeAttribute('aria-activedescendant');
        status.textContent = matches.length ? matches.length + ' نتیجه؛ برای انتخاب روی نام بزنید.' : (terms.length ? 'دانش‌آموزی پیدا نشد.' : 'نام دانش‌آموز را بنویسید.');
        matches.slice(0, 30).forEach((student, index) => {
            const option = document.createElement('button');
            option.type = 'button';
            option.id = 'report-student-option-' + index;
            option.setAttribute('role', 'option');
            option.setAttribute('aria-selected', 'false');
            option.style.cssText = 'display:block;width:100%;text-align:start;padding:10px;margin:3px 0;white-space:normal';
            option.textContent = student.label;
            option.addEventListener('click', () => choose(student));
            list.append(option);
        });
        if (matches.length > 30) status.textContent += ' ۳۰ نتیجه اول نمایش داده می‌شود؛ نام را کامل‌تر بنویسید.';
        list.style.display = matches.length ? 'block' : 'none';
        input.setAttribute('aria-expanded', matches.length ? 'true' : 'false');
    }
    input.addEventListener('input', () => { selected.value = ''; search(); });
    input.addEventListener('focus', () => { if (!selected.value) search(); });
    input.addEventListener('keydown', event => {
        const options = [...list.children];
        if (event.key === 'Escape') { close(); return; }
        if (event.key === 'Enter') {
            if (active >= 0 && list.style.display !== 'none') { event.preventDefault(); choose(matches[active]); }
            else if (!selected.value) event.preventDefault();
            return;
        }
        if (!['ArrowDown', 'ArrowUp'].includes(event.key) || !options.length) return;
        event.preventDefault();
        active = (active + (event.key === 'ArrowDown' ? 1 : -1) + options.length) % options.length;
        options.forEach((option, index) => {
            option.setAttribute('aria-selected', String(index === active));
            option.style.outline = index === active ? '2px solid #376ac2' : '';
        });
        input.setAttribute('aria-activedescendant', options[active].id);
        options[active].scrollIntoView({block: 'nearest'});
    });
    document.addEventListener('click', event => { if (event.target !== input && !list.contains(event.target)) close(); });
    input.form.addEventListener('submit', event => {
        if (!selected.value) { event.preventDefault(); status.textContent = 'دانش‌آموز را از نتایج جست‌وجو انتخاب کنید.'; input.focus(); }
    });
});
