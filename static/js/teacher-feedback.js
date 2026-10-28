document.addEventListener('DOMContentLoaded', () => {
    const kind = document.getElementById('id_feedback_type');
    const group = document.querySelector('[data-feedback-upload]');
    const file = document.getElementById('id_feedback_file');
    if (!kind || !group || !file) return;
    const update = () => {
        group.hidden = kind.value === 'text';
        group.querySelectorAll('input').forEach(input => { input.disabled = group.hidden; });
        file.accept = kind.value === 'image' ? 'image/*' : kind.value === 'video' ? '.mp4,.webm,.mov,.m4v,.avi,.mkv,.3gp' : '';
        file.setCustomValidity('');
    };
    kind.addEventListener('change', update);
    file.addEventListener('change', () => {
        const upload = file.files[0];
        const video = kind.value === 'video' || (upload && /\.(mp4|webm|mov|m4v|avi|mkv|3gp)$/i.test(upload.name));
        file.setCustomValidity(upload && video && upload.size > 20 * 1024 * 1024 ? 'حجم فیلم نباید بیشتر از ۲۰ مگابایت باشد.' : '');
        file.reportValidity();
    });
    update();
});
