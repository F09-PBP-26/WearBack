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
            const paymentCard = element.closest(".payment-card");
            if (paymentCard) {
                paymentCard.querySelector("#pay-now-button").disabled = true;
                paymentCard.querySelector("#payment-help").textContent = "Payment time expired. Return to transactions to place a new order.";
            }
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

function transactionSearch() {
    const searchInput = document.querySelector("#site-search");
    const transactionList = document.querySelector(".transaction-list");

    if (!searchInput || !transactionList) {
        return;
    }

    const transactionCards = transactionList.querySelectorAll(".transaction-card");
    const transactionCount = document.querySelector("#transaction-count");
    const transactionPlural = document.querySelector("#transaction-plural");

    const transactionEmpty = document.querySelector(".transaction-empty");

    function filterTransactions() {
        const transactionQuery = searchInput.value.trim().toLowerCase();
        let visible = 0;

        transactionCards.forEach((card) => {
            const transactionFiltered = card.textContent.toLowerCase().includes(transactionQuery);
            card.hidden = !transactionFiltered;

            if (transactionFiltered) {
                visible++;
            }
        });

        if (transactionEmpty) {
            transactionEmpty.hidden = visible > 0;
        }

        if (transactionCount) {
            transactionCount.textContent = visible;
        }

        if (transactionPlural) {
            transactionPlural.textContent = visible === 1 ? "" : "s";
        }
    }
    searchInput.addEventListener("input", filterTransactions);
    filterTransactions();
}

transactionSearch();
