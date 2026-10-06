    (function () {
      var navLinks = document.querySelector('.nav-links');
      if (navLinks) {
        var slider = navLinks.querySelector('.nav-slider');
        var activePage = navLinks.dataset.activePage;
        try {
          var previous = JSON.parse(sessionStorage.getItem('wearback-menu-transition') || 'null');
          sessionStorage.removeItem('wearback-menu-transition');
          if (previous && previous.to === window.location.pathname && previous.from !== activePage &&
              Date.now() - previous.time < 5000 && slider && slider.animate &&
              !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
            slider.animate([
              { transform: previous.from === 'auction' ? 'translateX(100%)' : 'translateX(0)',
                backgroundColor: previous.from === 'auction' ? 'var(--color-primary)' : 'var(--color-accent)' },
              { transform: activePage === 'auction' ? 'translateX(100%)' : 'translateX(0)',
                backgroundColor: activePage === 'auction' ? 'var(--color-primary)' : 'var(--color-accent)' }
            ], { duration: 280, easing: 'cubic-bezier(0.22, 1, 0.36, 1)' });
          }
        } catch (error) { /* Navigation still works when browser storage is unavailable. */ }
        navLinks.querySelectorAll('.nav-link').forEach(function (link) {
          link.addEventListener('click', function (event) {
            if (event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
            try {
              sessionStorage.setItem('wearback-menu-transition', JSON.stringify({
                from: activePage, to: new URL(link.href).pathname, time: Date.now()
              }));
            } catch (error) { /* Storage is optional for the sliding animation. */ }
          });
        });
      }

      var toggle = document.querySelector('.nav-toggle');
      var menu = document.getElementById('navbar-menu');
      var profileButton = document.querySelector('.nav-profile');
      var profileMenu = document.getElementById('profile-menu');
      function positionProfileMenu() {
        if (!profileMenu || !profileMenu.matches(':popover-open')) return;
        var bounds = profileButton.getBoundingClientRect();
        profileMenu.style.left = Math.max(8, Math.min(bounds.right - profileMenu.offsetWidth,
          window.innerWidth - profileMenu.offsetWidth - 8)) + 'px';
        profileMenu.style.top = Math.max(8, Math.min(bounds.bottom + 8,
          window.innerHeight - profileMenu.offsetHeight - 8)) + 'px';
      }
      if (profileButton && profileMenu) {
        profileMenu.addEventListener('toggle', positionProfileMenu);
        window.addEventListener('resize', positionProfileMenu);
      }

      function setOpen(open) {
        if (!open && profileMenu && profileMenu.matches(':popover-open')) profileMenu.hidePopover();
        toggle.setAttribute('aria-expanded', String(open));
        menu.classList.toggle('is-open', open);
      }

      toggle.addEventListener('click', function () {
        setOpen(toggle.getAttribute('aria-expanded') !== 'true');
      });

      document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && toggle.getAttribute('aria-expanded') === 'true') {
          setOpen(false);
          toggle.focus();
        }
      });

      window.addEventListener('resize', function () {
        if (window.innerWidth > 768) setOpen(false);
      });

      var loginDialog = document.getElementById('login-dialog');
      function bindNavbarPopup(dialogId, openSelector, closeSelector) {
        var listItemDialog = document.getElementById(dialogId);
        var listItemTrigger = document.querySelector(openSelector);
        if (!listItemDialog || !listItemTrigger) return;
        listItemTrigger.addEventListener('click', function () {
          setOpen(false);
          listItemDialog.showModal();
          document.documentElement.classList.add('login-open');
        });
        listItemDialog.querySelector(closeSelector).addEventListener('click', function () {
          listItemDialog.close();
        });
        listItemDialog.addEventListener('click', function (event) {
          var bounds = listItemDialog.getBoundingClientRect();
          if (event.target === listItemDialog &&
              (event.clientX < bounds.left || event.clientX > bounds.right ||
               event.clientY < bounds.top || event.clientY > bounds.bottom)) listItemDialog.close();
        });
        listItemDialog.addEventListener('close', function () {
          document.documentElement.classList.remove('login-open');
          if (listItemTrigger.getClientRects().length && getComputedStyle(listItemTrigger).visibility !== 'hidden') {
            listItemTrigger.focus();
          } else {
            toggle.focus();
          }
        });
      }
      bindNavbarPopup('list-item-dialog', '[data-list-item-open]', '[data-list-item-close]');
      bindNavbarPopup('cart-dialog', '[data-cart-open]', '[data-cart-close]');
      if (loginDialog) {
        var loginTrigger = null;
        var authPanels = loginDialog.querySelectorAll('[data-auth-panel]');
        var authForms = loginDialog.querySelectorAll('.login-form');

        function clearErrors(form) {
          form.querySelectorAll('.field-error').forEach(function (error) { error.remove(); });
          form.querySelectorAll('[aria-invalid]').forEach(function (input) {
            input.removeAttribute('aria-invalid');
            input.removeAttribute('aria-describedby');
          });
          var status = form.querySelector('.login-status');
          status.textContent = '';
          status.hidden = true;
        }

        function showErrors(form, errors) {
          var messages = [];
          var firstInput = null;
          Object.keys(errors).forEach(function (name) {
            var input = form.elements.namedItem(name);
            if (input && input.closest('.field')) {
              var error = document.createElement('p');
              error.className = 'field-error';
              error.id = input.id + '-error';
              error.textContent = errors[name].join(' ');
              input.closest('.field').appendChild(error);
              input.setAttribute('aria-invalid', 'true');
              input.setAttribute('aria-describedby', error.id);
              if (!firstInput) firstInput = input;
            } else {
              messages = messages.concat(errors[name]);
            }
          });
          var status = form.querySelector('.login-status');
          status.textContent = messages.join(' ') || 'Please check the highlighted fields.';
          status.hidden = false;
          if (firstInput) firstInput.focus();
        }

        function openLogin(trigger, mode) {
          mode = mode || 'login';
          var selectedPanel = loginDialog.querySelector('[data-auth-panel="' + mode + '"]');
          if (!selectedPanel) return;
          authPanels.forEach(function (panel) {
            panel.hidden = panel.getAttribute('data-auth-panel') !== mode;
            clearErrors(panel.querySelector('.login-form'));
          });
          loginDialog.setAttribute('aria-labelledby', mode + '-title');
          loginDialog.setAttribute('aria-describedby', mode + '-description');
          if (!loginDialog.open) {
            loginTrigger = trigger;
            loginDialog.showModal();
          }
          setOpen(false);
          document.documentElement.classList.add('login-open');
          loginDialog.querySelector('[data-auth-panel="' + mode + '"] input').focus();
          loginDialog.scrollTop = 0;
        }

        document.querySelectorAll('[data-login-open]').forEach(function (trigger) {
          trigger.addEventListener('click', function () { openLogin(trigger); });
        });
        document.querySelectorAll('[data-register-open]').forEach(function (trigger) {
          trigger.addEventListener('click', function () { openLogin(trigger, 'register'); });
        });
        loginDialog.querySelectorAll('[data-login-close]').forEach(function (button) {
          button.addEventListener('click', function () { loginDialog.close(); });
        });
        loginDialog.addEventListener('click', function (event) {
          var bounds = loginDialog.getBoundingClientRect();
          if (event.target === loginDialog &&
              (event.clientX < bounds.left || event.clientX > bounds.right ||
               event.clientY < bounds.top || event.clientY > bounds.bottom)) {
            loginDialog.close();
          }
        });
        loginDialog.addEventListener('close', function () {
          document.documentElement.classList.remove('login-open');
          authForms.forEach(function (form) {
            form.reset();
            clearErrors(form);
          });
          if (loginTrigger) {
            if (loginTrigger.getClientRects().length && window.getComputedStyle(loginTrigger).visibility !== 'hidden') {
              loginTrigger.focus();
            } else {
              toggle.focus();
            }
          }
        });
        authForms.forEach(function (form) {
          form.addEventListener('submit', async function (event) {
            event.preventDefault();
            if (form.dataset.submitting === 'true') return;
            clearErrors(form);
            form.dataset.submitting = 'true';
            var submit = form.querySelector('[type="submit"]');
            var originalLabel = submit.textContent;
            submit.disabled = true;
            submit.textContent = 'Please wait…';
            var body = new FormData(form);
            body.set('next', window.location.pathname + window.location.search + window.location.hash);
            try {
              var response = await fetch(form.action, {
                method: 'POST', body: body, credentials: 'same-origin',
                headers: { 'Accept': 'application/json', 'X-CSRFToken': body.get('csrfmiddlewaretoken') }
              });
              var data;
              try { data = await response.json(); } catch (error) {
                throw new Error(response.status === 403 ? 'Your session expired. Refresh the page and try again.' : 'Something went wrong. Please try again.');
              }
              if (response.ok && data.redirect) {
                window.location.assign(data.redirect);
              } else {
                showErrors(form, data.errors || { '__all__': ['Please try again.'] });
                form.querySelectorAll('[type="password"]').forEach(function (input) { input.value = ''; });
              }
            } catch (error) {
              showErrors(form, { '__all__': [error.message || 'Unable to connect. Please try again.'] });
            } finally {
              form.dataset.submitting = 'false';
              submit.disabled = false;
              submit.textContent = originalLabel;
            }
          });
        });

        document.querySelectorAll('[data-sso-login]').forEach(function (link) {
          var url = new URL(link.href);
          url.searchParams.set('next', window.location.pathname + window.location.search + window.location.hash);
          link.href = url.pathname + url.search;
        });

        var pageUrl = new URL(window.location.href);
        if (loginDialog.dataset.initialMode || pageUrl.searchParams.get('login') === '1' || pageUrl.searchParams.get('register') === '1') {
          var initialMode = loginDialog.dataset.initialMode || (pageUrl.searchParams.get('register') === '1' ? 'register' : 'login');
          openLogin(document.querySelector('.nav-login'), initialMode);
          pageUrl.searchParams.delete('login');
          pageUrl.searchParams.delete('register');
          window.history.replaceState(null, '', pageUrl.pathname + pageUrl.search + pageUrl.hash);
          if (loginDialog.dataset.authNotice) {
            var notice = loginDialog.querySelector('[data-auth-panel="' + initialMode + '"] .login-status');
            notice.textContent = loginDialog.dataset.authNotice;
            notice.hidden = false;
          }
        }
      }

      var search = document.getElementById('site-search');
      var navbar = document.querySelector('.navbar');
      var cancelSearch = document.querySelector('.search-cancel');
      if (search && navbar && cancelSearch) {
        var searchForm = search.closest('.search');
        var searchAnimation;
        var hiddenControls = navbar.querySelectorAll('.nav-links, .nav-account, .nav-menu > .nav-login, .nav-toggle');
        function setSearchMode(active) {
          if (navbar.classList.contains('is-searching') === active) return;
          if (searchAnimation) searchAnimation.cancel();
          var before = searchForm.getBoundingClientRect();
          if (active && profileMenu && profileMenu.matches(':popover-open')) profileMenu.hidePopover();
          navbar.classList.toggle('is-searching', active);
          cancelSearch.hidden = !active;
          hiddenControls.forEach(function (control) { control.inert = active; });
          if (!active && window.innerWidth <= 768) setOpen(false);
          var after = searchForm.getBoundingClientRect();
          if (after.width && before.width && searchForm.animate &&
              !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
            var target = getComputedStyle(searchForm).transform;
            target = target === 'none' ? '' : target;
            searchAnimation = searchForm.animate([
              { transform: target + ' translate(' + (before.left - after.left) + 'px,' +
                  (before.top - after.top) + 'px) scaleX(' + (before.width / after.width) + ')' },
              { transform: target || 'none' }
            ], { duration: 280, easing: 'cubic-bezier(0.22, 1, 0.36, 1)' });
          }
        }
        function exitSearch() {
          search.blur();
          setSearchMode(false);
          var returnTarget = window.innerWidth <= 768 ? toggle : navbar.querySelector('.nav-brand');
          requestAnimationFrame(function () { returnTarget.focus({ preventScroll: true }); });
        }
        search.addEventListener('focus', function () { setSearchMode(true); });
        cancelSearch.addEventListener('click', exitSearch);
        document.addEventListener('pointerdown', function (event) {
          if (navbar.classList.contains('is-searching') && !navbar.contains(event.target)) {
            search.blur();
            setSearchMode(false);
          }
        });
        document.addEventListener('keydown', function (event) {
          if (event.key === 'Escape' && navbar.classList.contains('is-searching')) {
            event.preventDefault();
            exitSearch();
          }
        });
        window.addEventListener('resize', function () {
          if (searchAnimation) searchAnimation.cancel();
        });
      }
      var catalog = document.querySelector('.catalog-grid');
      if (search && catalog) {
        var items = catalog.querySelectorAll('.catalog-item');
        var empty = document.querySelector('.catalog-empty');
        var catalogSection = document.getElementById('catalog');
        var searchScrollTimer;
        var selectedCategory = 'all';
        var categoryFilters = document.querySelectorAll('[data-category-filter]');
        function filterCatalog() {
          var query = search.value.trim().toLowerCase();
          var visible = 0;
          items.forEach(function (item) {
            item.hidden = item.textContent.toLowerCase().indexOf(query) === -1 ||
              (selectedCategory !== 'all' && item.dataset.category !== selectedCategory);
            if (!item.hidden) visible += 1;
          });
          empty.hidden = visible > 0;
        }
        categoryFilters.forEach(function (button) {
          button.addEventListener('click', function () {
            selectedCategory = button.dataset.categoryFilter;
            categoryFilters.forEach(function (filter) {
              var active = filter === button;
              filter.classList.toggle('is-active', active);
              filter.setAttribute('aria-pressed', String(active));
            });
            filterCatalog();
          });
        });
        search.addEventListener('input', function () {
          filterCatalog();
          clearTimeout(searchScrollTimer);
          searchScrollTimer = setTimeout(function () {
            if (!catalogSection) return;
            catalogSection.scrollIntoView({
              block: 'start',
              behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth'
            });
          }, 120);
        });
      }
    })();
