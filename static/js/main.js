(function () {
  var navLinks = document.querySelector(".nav-links");
  if (navLinks) {
    var slider = navLinks.querySelector(".nav-slider");
    var activePage = navLinks.dataset.activePage;
    try {
      var previous = JSON.parse(
        sessionStorage.getItem("wearback-menu-transition") || "null",
      );
      sessionStorage.removeItem("wearback-menu-transition");
      if (
        previous &&
        previous.to === window.location.pathname &&
        previous.from !== activePage &&
        Date.now() - previous.time < 5000 &&
        slider &&
        slider.animate &&
        !window.matchMedia("(prefers-reduced-motion: reduce)").matches
      ) {
        slider.animate(
          [
            {
              transform:
                previous.from === "auction"
                  ? "translateX(100%)"
                  : "translateX(0)",
              backgroundColor:
                previous.from === "auction"
                  ? "var(--color-primary)"
                  : "var(--color-accent)",
            },
            {
              transform:
                activePage === "auction" ? "translateX(100%)" : "translateX(0)",
              backgroundColor:
                activePage === "auction"
                  ? "var(--color-primary)"
                  : "var(--color-accent)",
            },
          ],
          { duration: 280, easing: "cubic-bezier(0.22, 1, 0.36, 1)" },
        );
      }
    } catch (error) {
      /* Navigation still works when browser storage is unavailable. */
    }
    navLinks.querySelectorAll(".nav-link").forEach(function (link) {
      link.addEventListener("click", function (event) {
        if (
          event.button !== 0 ||
          event.ctrlKey ||
          event.metaKey ||
          event.shiftKey ||
          event.altKey
        )
          return;
        try {
          sessionStorage.setItem(
            "wearback-menu-transition",
            JSON.stringify({
              from: activePage,
              to: new URL(link.href).pathname,
              time: Date.now(),
            }),
          );
        } catch (error) {
          /* Storage is optional for the sliding animation. */
        }
      });
    });
  }

  var toggle = document.querySelector(".nav-toggle");
  var menu = document.getElementById("navbar-menu");
  var profileButton = document.querySelector(".nav-profile");
  var profileMenu = document.getElementById("profile-menu");

  function positionProfileMenu() {
    if (!profileMenu || !profileMenu.matches(":popover-open") || !profileButton)
      return;
    requestAnimationFrame(function () {
      var bounds = profileButton.getBoundingClientRect();
      profileMenu.style.left =
        Math.max(
          8,
          Math.min(
            bounds.right - profileMenu.offsetWidth,
            window.innerWidth - profileMenu.offsetWidth - 8,
          ),
        ) + "px";
      profileMenu.style.top =
        Math.max(
          8,
          Math.min(
            bounds.bottom + 8,
            window.innerHeight - profileMenu.offsetHeight - 8,
          ),
        ) + "px";
    });
  }

  if (profileButton && profileMenu) {
    profileButton.addEventListener("click", function (e) {
      e.preventDefault();
      if (typeof profileMenu.togglePopover === "function") {
        profileMenu.togglePopover();
      }
    });
    profileMenu.addEventListener("toggle", positionProfileMenu);
    window.addEventListener("resize", positionProfileMenu);
  }

  function setOpen(open) {
    if (!open && profileMenu && profileMenu.matches(":popover-open"))
      profileMenu.hidePopover();
    if (toggle) toggle.setAttribute("aria-expanded", String(open));
    if (menu) menu.classList.toggle("is-open", open);
  }

  if (toggle) {
    toggle.addEventListener("click", function () {
      setOpen(toggle.getAttribute("aria-expanded") !== "true");
    });
  }

  document.addEventListener("keydown", function (e) {
    if (
      toggle &&
      e.key === "Escape" &&
      toggle.getAttribute("aria-expanded") === "true"
    ) {
      setOpen(false);
      toggle.focus();
    }
  });

  window.addEventListener("resize", function () {
    if (window.innerWidth > 768) setOpen(false);
  });

  function bindNavbarPopup(dialogId, openSelector, closeSelector) {
    var listItemDialog = document.getElementById(dialogId);
    var listItemTrigger = document.querySelector(openSelector);
    if (!listItemDialog || !listItemTrigger) return;
    listItemTrigger.addEventListener("click", function (event) {
      event.preventDefault(); // Mencegah tautan <a> berpindah halaman
      setOpen(false);
      listItemDialog.showModal();
      document.documentElement.classList.add("login-open");
    });
    var closeBtn = listItemDialog.querySelector(closeSelector);
    if (closeBtn) {
      closeBtn.addEventListener("click", function () {
        listItemDialog.close();
      });
    }
    listItemDialog.addEventListener("click", function (event) {
      var bounds = listItemDialog.getBoundingClientRect();
      if (
        event.target === listItemDialog &&
        (event.clientX < bounds.left ||
          event.clientX > bounds.right ||
          event.clientY < bounds.top ||
          event.clientY > bounds.bottom)
      )
        listItemDialog.close();
    });
    listItemDialog.addEventListener("close", function () {
      document.documentElement.classList.remove("login-open");
      if (
        listItemTrigger.getClientRects().length &&
        getComputedStyle(listItemTrigger).visibility !== "hidden"
      ) {
        listItemTrigger.focus();
      } else if (toggle) {
        toggle.focus();
      }
    });
  }

  bindNavbarPopup(
    "list-item-dialog",
    "[data-list-item-open]",
    "[data-list-item-close]",
  );
  bindNavbarPopup("cart-dialog", "[data-cart-open]", "[data-cart-close]");

  // --- MODUL AUTHENTICATION & DIALOG ---
  var loginDialog = document.getElementById("login-dialog");
  var loginTrigger = null;
  var authPanels = loginDialog
    ? loginDialog.querySelectorAll("[data-auth-panel]")
    : [];
  var authForms = loginDialog
    ? loginDialog.querySelectorAll(".login-form")
    : [];

  function authNext() {
    if (loginDialog && loginDialog.dataset.next)
      return loginDialog.dataset.next;
    var destination = new URL(window.location.href);
    destination.searchParams.delete("login");
    destination.searchParams.delete("register");
    destination.searchParams.delete("next");
    return destination.pathname + destination.search + destination.hash;
  }

  function clearErrors(form) {
    if (!form) return;
    form.querySelectorAll(".field-error").forEach(function (error) {
      error.remove();
    });
    form.querySelectorAll("[aria-invalid]").forEach(function (input) {
      input.removeAttribute("aria-invalid");
      input.removeAttribute("aria-describedby");
    });
    var status = form.querySelector(".login-status");
    if (status) {
      status.textContent = "";
      status.hidden = true;
    }
  }

  function showErrors(form, errors) {
    var firstInput = null;
    Object.keys(errors).forEach(function (name) {
      var input = form.elements.namedItem(name);
      if (input && input.closest(".field")) {
        var error = document.createElement("p");
        error.className = "field-error";
        error.id = "error-" + name;
        error.textContent = Array.isArray(errors[name])
          ? errors[name].join(" ")
          : errors[name];
        input.closest(".field").appendChild(error);
        input.setAttribute("aria-invalid", "true");
        input.setAttribute("aria-describedby", error.id);
        if (!firstInput) firstInput = input;
      } else {
        var status = form.querySelector(".login-status");
        if (status) {
          status.textContent = Array.isArray(errors[name])
            ? errors[name].join(" ")
            : errors[name];
          status.hidden = false;
        }
      }
    });
    if (firstInput) firstInput.focus();
  }

  function openLogin(trigger, mode) {
    if (!loginDialog) return;
    mode = mode || "login";
    authPanels.forEach(function (panel) {
      panel.hidden = panel.getAttribute("data-auth-panel") !== mode;
      clearErrors(panel.querySelector(".login-form"));
    });
    loginDialog.setAttribute("aria-labelledby", mode + "-title");
    loginDialog.setAttribute("aria-describedby", mode + "-description");
    if (!loginDialog.open) {
      loginTrigger = trigger;
      loginDialog.showModal();
    }
    setOpen(false);
    document.documentElement.classList.add("login-open");
    var firstInput = loginDialog.querySelector(
      "[data-auth-panel='" + mode + "'] input",
    );
    if (firstInput) firstInput.focus();
    loginDialog.scrollTop = 0;
  }

  document.querySelectorAll("[data-login-open]").forEach(function (trigger) {
    trigger.addEventListener("click", function () {
      openLogin(trigger, "login");
    });
  });

  document.querySelectorAll("[data-register-open]").forEach(function (trigger) {
    trigger.addEventListener("click", function () {
      openLogin(trigger, "register");
    });
  });

  document.querySelectorAll("[data-profile-open]").forEach(function (trigger) {
    trigger.addEventListener("click", function () {
      openLogin(trigger, "profile");
    });
  });

  if (loginDialog) {
    loginDialog
      .querySelectorAll("[data-login-close]")
      .forEach(function (button) {
        button.addEventListener("click", function () {
          loginDialog.close();
        });
      });

    loginDialog.addEventListener("click", function (event) {
      var bounds = loginDialog.getBoundingClientRect();
      if (
        event.target === loginDialog &&
        (event.clientX < bounds.left ||
          event.clientX > bounds.right ||
          event.clientY < bounds.top ||
          event.clientY > bounds.bottom)
      ) {
        loginDialog.close();
      }
    });

    loginDialog.addEventListener("close", function () {
      document.documentElement.classList.remove("login-open");
      authForms.forEach(function (form) {
        form.reset();
        clearErrors(form);
      });
      if (
        loginTrigger &&
        loginTrigger.getClientRects().length &&
        window.getComputedStyle(loginTrigger).visibility !== "hidden"
      ) {
        loginTrigger.focus();
      }
    });
  }

  authForms.forEach(function (form) {
    form.addEventListener("submit", async function (event) {
      event.preventDefault();
      if (form.dataset.submitting === "true") return;
      clearErrors(form);
      form.dataset.submitting = "true";
      var submit = form.querySelector('[type="submit"]');
      var originalLabel = submit ? submit.textContent : "";
      if (submit) {
        submit.disabled = true;
        submit.textContent = "Please wait...";
      }
      var body = new FormData(form);
      body.set("next", authNext());
      try {
        var response = await fetch(form.action, {
          method: "POST",
          body: body,
          credentials: "same-origin",
          headers: {
            Accept: "application/json",
            "X-CSRFToken": body.get("csrfmiddlewaretoken"),
          },
        });
        var data;
        try {
          data = await response.json();
        } catch (error) {
          throw new Error(
            response.status === 401
              ? "Your session expired. Refresh the page and try again."
              : "Something went wrong. Please try again.",
          );
        }
        if (response.ok && data.redirect) {
          window.location.assign(data.redirect);
        } else {
          showErrors(form, data.errors || { __all__: ["Please try again."] });
          form.querySelectorAll('[type="password"]').forEach(function (input) {
            input.value = "";
          });
        }
      } catch (err) {
        var status = form.querySelector(".login-status");
        if (status) {
          status.textContent =
            err.message || "Something went wrong. Please try again.";
          status.hidden = false;
        }
      } finally {
        form.dataset.submitting = "false";
        if (submit) {
          submit.disabled = false;
          submit.textContent = originalLabel;
        }
      }
    });
  });

  document.querySelectorAll("[data-sso-login]").forEach(function (link) {
    var url = new URL(link.href);
    url.searchParams.set("next", authNext());
    link.href = url.pathname + url.search;
  });

  var pageUrl = new URL(window.location.href);
  if (
    loginDialog &&
    (loginDialog.dataset.initialMode ||
      pageUrl.searchParams.get("login") === "1" ||
      pageUrl.searchParams.get("register") === "1")
  ) {
    var initialMode =
      loginDialog.dataset.initialMode ||
      (pageUrl.searchParams.get("register") === "1" ? "register" : "login");
    openLogin(document.querySelector(".nav-login"), initialMode);
    pageUrl.searchParams.delete("login");
    pageUrl.searchParams.delete("register");
    window.history.replaceState(
      null,
      "",
      pageUrl.pathname + pageUrl.search + pageUrl.hash,
    );
    if (loginDialog.dataset.authNotice) {
      var notice = loginDialog.querySelector(
        "[data-auth-panel='" + initialMode + "'] .login-status",
      );
      if (notice) {
        notice.textContent = loginDialog.dataset.authNotice;
        notice.hidden = false;
      }
    }
  }

  var search = document.getElementById("site-search");
  var navbar = document.querySelector(".navbar");
  var cancelSearch = document.querySelector(".search-cancel");
  if (search && navbar && cancelSearch) {
    var searchForm = search.closest(".search");
    var searchAnimation;
    var hiddenControls = navbar.querySelectorAll(
      ".nav-links, .nav-account, .nav-menu > .nav-login, .nav-toggle",
    );
    function setSearchMode(active) {
      if (navbar.classList.contains("is-searching") === active) return;
      if (searchAnimation) searchAnimation.cancel();
      var before = searchForm.getBoundingClientRect();
      if (active && profileMenu && profileMenu.matches(":popover-open"))
        profileMenu.hidePopover();
      navbar.classList.toggle("is-searching", active);
      cancelSearch.hidden = !active;
      hiddenControls.forEach(function (control) {
        control.inert = active;
      });
      if (!active && window.innerWidth <= 768) setOpen(false);
      var after = searchForm.getBoundingClientRect();
      if (
        after.width &&
        before.width &&
        searchForm.animate &&
        !window.matchMedia("(prefers-reduced-motion: reduce)").matches
      ) {
        var target = getComputedStyle(searchForm).transform;
        target = target === "none" ? "" : target;
        searchAnimation = searchForm.animate(
          [
            {
              transform:
                target +
                " translate(" +
                (before.left - after.left) +
                "px," +
                (before.top - after.top) +
                "px) scaleX(" +
                before.width / after.width +
                ")",
            },
            { transform: target || "none" },
          ],
          { duration: 280, easing: "cubic-bezier(0.22, 1, 0.36, 1)" },
        );
      }
    }
    function exitSearch() {
      search.blur();
      setSearchMode(false);
      var returnTarget =
        window.innerWidth <= 768 ? toggle : navbar.querySelector(".nav-brand");
      requestAnimationFrame(function () {
        if (returnTarget) returnTarget.focus({ preventScroll: true });
      });
    }
    search.addEventListener("focus", function () {
      setSearchMode(true);
    });
    cancelSearch.addEventListener("click", exitSearch);
    document.addEventListener("pointerdown", function (event) {
      if (
        navbar.classList.contains("is-searching") &&
        !navbar.contains(event.target)
      ) {
        search.blur();
        setSearchMode(false);
      }
    });
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && navbar.classList.contains("is-searching")) {
        event.preventDefault();
        exitSearch();
      }
    });
    window.addEventListener("resize", function () {
      if (searchAnimation) searchAnimation.cancel();
    });
  }
  document
    .querySelectorAll("[data-listing-thumbnail] img[data-fallback-src]")
    .forEach(function (image) {
      function showFallback() {
        if (image.getAttribute("src") !== image.dataset.fallbackSrc) {
          image.src = image.dataset.fallbackSrc;
          if (image.alt) image.alt = "No product photo available";
        }
      }
      image.addEventListener("error", showFallback);
      if (image.complete && image.naturalWidth === 0) showFallback();
    });

  var catalog = document.querySelector(".catalog-grid");
  if (search && catalog) {
    var items = catalog.querySelectorAll(".catalog-item");
    var empty = document.querySelector(".catalog-empty");
    var catalogSection = document.getElementById("catalog");
    var searchScrollTimer;
    var selectedCategory = "all";
    var categoryFilters = document.querySelectorAll("[data-category-filter]");
    function filterCatalog() {
      var query = search.value.trim().toLowerCase();
      var visible = 0;
      items.forEach(function (item) {
        item.hidden =
          item.textContent.toLowerCase().indexOf(query) === -1 ||
          (selectedCategory !== "all" &&
            item.dataset.category !== selectedCategory);
        if (!item.hidden) visible += 1;
      });
      if (empty) empty.hidden = items.length === 0 || visible > 0;
    }
    function setCategory(category) {
      selectedCategory = category;
      categoryFilters.forEach(function (filter) {
        var active = filter.dataset.categoryFilter === category;
        filter.classList.toggle("is-active", active);
        filter.setAttribute("aria-pressed", String(active));
      });
      filterCatalog();
    }
    categoryFilters.forEach(function (button) {
      button.addEventListener("click", function () {
        setCategory(button.dataset.categoryFilter);
      });
    });
    search.addEventListener("input", function () {
      filterCatalog();
      clearTimeout(searchScrollTimer);
      searchScrollTimer = setTimeout(function () {
        if (!catalogSection) return;
        catalogSection.scrollIntoView({
          block: "start",
          behavior: window.matchMedia("(prefers-reduced-motion: reduce)")
            .matches
            ? "instant"
            : "smooth",
        });
      }, 120);
    });
    var resetFilters = document.querySelector("[data-catalog-reset]");
    if (resetFilters) {
      resetFilters.addEventListener("click", function () {
        clearTimeout(searchScrollTimer);
        search.value = "";
        setCategory("all");
        var allCategories = document.querySelector('[data-category-filter="all"]');
        if (allCategories) allCategories.focus();
      });
    }
    filterCatalog();
  }
})();
