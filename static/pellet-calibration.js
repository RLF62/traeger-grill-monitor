const captureButtons = document.querySelectorAll('.pellet-capture');
const toggle = document.getElementById('pellet-live-toggle');
const rawDisplay = document.getElementById('pellet-raw');
const percentDisplay = document.getElementById('pellet-percent');
const status = document.getElementById('pellet-live-status');
let running = false;
let timer = null;
let request = null;

captureButtons.forEach(button => {
  button.addEventListener('click', () => {
    const input = document.getElementById(button.dataset.target);
    if (input && button.dataset.reading) input.value = button.dataset.reading;
  });
});

function showReading(reading) {
  const raw = reading.raw;
  const valid = Number.isInteger(raw) && raw >= 0;
  rawDisplay.textContent = valid ? String(raw) : 'Unavailable';
  percentDisplay.textContent = reading.percent === null ? 'Sensor unavailable' : `${reading.percent}%`;
  captureButtons.forEach(button => {
    button.disabled = !valid;
    button.dataset.reading = valid ? String(raw) : '';
  });
}

async function poll() {
  if (!running) return;
  request = new AbortController();
  try {
    const response = await fetch(toggle.dataset.url, {cache: 'no-store', signal: request.signal});
    if (!response.ok) throw new Error('Sensor request failed');
    const reading = await response.json();
    if (running) {
      showReading(reading);
      status.textContent = 'Live sensor readings active.';
    }
  } catch (error) {
    if (running && error.name !== 'AbortError') status.textContent = 'Live reading failed; retrying.';
  } finally {
    request = null;
    if (running) timer = setTimeout(poll, 1000);
  }
}

if (toggle) toggle.addEventListener('click', () => {
  running = !running;
  toggle.textContent = running ? 'Stop live readings' : 'Start live readings';
  toggle.setAttribute('aria-pressed', String(running));
  if (running) {
    status.textContent = 'Starting live sensor readings…';
    poll();
  } else {
    clearTimeout(timer);
    if (request) request.abort();
    status.textContent = 'Live readings stopped. Normal sampling continues.';
  }
});
