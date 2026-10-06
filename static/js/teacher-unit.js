document.addEventListener('DOMContentLoaded', () => {
  const unit = document.getElementById('id_is_language_teacher');
  if (!unit) return;
  const classrooms = document.querySelectorAll('[name="classrooms"]');
  function update() {
    classrooms.forEach(input => {
      input.disabled = unit.checked;
      if (unit.checked) input.checked = false;
    });
  }
  unit.addEventListener('change', update);
  update();
});
