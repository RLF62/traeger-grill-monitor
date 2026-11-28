const slider = document.getElementById('led-brightness-slider');
const value = document.getElementById('led-brightness-value');
if (slider && value) slider.addEventListener('input', () => { value.value = `${slider.value}%`; });
