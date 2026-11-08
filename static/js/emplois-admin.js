/* Champs correspondant au cycle choisi. */
(() => {
    function init() {
        const select = document.getElementById('edt-cycle');
        if (!select) return;

        function updateFields() {
            const mode = {DUT: 'dut', Bachelor: 'bachelor', Licence: 'unique'}[select.value];
            document.querySelectorAll('[data-edt-fields]').forEach(section => {
                const visible = section.dataset.edtFields === mode;
                section.hidden = !visible;
                section.querySelectorAll('input').forEach(input => { input.disabled = !visible; });
            });
        }

        select.addEventListener('change', updateFields);
        updateFields();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init, { once: true });
    } else {
        init();
    }
})();
