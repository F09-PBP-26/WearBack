/* Preview interactions only. No reviews are submitted or persisted yet. */
document.querySelectorAll('[data-review-card]').forEach((card) => {
  const stars = [...card.querySelectorAll('.review-star')];
  const updateStars = () => {
    const selected = card.querySelector('input[type="radio"]:checked');
    stars.forEach((star) => {
      star.classList.toggle('is-selected', Number(star.querySelector('input').value) <= Number(selected?.value || 0));
    });
  };
  card.querySelectorAll('input[type="radio"]').forEach((input) => {
    input.addEventListener('change', updateStars);
  });
  const comment = card.querySelector('textarea');
  const updateCount = () => {
    card.querySelector('[data-review-count]').textContent = `${comment.value.length} / 500`;
  };
  comment.addEventListener('input', updateCount);
  updateStars();
  updateCount();
});
