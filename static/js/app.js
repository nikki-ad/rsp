document.addEventListener("DOMContentLoaded", function () {
    var toggle = document.querySelector("[data-sidebar-toggle]");
    var overlay = document.querySelector("[data-sidebar-overlay]");

    function closeSidebar() {
        document.body.classList.remove("sidebar-open");
    }

    if (toggle) {
        toggle.addEventListener("click", function () {
            document.body.classList.toggle("sidebar-open");
        });
    }

    if (overlay) {
        overlay.addEventListener("click", closeSidebar);
    }
});
