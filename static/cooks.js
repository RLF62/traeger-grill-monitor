document.querySelectorAll('[data-confirm-remove]').forEach(button => {
  button.addEventListener('click', event => {
    if (!window.confirm('Remove this saved cook?')) event.preventDefault();
  });
});
