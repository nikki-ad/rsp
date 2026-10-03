document.addEventListener('DOMContentLoaded', () => {
    const audience = document.getElementById('id_audience');
    if (audience) {
        const update = () => {
            [['classrooms', 'students'], ['teachers', 'teachers']].forEach(([name, value]) => {
                const field = document.querySelector(`[data-field="${name}"]`);
                if (!field) return;
                field.hidden = audience.value !== value;
                field.querySelectorAll('input').forEach(input => { input.disabled = field.hidden; });
            });
        };
        audience.addEventListener('change', update);
        update();
    }
    const kind = document.getElementById('id_content_type');
    const upload = document.getElementById('id_file');
    if (kind && upload) {
        const update = () => {
            upload.accept = kind.value === 'image' ? 'image/*' : kind.value === 'video' ? '.mp4,.webm,.mov,.m4v,.avi,.mkv,.3gp' : '';
            upload.setCustomValidity('');
        };
        kind.addEventListener('change', update);
        update();
    }
    document.querySelectorAll('input[type="file"]').forEach(input => {
        input.addEventListener('change', () => {
            const file = input.files[0];
            const video = input.name === 'video' || (kind && kind.value === 'video') || (file && /\.(mp4|webm|mov|m4v|avi|mkv|3gp)$/i.test(file.name));
            input.setCustomValidity(file && video && file.size > 20 * 1024 * 1024 ? 'حجم فیلم نباید بیشتر از ۲۰ مگابایت باشد.' : '');
            input.reportValidity();
        });
    });
});
