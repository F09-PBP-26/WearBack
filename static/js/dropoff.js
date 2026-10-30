document.addEventListener("DOMContentLoaded", function () {
    const previewElement = document.getElementById("dropoff-map");
    const modal = document.getElementById("location-modal");
    const pickerElement = document.getElementById("location-picker-map");

    const openButton = document.getElementById("change-location-button");
    const closeButton = document.getElementById("close-location-modal");
    const cancelButton = document.getElementById("cancel-location");
    const confirmButton = document.getElementById("confirm-location");

    const addressElement = document.getElementById("selected-address");
    const captionElement = document.getElementById("map-caption");
    const coordinatesElement = document.getElementById("selected-coordinates");
    const errorElement = document.getElementById("location-error");

    const requiredElements = [
        previewElement,
        modal,
        pickerElement,
        openButton,
        closeButton,
        cancelButton,
        confirmButton,
        addressElement,
        captionElement,
        coordinatesElement,
        errorElement
    ];

    // For Time
    const orderDate = document.getElementById("order-date");

    if (orderDate) {
        const now = new Date();

        orderDate.textContent = new Intl.DateTimeFormat("en-GB", {
            day: "numeric",
            month: "long",
            year: "numeric",
            timeZone: "Asia/Jakarta"
        }).format(now);
    }

    if (requiredElements.some(element => !element)) {
        console.error(
            "Location picker error: one or more HTML elements are missing."
        );
        return;
    }

    if (typeof L === "undefined") {
        console.error("Leaflet failed to load.");
        return;
    }

    // Default coordinates around Universitas Indonesia, Depok.
    const defaultLocation = L.latLng(-6.370375, 106.827413);

    let selectedLocation = null;
    let temporaryLocation = null;

    let previewMap = null;
    let previewMarker = null;

    let pickerMap = null;
    let pickerMarker = null;

    // Helper
    function formatCoordinates(location) {
        return (
            location.lat.toFixed(6) +
            ", " +
            location.lng.toFixed(6)
        );
    }

    function setError(message) {
        errorElement.textContent = message || "";
    }

    function setTemporaryLocation(latlng) {
        temporaryLocation = L.latLng(latlng.lat, latlng.lng);

        coordinatesElement.textContent =
            formatCoordinates(temporaryLocation);

        pickerMarker.setLatLng(temporaryLocation);

        confirmButton.disabled = false;
        setError("");
    }


    function initializePickerMap() {
        if (pickerMap) {
            return;
        }

        pickerMap = L.map(pickerElement).setView(
            defaultLocation,
            16
        );

        L.tileLayer(
            "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
            {
                maxZoom: 19,
                attribution:
                    '&copy; <a href="https://www.openstreetmap.org/copyright">' +
                    "OpenStreetMap</a> contributors"
            }
        ).addTo(pickerMap);

        pickerMarker = L.marker(defaultLocation, {
            draggable: true
        }).addTo(pickerMap);

        pickerMap.on("click", function (event) {
            setTemporaryLocation(event.latlng);
        });

        pickerMarker.on("dragend", function (event) {
            setTemporaryLocation(event.target.getLatLng());
        });
    }


    function openModal() {
        temporaryLocation = selectedLocation
            ? L.latLng(
                selectedLocation.lat,
                selectedLocation.lng
            )
            : null;

        const initialPosition =
            temporaryLocation || defaultLocation;

        coordinatesElement.textContent = temporaryLocation
            ? formatCoordinates(temporaryLocation)
            : "Click the map or drag the marker to select a point.";

        setError("");

        confirmButton.disabled = !temporaryLocation;
        confirmButton.textContent = "Use this location";

        modal.classList.add("is-open");
        modal.setAttribute("aria-hidden", "false");
        document.body.style.overflow = "hidden";

        initializePickerMap();

        pickerMap.setView(initialPosition, 16);
        pickerMarker.setLatLng(initialPosition);

        requestAnimationFrame(function () {
            pickerMap.invalidateSize();
        });
    }

    function closeModal() {
        modal.classList.remove("is-open");
        modal.setAttribute("aria-hidden", "true");
        document.body.style.overflow = "";
    }


    function updatePreview() {
    initializePreviewMap();

    const position = L.latLng(
        selectedLocation.lat,
        selectedLocation.lng
    );

    previewMap.setView(position, 16);
    previewMarker.setLatLng(position);
    previewMarker.bindPopup("Selected drop-off location");

    requestAnimationFrame(function () {
        previewMap.invalidateSize();
    });
}

    function initializePreviewMap() {
        if (previewMap) return;

        const initialLocation = selectedLocation
            ? L.latLng(selectedLocation.lat, selectedLocation.lng)
            : defaultLocation;

        previewMap = L.map(previewElement).setView(
            initialLocation,
            16
        );

        L.tileLayer(
            "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
            {
                maxZoom: 19,
                attribution:
                    '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            }
        ).addTo(previewMap);

        previewMarker = L.marker(initialLocation).addTo(previewMap);
    }

    function confirmLocation() {
        if (!temporaryLocation) {
            setError("Please click the map or move the marker first.");
            return;
        }

        try {
            selectedLocation = {lat: temporaryLocation.lat,lng: temporaryLocation.lng};

            const coordinates =
                formatCoordinates(selectedLocation);

            addressElement.textContent =
                "Selected location (" + coordinates + ")";

            captionElement.textContent =
                "Selected coordinates: " + coordinates;

            openButton.textContent = "Change";

            closeModal();
            updatePreview();

            console.log(
                "Drop-off location selected:",
                selectedLocation
            );
        } catch (error) {
            console.error(
                "Failed to confirm drop-off location:",
                error
            );

            setError(
                "Could not update the map. Please check the console."
            );
        }
    }


    openButton.addEventListener("click", openModal);

    closeButton.addEventListener("click", closeModal);

    cancelButton.addEventListener("click", closeModal);

    confirmButton.addEventListener("click", function (event) {
        event.preventDefault();
        confirmLocation();
    });

    modal.addEventListener("click", function (event) {
        if (event.target === modal) {
            closeModal();
        }
    });

    document.addEventListener("keydown", function (event) {
        if (
            event.key === "Escape" &&
            modal.classList.contains("is-open")
        ) {
            closeModal();
        }
    });
    initializePreviewMap();

    requestAnimationFrame(function () {
        previewMap.invalidateSize();
    });

    console.log("Drop-off location picker initialized.");
});


// ========================================
// MIDTRANS PAYMENT
// ========================================

document.addEventListener("DOMContentLoaded", function () {
    const paymentButton = document.getElementById("confirm-payment");
    const paymentMessage = document.getElementById("payment-message");
    const paymentForm = document.getElementById("payment-form");

    if (!paymentButton || !paymentForm) {
        return;
    }

    function getCsrfToken() {
        const csrfInput = paymentForm.querySelector(
            'input[name="csrfmiddlewaretoken"]'
        );

        return csrfInput ? csrfInput.value : "";
    }

    function showMessage(message) {
        if (paymentMessage) {
            paymentMessage.textContent = message;
        }
    }

    paymentButton.addEventListener("click", async function () {
        if (!window.snap) {
            showMessage("Payment service is unavailable. Please refresh the page.");
            return;
        }

        paymentButton.disabled = true;
        paymentButton.textContent = "Preparing payment...";
        showMessage("");

        try {
            const response = await fetch(
                paymentButton.dataset.paymentUrl,
                {
                    method: "POST",
                    headers: {
                        "X-CSRFToken": getCsrfToken(),
                        "Content-Type": "application/json"
                    },
                    credentials: "same-origin"
                }
            );

            const data = await response.json();

            if (!response.ok || !data.success || !data.token) {
                throw new Error(
                    data.message || "Unable to prepare payment."
                );
            }

            window.snap.pay(data.token, {
                onSuccess: function () {
                    showMessage(
                        "Payment submitted successfully. Waiting for payment verification."
                    );
                    paymentButton.disabled = false;
                    paymentButton.textContent = "Confirm Payment";
                },

                onPending: function () {
                    showMessage(
                        "Payment is pending. Please complete your payment."
                    );
                    paymentButton.disabled = false;
                    paymentButton.textContent = "Confirm Payment";
                },

                onError: function () {
                    showMessage(
                        "Payment failed. Please try again."
                    );
                    paymentButton.disabled = false;
                    paymentButton.textContent = "Confirm Payment";
                },

                onClose: function () {
                    showMessage(
                        "Payment window closed. You can continue payment later."
                    );
                    paymentButton.disabled = false;
                    paymentButton.textContent = "Confirm Payment";
                }
            });

        } catch (error) {
            console.error("Midtrans payment error:", error);

            showMessage(error.message || "An unexpected error occurred.");

            paymentButton.disabled = false;
            paymentButton.textContent = "Confirm Payment";
        }
    });
});