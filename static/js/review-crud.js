(() => {
  const message = document.querySelector('[data-review-message]');
  const announce = (text) => { if (message) message.textContent = text; };
  const initialize = () => {
    document.querySelectorAll('[data-review-card]').forEach((card) => {
      const update = () => {
        const rating = Number(card.querySelector('input[name="rating"]:checked')?.value || 0);
        card.querySelectorAll('.review-star').forEach((star) => {
          star.classList.toggle('is-selected', Number(star.querySelector('input').value) <= rating);
        });
        const comment = card.querySelector('textarea');
        const count = card.querySelector('[data-review-count]');
        if (comment && count) count.textContent = `${comment.value.length} / 500`;
      };
      card.addEventListener('input', update);
      update();
    });
  };
  const readResponse = async (response) => {
    if (response.redirected || !response.headers.get('content-type')?.includes('application/json')) {
      throw new Error('Your session may have expired. Refresh the page and sign in again.');
    }
    return response.json();
  };
  document.addEventListener('submit', async (event) => {
    const form = event.target.closest('[data-review-form]');
    if (!form) return;
    event.preventDefault();
    if (form.hasAttribute('data-confirm-delete') && !window.confirm('Delete this review?')) return;
    const buttons = [...form.querySelectorAll('button')];
    buttons.forEach((button) => { button.disabled = true; });
    announce('Saving…');
    try {
      const response = await fetch(form.action, {
        method: 'POST', body: new FormData(form), credentials: 'same-origin',
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
      });
      const data = await readResponse(response);
      if (data.html) {
        document.querySelector('#review-editor').innerHTML = data.html;
        initialize();
      }
      announce(response.ok ? data.message : 'Please check the form errors and try again.');
    } catch (error) { announce(error.message || 'Unable to save. Please try again.'); }
    finally { buttons.forEach((button) => { button.disabled = false; }); }
  });
  let filterRequest;
  const loadResults = async (url) => {
    filterRequest?.abort();
    filterRequest = new AbortController();
    announce('Loading reviews…');
    try {
      const response = await fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' }, signal: filterRequest.signal });
      const data = await readResponse(response);
      if (!response.ok) throw new Error('Unable to load reviews.');
      document.querySelector('#review-results').innerHTML = data.html;
      window.history.replaceState(null, '', url);
      announce('Reviews updated.');
    } catch (error) { if (error.name !== 'AbortError') announce(error.message); }
  };
  document.querySelector('[data-review-filters]')?.addEventListener('submit', (event) => {
    event.preventDefault();
    loadResults(`${window.location.pathname}?${new URLSearchParams(new FormData(event.target))}`);
  });
  document.addEventListener('click', (event) => {
    const link = event.target.closest('[data-review-page]');
    if (!link || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    loadResults(link.href);
  });
  initialize();
})();
