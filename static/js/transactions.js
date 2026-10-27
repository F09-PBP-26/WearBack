function updatePaymentCountdowns() {
    const countdowns = document.querySelectorAll(".payment-countdown");

    countdowns.forEach((element) => {
        const deadline = new Date(element.dataset.deadline).getTime();
        const remaining = deadline - Date.now();

        if (Number.isNaN(deadline)) {
            element.textContent = "Invalid deadline";
            return;
        }

        if (remaining <= 0) {
            element.textContent = "Payment time expired";
            element.classList.add("payment-expired");
            return;
        }

        const hours = Math.floor(remaining / (1000 * 60 * 60));
        const minutes = Math.floor(
            (remaining % (1000 * 60 * 60)) / (1000 * 60)
        );
        const seconds = Math.floor((remaining % (1000 * 60)) / 1000);

        element.textContent =
            `${hours.toString().padStart(2, "0")}:` +
            `${minutes.toString().padStart(2, "0")}:` +
            `${seconds.toString().padStart(2, "0")} remaining`;
    });
}

updatePaymentCountdowns();
setInterval(updatePaymentCountdowns, 1000);