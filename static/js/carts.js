
document.addEventListener("DOMContentLoaded", function () {
    const cartItems = document.querySelector(".cart-items");
    const selectAll = document.querySelector("#select-all-cart");
    const selectionCount = document.querySelector("#cart-selection-count");
    const totalProducts = document.querySelector("#cart-total-products");
    const summaryItemCount = document.querySelector("#summary-item-count");
    const summarySubtotal = document.querySelector("#summary-subtotal");
    const summaryTotal = document.querySelector("#summary-total");
    const buyButton = document.querySelector("#cart-buy-button");
    const cartEmpty = document.querySelector("#cart-empty");
    const checkoutMessage = document.querySelector("#cart-checkout-message");

    if (!cartItems) return;

    const formatRupiah = (amount) =>
    "Rp" + Number(amount).toLocaleString("en-US");

    function getItems() {
        return [...cartItems.querySelectorAll(".cart-item")];
    }

    function updateCart() {
        const items = getItems();
        let selectedProducts = 0;
        let selectedQuantity = 0;
        let subtotal = 0;

        items.forEach((item) => {
            const checkbox = item.querySelector(".cart-select-item");
            const quantity = Number(item.dataset.quantity);
            const price = Number(item.dataset.price);
            const total = price * quantity;

            item.querySelector(".quantity-value").textContent = quantity;
            item.querySelector(".cart-item-total").textContent = formatRupiah(total);
            item.querySelector(".quantity-decrease").disabled = quantity <= 1;

            if (checkbox.checked) {
                selectedProducts++;
                selectedQuantity += quantity;
                subtotal += total;
            }
        });

        const checkedCount = items.filter((item) => item.querySelector(".cart-select-item").checked).length;

        selectAll.checked = items.length > 0 && checkedCount === items.length;
        selectAll.indeterminate = checkedCount > 0 && checkedCount < items.length;

        selectionCount.textContent = `${checkedCount} of ${items.length} products selected`;
        totalProducts.textContent = items.length;
        summaryItemCount.textContent = `${selectedQuantity} item${selectedQuantity !== 1 ? "s" : ""}`;
        summarySubtotal.textContent = formatRupiah(subtotal);
        summaryTotal.textContent = formatRupiah(subtotal);        
        buyButton.textContent =`Buy (${selectedQuantity} item${selectedQuantity !== 1 ? "s" : ""})`;
        buyButton.disabled = selectedQuantity === 0;

        if (cartEmpty) {
            cartEmpty.hidden = items.length > 0;
        }
        if (items.length === 0) {
            selectionCount.textContent = "0 of 0 products selected";
        }
    }

    selectAll.addEventListener("change", function () {
        getItems().forEach((item) => {item.querySelector(".cart-select-item").checked = selectAll.checked;});
        updateCart();
    });

    cartItems.addEventListener("change", function (event) {
        if (event.target.matches(".cart-select-item")) {
            updateCart();
        }
    });

    const cartConfirmModal = document.querySelector("#cart-confirm-modal");
    const confirmItemName = document.querySelector("#cart-confirm-item-name");
    const cancelRemoveButton = document.querySelector("#cart-cancel-remove");
    const confirmRemoveButton = document.querySelector("#cart-confirm-remove");

    let itemRemove = null;

    function getCookie(name) {
        const cookies = document.cookie.split(";");
        for (const cookie of cookies) {
            const trimmedCookie = cookie.trim();
            if (trimmedCookie.startsWith(name + "=")) {
                return decodeURIComponent(
                    trimmedCookie.substring(name.length + 1)
                );
            }
        }
        return null;
    }
    
    cartItems.addEventListener("click", function (event) {
        const item = event.target.closest(".cart-item");
        if (!item) return;

        if (event.target.closest(".quantity-increase")) {
            item.dataset.quantity = Number(item.dataset.quantity) + 1;
        } else if (event.target.closest(".quantity-decrease")) {
            item.dataset.quantity = Math.max(1, Number(item.dataset.quantity) - 1);
        } else if (event.target.closest(".cart-remove")) {
            itemRemove = item;
            const itemName = item.querySelector(".cart-item-details h2").textContent.trim();
            confirmItemName.textContent = itemName;
            cartConfirmModal.hidden = false;
            return;
        } else {
            return;
        }
        updateCart();
    });

    cancelRemoveButton.addEventListener("click", function () {
        cartConfirmModal.hidden = true;
        itemRemove = null;
    });

    confirmRemoveButton.addEventListener("click", async function () {
        if (!itemRemove) return;

        const item = itemRemove;
        const deleteUrl = item.dataset.deleteUrl;
        confirmRemoveButton.disabled = true;

        try {
            const response = await fetch(deleteUrl, {
                method: "POST",
                headers: {
                    "X-CSRFToken": getCookie("csrftoken"),
                    "X-Requested-With": "XMLHttpRequest"
                }
            });

            const data = await response.json();

            if (!response.ok || !data.success) {
                throw new Error(data.message || "Failed to remove item.");
            }

            item.remove();
            itemRemove = null;
            cartConfirmModal.hidden = true;
            updateCart();
        } catch (error) {
            console.error("Error removing cart item:", error);
            alert("Error: " + error.message);
        } finally {
            confirmRemoveButton.disabled = false;
        }
    });

    cartConfirmModal.addEventListener("click", function (event) {
        if (event.target === cartConfirmModal) {
            cartConfirmModal.hidden = true;
            itemRemove = null;
        }
    });

    const cartCheckout = document.querySelector("#cart-checkout");
    const selectedCartIds = document.querySelector("#selected-cart-ids");

    cartCheckout.addEventListener("submit", function (event) {
        const selectedItems = getItems().filter((item) => {
            return item.querySelector(".cart-select-item").checked;
        });
        if (selectedItems.length === 0) {
            event.preventDefault();
            return;
        }
        selectedCartIds.value = selectedItems.map((item) => item.dataset.cartId).join(",");
    });
    updateCart();
});

function cartSearch() {
    const searchInput = document.querySelector("#site-search");
    const cartList = document.querySelector(".cart-items");

    if (!searchInput || !cartList) {
        return;
    }

    const cartItems = cartList.querySelectorAll(".cart-item");
    const cartCount = document.querySelector("#cart-total-products");
    const cartPlural = document.querySelector("#cart-product-plural");
    const cartSearchEmpty = document.querySelector(".cart-search-empty");

    function filterCartItems() {
        const cartQuery = searchInput.value.trim().toLowerCase();
        let visible = 0;

        cartItems.forEach((item) => {
            const cartFiltered = item.textContent
                .toLowerCase()
                .includes(cartQuery);

            item.hidden = !cartFiltered;

            if (cartFiltered) {
                visible++;
            }
        });

        if (cartCount) {
            cartCount.textContent = visible;
        }
        if (cartPlural) {
            cartPlural.textContent = visible === 1 ? "" : "s";
        }
        if (cartSearchEmpty) {
            cartSearchEmpty.hidden = visible > 0 || cartItems.length === 0;
        }
    }
    searchInput.addEventListener("input", filterCartItems);
    filterCartItems();
}

cartSearch();