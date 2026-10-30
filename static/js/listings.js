(function () {
  document.querySelectorAll('[data-notice-dismiss]').forEach(function (button) {
    button.addEventListener('click', function () {
      button.closest('[data-listing-notice]').remove();
    });
  });

  document.querySelectorAll('[data-item-photo]').forEach(function (photo) {
    var image = photo.querySelector('[data-product-image]');
    if (!image) return;
    function showFallback() {
      image.hidden = true;
      photo.querySelector('[data-photo-fallback]').hidden = false;
      photo.querySelector('[data-photo-caption]').textContent = 'Photo unavailable. You can still explore the item details.';
    }
    image.addEventListener('error', showFallback);
    if (image.complete && image.naturalWidth === 0) showFallback();
  });

  document.querySelectorAll('[data-seller-photo]').forEach(function (photo) {
    var input = photo.querySelector('input[name="image_url"]');
    var image = photo.querySelector('[data-preview-image]');
    var box = photo.querySelector('[data-preview-box]');
    var empty = photo.querySelector('[data-preview-empty]');
    var title = photo.querySelector('[data-preview-title]');
    var hint = photo.querySelector('[data-preview-hint]');
    var timer;
    var revision = 0;
    function showMessage(heading, message) {
      image.hidden = true;
      empty.hidden = false;
      box.classList.remove('seller-photo-loaded');
      title.textContent = heading;
      hint.textContent = message;
    }
    function showFailure() {
      showMessage('We couldn’t load this photo', 'Check that the URL links directly to an image.');
    }
    image.addEventListener('error', showFailure);
    if (image.getAttribute('src') && image.complete && !image.naturalWidth) showFailure();
    input.addEventListener('input', function () {
      clearTimeout(timer);
      var current = ++revision;
      var url = input.value.trim();
      if (!url) {
        showMessage('Your photo will appear here', 'Paste a photo URL below');
        return;
      }
      try {
        if (new URL(url).protocol !== 'https:') throw new Error('HTTPS required');
      } catch (error) {
        showMessage('Use a secure photo URL', 'Paste a direct image link beginning with https://.');
        return;
      }
      showMessage('Loading your photo…', 'Checking the image link');
      timer = setTimeout(function () {
        var candidate = new Image();
        candidate.onload = function () {
          if (current !== revision) return;
          image.src = url;
          image.hidden = false;
          empty.hidden = true;
          box.classList.add('seller-photo-loaded');
        };
        candidate.onerror = function () { if (current === revision) showFailure(); };
        candidate.src = url;
      }, 250);
    });
  });

  var sellerForm = document.querySelector('[data-seller-form]');
  if (sellerForm) {
    var submitting = false;
    var saveButton = sellerForm.querySelector('[data-save-item]');
    var saveLabel = saveButton.textContent;
    var hasErrors = Boolean(document.querySelector('[data-form-errors]'));
    function formValues() {
      return JSON.stringify(Array.from(new FormData(sellerForm).entries()).filter(function (entry) {
        return entry[0] !== 'csrfmiddlewaretoken';
      }));
    }
    var initialValues = formValues();
    function updateDirty() {
      sellerForm.dataset.dirty = String(hasErrors || formValues() !== initialValues);
    }
    sellerForm.addEventListener('input', updateDirty);
    sellerForm.addEventListener('change', updateDirty);
    sellerForm.addEventListener('invalid', function (event) {
      var details = event.target.closest('details');
      if (details) details.open = true;
    }, true);
    updateDirty();
    window.addEventListener('beforeunload', function (event) {
      if (!submitting && sellerForm.dataset.dirty === 'true') {
        event.preventDefault();
        event.returnValue = '';
      }
    });
    sellerForm.addEventListener('submit', function (event) {
      if (submitting) { event.preventDefault(); return; }
      submitting = true;
      saveButton.disabled = true;
      saveButton.textContent = 'Saving…';
    });
    document.querySelectorAll('[data-discard-changes]').forEach(function (link) {
      link.addEventListener('click', function () { submitting = true; });
    });
    window.addEventListener('pageshow', function (event) {
      if (event.persisted) {
        submitting = false;
        saveButton.disabled = false;
        saveButton.textContent = saveLabel;
        updateDirty();
      }
    });
    var errors = document.querySelector('[data-form-errors]');
    if (errors) errors.focus();
  }

  document.querySelectorAll('[data-quantity-control]').forEach(function (control) {
    var input = control.querySelector('[data-quantity-input]');
    var decrease = control.querySelector('[data-quantity-decrease]');
    var increase = control.querySelector('[data-quantity-increase]');
    var status = document.querySelector('[data-quantity-status]');
    var maximum = Number(input.max);
    function updateQuantity(value) {
      value = Number.isFinite(value) ? Math.floor(value) : 1;
      value = Math.max(1, Math.min(maximum, value));
      input.value = value;
      decrease.disabled = value <= 1;
      increase.disabled = value >= maximum;
      if (status) status.textContent = 'Quantity: ' + value;
    }
    decrease.addEventListener('click', function () { updateQuantity(Number(input.value) - 1); });
    increase.addEventListener('click', function () { updateQuantity(Number(input.value) + 1); });
    input.addEventListener('input', function () {
      if (input.value !== '') updateQuantity(input.valueAsNumber);
    });
    input.addEventListener('change', function () { updateQuantity(input.valueAsNumber); });
    input.addEventListener('blur', function () { updateQuantity(input.valueAsNumber); });
    updateQuantity(Number(input.value));

    var cartForm = document.querySelector('[data-add-to-cart-form]');
    var cartQuantity = cartForm ? cartForm.querySelector('[data-cart-quantity]') : null;

    if (cartQuantity) {
      function syncCartQuantity() {
        cartQuantity.value = input.value;
      }

      input.addEventListener('input', syncCartQuantity);
      input.addEventListener('change', syncCartQuantity);
      syncCartQuantity();
    }
  });

  document.querySelectorAll('[data-listing-dialog]').forEach(function (dialog) {
    var trigger = null;
    document.querySelectorAll('[data-dialog-open]').forEach(function (link) {
      if (link.dataset.dialogOpen !== dialog.id) return;
      link.addEventListener('click', function (event) {
        if (link.hasAttribute('data-require-dirty') && (!sellerForm || sellerForm.dataset.dirty !== 'true')) return;
        if (typeof dialog.showModal !== 'function') return;
        event.preventDefault();
        trigger = link;
        dialog.showModal();
        document.documentElement.classList.add('login-open');
      });
    });
    dialog.querySelectorAll('[data-dialog-close]').forEach(function (button) {
      button.addEventListener('click', function () { dialog.close(); });
    });
    dialog.addEventListener('click', function (event) {
      var bounds = dialog.getBoundingClientRect();
      if (event.target === dialog && (event.clientX < bounds.left || event.clientX > bounds.right ||
          event.clientY < bounds.top || event.clientY > bounds.bottom)) dialog.close();
    });
    dialog.addEventListener('close', function () {
      if (!document.querySelector('dialog[open]')) document.documentElement.classList.remove('login-open');
      if (trigger) trigger.focus();
    });
  });
}());
