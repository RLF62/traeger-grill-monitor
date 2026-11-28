document.querySelectorAll('.pellet-capture').forEach(button => {
  button.addEventListener('click', () => {
    const input = document.getElementById(button.dataset.target);
    if (input) input.value = button.dataset.reading;
  });
});
