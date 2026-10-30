/* Class checkboxes are UI shortcuts; only the final student IDs are submitted. */
document.addEventListener('DOMContentLoaded', () => {
    const source = document.getElementById('online-class-groups');
    const year = document.getElementById('id_academic_year');
    const original = document.getElementById('id_students');
    if (!source || !year || !original) return;
    const selected = new Set(Array.from(original.querySelectorAll('input:checked'), el => el.value));
    const container = document.createElement('div');
    container.id = 'id_students';
    original.replaceWith(container);
    const search = document.createElement('input');
    search.type = 'search';
    search.placeholder = 'جستجوی نام دانش‌آموز یا کلاس';
    search.setAttribute('aria-label', search.placeholder);
    container.before(search);
    const status = document.createElement('p');
    status.setAttribute('role', 'status');
    container.before(status);
    const endpoint = document.getElementById('online-class-endpoint').dataset.url;
    const submit = container.closest('form').querySelector('button[type="submit"]');
    let sequence = 0;

    function render(groups, checked) {
        container.replaceChildren();
        const syncGroups = [];
        function syncSelection(changed) {
            container.querySelectorAll('input[name="students"]').forEach(input => {
                if (input.value === changed.value) input.checked = changed.checked;
            });
        }
        groups.forEach(group => {
            const details = document.createElement('details');
            details.style.cssText = 'margin:8px 0;padding:12px;border:1px solid #ddd;border-radius:12px';
            const summary = document.createElement('summary');
            const all = document.createElement('input');
            all.type = 'checkbox';
            all.setAttribute('aria-label', 'انتخاب همه دانش‌آموزان ' + group.name);
            const title = document.createElement('span');
            const list = document.createElement('div');
            list.style.cssText = 'display:grid;gap:8px;margin-top:12px';
            const children = [];
            group.students.forEach(student => {
                const label = document.createElement('label');
                const input = document.createElement('input');
                input.type = 'checkbox';
                input.name = 'students';
                input.value = student.id;
                input.checked = checked.has(student.id);
                label.append(input, document.createTextNode(' ' + student.name));
                list.append(label);
                children.push(input);
            });
            function sync() {
                const count = children.filter(el => el.checked).length;
                all.checked = children.length > 0 && count === children.length;
                all.indeterminate = count > 0 && count < children.length;
                all.disabled = children.length === 0;
                title.textContent = ` ${group.name} — ${count} از ${children.length} نفر`;
            }
            all.addEventListener('click', event => event.stopPropagation());
            all.addEventListener('change', () => {
                const checked = all.checked;
                children.forEach(el => { el.checked = checked; syncSelection(el); });
                syncGroups.forEach(update => update());
            });
            syncGroups.push(sync);
            children.forEach(el => el.addEventListener('change', () => {
                syncSelection(el);
                syncGroups.forEach(update => update());
            }));
            summary.append(all, title);
            details.append(summary, list);
            container.append(details);
            sync();
        });
        filter();
    }
    function filter() {
        const term = search.value.trim().toLocaleLowerCase('fa');
        container.querySelectorAll('details').forEach(details => {
            const groupMatch = details.querySelector('summary span').textContent.toLocaleLowerCase('fa').includes(term);
            let any = false;
            details.querySelectorAll('label').forEach(label => {
                const match = groupMatch || label.textContent.toLocaleLowerCase('fa').includes(term);
                label.hidden = !match;
                any = any || match;
            });
            details.hidden = !groupMatch && !any;
            if (term && any) details.open = true;
        });
    }
    search.addEventListener('input', filter);
    render(JSON.parse(source.textContent), selected);
    year.addEventListener('change', async () => {
        const current = ++sequence;
        container.replaceChildren();
        submit.disabled = true;
        status.textContent = 'در حال دریافت دانش‌آموزان…';
        try {
            if (!year.value) {
                status.textContent = 'سال تحصیلی را انتخاب کنید.';
                submit.disabled = false;
                return;
            }
            const response = await fetch(endpoint + '?academic_year=' + encodeURIComponent(year.value));
            if (!response.ok) throw new Error('load');
            const data = await response.json();
            if (current !== sequence) return;
            render(data.classrooms || [], new Set());
            status.textContent = '';
            submit.disabled = false;
        } catch (error) {
            if (current !== sequence) return;
            status.textContent = 'دریافت دانش‌آموزان ناموفق بود؛ سال تحصیلی را دوباره انتخاب کنید.';
        }
    });
});
