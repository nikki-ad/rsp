document.addEventListener('DOMContentLoaded', () => {
    if (!window.XMLHttpRequest || !window.FormData) return;
    const digits = new Intl.NumberFormat('fa-IR', { maximumFractionDigits: 0 });

    document.querySelectorAll('form[data-upload-progress]').forEach(form => {
        let busy = false;
        const panel = document.createElement('section');
        panel.className = 'upload-progress';
        panel.hidden = true;
        panel.innerHTML = `
            <p class="upload-progress__status" role="status" aria-live="polite"></p>
            <div class="upload-progress__track" role="progressbar" aria-label="پیشرفت ارسال"
                 aria-valuemin="0" aria-valuemax="100" aria-valuenow="0">
                <div class="upload-progress__fill"></div>
            </div>
            <span class="upload-progress__percent" aria-hidden="true">۰٪</span>
            <ul class="upload-progress__errors"></ul>`;
        form.appendChild(panel);
        const status = panel.querySelector('.upload-progress__status');
        const bar = panel.querySelector('[role="progressbar"]');
        const fill = panel.querySelector('.upload-progress__fill');
        const percent = panel.querySelector('.upload-progress__percent');
        const errors = panel.querySelector('.upload-progress__errors');
        const leaveWarning = event => {
            event.preventDefault();
            event.returnValue = '';
        };
        const setPercent = value => {
            fill.style.width = value + '%';
            bar.setAttribute('aria-valuenow', value);
            percent.textContent = digits.format(value) + '٪';
        };

        form.addEventListener('submit', event => {
            if (busy) { event.preventDefault(); return; }
            if (event.defaultPrevented || !form.reportValidity()) return;
            event.preventDefault();
            const data = new FormData(form);
            if (event.submitter && event.submitter.name) {
                data.append(event.submitter.name, event.submitter.value);
            }
            const hasFiles = Array.from(form.querySelectorAll('input[type="file"]'))
                .some(input => !input.disabled && input.files.length);
            const controls = Array.from(form.elements).filter(control => !control.disabled);
            const unlock = () => {
                busy = false;
                controls.forEach(control => { control.disabled = false; });
                form.removeAttribute('aria-busy');
                window.removeEventListener('beforeunload', leaveWarning);
            };
            const fail = message => {
                unlock();
                panel.classList.remove('is-saving');
                panel.classList.add('is-error');
                status.textContent = message;
            };
            busy = true;
            controls.forEach(control => { control.disabled = true; });
            form.setAttribute('aria-busy', 'true');
            window.addEventListener('beforeunload', leaveWarning);
            form.querySelectorAll('[data-upload-error]').forEach(item => item.remove());
            form.querySelectorAll('[aria-invalid="true"]').forEach(input => input.removeAttribute('aria-invalid'));
            errors.replaceChildren();
            panel.hidden = false;
            panel.classList.remove('is-error', 'is-success', 'is-saving');
            setPercent(0);
            percent.hidden = !hasFiles;
            status.textContent = hasFiles ? 'در حال آپلود؛ لطفاً این صفحه را نبندید…' : 'در حال ذخیره…';
            if (!hasFiles) {
                panel.classList.add('is-saving');
                bar.removeAttribute('aria-valuenow');
            }

            const xhr = new XMLHttpRequest();
            const saving = () => {
                if (!busy) return;
                if (hasFiles) setPercent(100);
                panel.classList.add('is-saving');
                status.textContent = 'ارسال تمام شد؛ در حال ذخیره و تأیید سرور…';
            };
            xhr.upload.addEventListener('progress', event => {
                if (!busy || !hasFiles) return;
                if (event.lengthComputable) {
                    const value = Math.min(100, Math.floor(event.loaded / event.total * 100));
                    setPercent(value);
                    if (value === 100) saving();
                } else {
                    bar.removeAttribute('aria-valuenow');
                    percent.hidden = true;
                    panel.classList.add('is-saving');
                }
            });
            xhr.upload.addEventListener('load', saving);
            xhr.addEventListener('load', () => {
                let result;
                try { result = JSON.parse(xhr.responseText); } catch (_) { result = null; }
                if (xhr.status >= 200 && xhr.status < 300 && result && result.success === true) {
                    let destination;
                    try { destination = new URL(result.redirect_url, window.location.href); } catch (_) { destination = null; }
                    if (!destination || destination.origin !== window.location.origin) {
                        fail('پاسخ سرور نامعتبر بود؛ پیش از ارسال دوباره، فهرست را بررسی کنید.');
                        return;
                    }
                    window.removeEventListener('beforeunload', leaveWarning);
                    panel.classList.remove('is-saving');
                    panel.classList.add('is-success');
                    setPercent(100);
                    status.textContent = result.message;
                    window.location.assign(destination.href);
                    return;
                }
                if (xhr.status === 422 && result && result.errors) {
                    Object.entries(result.errors).forEach(([name, items]) => {
                        const field = Array.from(form.elements).find(input => input.name === name);
                        items.forEach(item => {
                            const li = document.createElement('li');
                            li.textContent = item.message;
                            errors.appendChild(li);
                            if (field) {
                                field.setAttribute('aria-invalid', 'true');
                                const hint = document.createElement('small');
                                hint.dataset.uploadError = '';
                                hint.className = 'upload-progress__field-error';
                                hint.textContent = item.message;
                                field.insertAdjacentElement('afterend', hint);
                            }
                        });
                    });
                    fail(result.message);
                } else if (xhr.responseURL && new URL(xhr.responseURL).pathname === '/accounts/login/') {
                    fail('نشست شما تمام شده است؛ دوباره وارد سامانه شوید.');
                } else if (xhr.status === 413) {
                    fail('حجم فایل بیشتر از حد مجاز سرور است؛ فایل کوچک‌تری انتخاب کنید.');
                } else if (xhr.status === 403) {
                    fail('اجازه ثبت تأیید نشد؛ ورود و دسترسی خود را بررسی کنید.');
                } else {
                    fail('تأیید ذخیره از سرور دریافت نشد؛ پیش از ارسال دوباره، فهرست را بررسی کنید.');
                }
            });
            xhr.addEventListener('error', () => fail('ارتباط قطع شد؛ تأیید ذخیره دریافت نشد. پیش از ارسال دوباره، فهرست را بررسی کنید.'));
            xhr.addEventListener('abort', () => fail('ارسال متوقف شد؛ تأیید ذخیره دریافت نشد.'));
            try {
                xhr.open('POST', form.action);
                xhr.setRequestHeader('X-RSP-Upload', '1');
                xhr.setRequestHeader('Accept', 'application/json');
                // The browser supplies the multipart boundary, including the CSRF form field.
                xhr.send(data);
            } catch (_) {
                fail('ارسال شروع نشد؛ اتصال خود را بررسی و دوباره تلاش کنید.');
            }
        });
    });
});
