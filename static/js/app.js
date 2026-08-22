// =========================================================
// Dayflow HR Management System — Frontend behavior
// =========================================================

document.addEventListener("DOMContentLoaded", function () {

    // Confirm before any destructive delete action.
    document.querySelectorAll(".confirm-delete").forEach(function (form) {
        form.addEventListener("submit", function (e) {
            const confirmed = window.confirm(
                "Are you sure you want to delete this record? This action cannot be undone."
            );
            if (!confirmed) {
                e.preventDefault();
            }
        });
    });

    // Auto-dismiss flash messages after a few seconds.
    document.querySelectorAll(".flash").forEach(function (el) {
        setTimeout(function () {
            el.style.transition = "opacity 0.4s ease";
            el.style.opacity = "0";
            setTimeout(function () {
                el.remove();
            }, 400);
        }, 5000);
    });

    // Client-side check: end date cannot be before start date (time off form).
    const startDateInput = document.getElementById("start_date");
    const endDateInput = document.getElementById("end_date");
    if (startDateInput && endDateInput) {
        function validateDateRange() {
            if (startDateInput.value && endDateInput.value) {
                if (endDateInput.value < startDateInput.value) {
                    endDateInput.setCustomValidity("End date cannot be before start date.");
                } else {
                    endDateInput.setCustomValidity("");
                }
            }
        }
        startDateInput.addEventListener("change", validateDateRange);
        endDateInput.addEventListener("change", validateDateRange);
    }

    // Confirm before submitting an Approve/Reject time off action.
    document.querySelectorAll(".timeoff-action-form").forEach(function (form) {
        form.addEventListener("submit", function () {
            const btn = form.querySelector("button[type=submit]");
            if (btn) {
                btn.disabled = true;
                btn.textContent = "Processing...";
            }
        });
    });

});
