// Filter the already-rendered snapshot only. No timer, network requests or live updates.
document.addEventListener('DOMContentLoaded', () => {
    const search = document.getElementById('attendance-search');
    const filter = document.getElementById('attendance-filter');
    if (!search || !filter) return;
    function apply() {
        const term = search.value.trim().toLocaleLowerCase('fa');
        document.querySelectorAll('#attendance-table tbody tr[data-name]').forEach(row => {
            const match = filter.value === 'all' || row.dataset.presence === filter.value || row.dataset.kind === filter.value;
            row.hidden = !match || !row.dataset.name.toLocaleLowerCase('fa').includes(term);
        });
    }
    search.addEventListener('input', apply);
    filter.addEventListener('change', apply);
});
