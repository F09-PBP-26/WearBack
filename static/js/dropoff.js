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

    const latitudeInput = document.getElementById("id_latitude");
    const longitudeInput = document.getElementById("id_longitude");
    const addressInput = document.getElementById("id_address");

    const requiredElements = [
        latitudeInput,
        longitudeInput,
        addressInput,
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

    const savedLatitude = Number(latitudeInput.value);
    const savedLongitude = Number(longitudeInput.value);
    let selectedLocation = latitudeInput.value.trim() && longitudeInput.value.trim()
        && Number.isFinite(savedLatitude) && Math.abs(savedLatitude) <= 90
        && Number.isFinite(savedLongitude) && Math.abs(savedLongitude) <= 180
        ? {lat: savedLatitude, lng: savedLongitude} : null;
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

            latitudeInput.value = selectedLocation.lat.toFixed(6);
            longitudeInput.value = selectedLocation.lng.toFixed(6);
            addressElement.textContent = addressInput.value.trim()
                || "Selected location (" + coordinates + ")";

            captionElement.textContent =
                "Selected coordinates: " + coordinates;

            openButton.textContent = "Change";

            closeModal();
            updatePreview();

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

    if (selectedLocation) {
        openButton.textContent = "Change";
        captionElement.textContent = "Selected coordinates: " + formatCoordinates(selectedLocation);
    }
    addressInput.addEventListener("input", function () {
        addressElement.textContent = addressInput.value.trim() || "No address entered";
    });
});
