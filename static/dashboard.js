'use strict';
const $ = id => document.getElementById(id);
let previousSample = '';
let previousCook = '';
let currentHistory = [];
let refreshMs = 15000;
const colors = {grill:'#ffad48', probe1:'#69c9c0', probe2:'#9da8ff', pellets:'#a4dc74'};
const visible = {grill:true, probe1:true, probe2:true, pellets:true};
const dialAnimations = new WeakMap();
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
function animateDial(dial, amount) {
  const previous = parseFloat(dial.dataset.amount || '0');
  const active = dialAnimations.get(dial);
  if (active) cancelAnimationFrame(active);
  if (reducedMotion.matches) {
    dial.style.setProperty('--amount', amount);
    dial.dataset.amount = amount;
    return;
  }
  const started = performance.now();
  function frame(now) {
    const t = Math.min(1, (now - started) / 1100);
    const eased = 1 - Math.pow(1 - t, 3);
    dial.style.setProperty('--amount', (previous + (amount - previous) * eased).toFixed(4));
    if (t < 1) dialAnimations.set(dial, requestAnimationFrame(frame));
    else dial.dataset.amount = amount;
  }
  dialAnimations.set(dial, requestAnimationFrame(frame));
}
const fmt = value => value === null || value === undefined || !Number.isFinite(value) || value <= 0 ? '—' : String(Math.round(value));
function targetMarker(dial, target, max) {
  const svg = dial.querySelector('.target-overlay');
  svg.replaceChildren();
  if (typeof target !== 'number' || target <= 0 || target > max) return;
  const ns = 'http://www.w3.org/2000/svg';
  const angle = -135 + (target / max) * 270;
  const point = (radius, degrees) => {
    const radians = degrees * Math.PI / 180;
    return [100 + radius * Math.sin(radians), 100 - radius * Math.cos(radians)];
  };
  const start = Math.max(-135, angle - 4);
  const end = Math.min(135, angle + 4);
  const innerStart = point(82, start), outerStart = point(99, start);
  const outerEnd = point(99, end), innerEnd = point(82, end);
  const marker = document.createElementNS(ns, 'path');
  marker.setAttribute('d', 'M ' + innerStart.join(' ') + ' L ' + outerStart.join(' ') +
    ' A 99 99 0 0 1 ' + outerEnd.join(' ') + ' L ' + innerEnd.join(' ') +
    ' A 82 82 0 0 0 ' + innerStart.join(' ') + ' Z');
  marker.setAttribute('fill', '#b7f878');
  svg.appendChild(marker);
  const labelPoint = point(65, angle);
  const label = document.createElementNS(ns, 'text');
  label.setAttribute('x', labelPoint[0].toFixed(1));
  label.setAttribute('y', (labelPoint[1] + 4).toFixed(1));
  label.setAttribute('text-anchor', 'middle');
  label.textContent = String(Math.round(target));
  svg.appendChild(label);
}
function updateDial(name, value, target) {
  $(name + '-value').textContent = fmt(value);
  $(name + '-target').textContent = fmt(target);
  const dial = document.querySelector('[data-field="' + name + '"] .dial');
  const amount = value && value > 0 ? Math.min(value / 500, 1) : 0;
  animateDial(dial, amount);
  targetMarker(dial, target, 500);
  dial.classList.toggle('empty', !value || value <= 0);
}
function chart(rows, animate = true) {
  const svg = $('trend');
  const ns = 'http://www.w3.org/2000/svg';
  svg.replaceChildren();
  $('chart-tooltip').hidden = true;
  const add = (tag, attrs, parent = svg) => {
    const node = document.createElementNS(ns, tag);
    Object.entries(attrs).forEach(([k, v]) => node.setAttribute(k, String(v)));
    parent.appendChild(node);
    return node;
  };
  const temperatures = ['grill','probe1','probe2'].filter(name => visible[name]);
  const all = rows.flatMap(r => temperatures.map(name => r[name])).filter(v => v !== null && v > 0);
  if (!all.length && (!visible.pellets || !rows.some(r => r.pellets !== null && r.pellets >= 0))) {
    const label = add('text', {x: 400, y: 125, 'text-anchor': 'middle', fill: '#b6bec6'});
    label.textContent = rows.length ? 'Choose a line in the legend' : 'Waiting for this cook’s first reading';
    return;
  }
  const min = all.length ? Math.max(0, Math.floor(Math.min(...all) / 50) * 50 - 25) : 0;
  const max = all.length ? Math.max(min + 50, Math.ceil(Math.max(...all) / 50) * 50 + 25) : 500;
  const y = v => 220 - (v - min) / (max - min) * 190;
  const pelletY = v => 220 - Math.max(0, Math.min(100, v)) / 100 * 190;
  for (let n = 0; n <= 4; n++) {
    const value = Math.round(min + (max - min) * n / 4);
    const py = y(value);
    add('line', {x1: 45, y1: py, x2: 750, y2: py, stroke: '#3d454c', 'stroke-width': 1});
    const label = add('text', {x: 36, y: py + 4, 'text-anchor': 'end', fill: '#98a4ab', 'font-size': 12});
    label.textContent = temperatures.length ? value : '';
  }
  const first = new Date(rows[0].time).getTime();
  const last = new Date(rows[rows.length - 1].time).getTime();
  const span = Math.max(1, last - first);
  const x = r => 45 + (new Date(r.time).getTime() - first) / span * 705;
  if (visible.pellets) {
    for (const value of [0,25,50,75,100]) {
      const label = add('text', {x:790, y:pelletY(value)+4, 'text-anchor':'end', fill:'#9eba99', 'font-size':12});
      label.textContent = value + '%';
    }
  }
  for (const [field, color] of Object.entries(colors)) {
    if (!visible[field]) continue;
    let points = [];
    const flush = () => {
      if (points.length > 1) {
        const line = add('polyline', {points: points.join(' '), fill:'none', stroke:color, 'stroke-width':3, 'stroke-linecap':'round', 'stroke-linejoin':'round'});
        if (animate && !reducedMotion.matches) {
          const length = line.getTotalLength();
          line.style.strokeDasharray = length;
          line.style.strokeDashoffset = length;
          line.animate([{strokeDashoffset:length}, {strokeDashoffset:0}], {duration:950, easing:'ease-out', fill:'forwards'});
        }
        const hit = add('polyline', {points:points.join(' '), fill:'none', stroke:'transparent',
          'stroke-width':14, 'pointer-events':'stroke'});
        hit.addEventListener('pointermove', event => {
          const samples = rows.filter(r => r[field] !== null && (field === 'pellets' ? r[field] >= 0 : r[field] > 0));
          const plotX = (event.clientX - svg.getBoundingClientRect().left) * 800 / svg.getBoundingClientRect().width;
          const nearest = samples.reduce((best, row) => Math.abs(x(row)-plotX) < Math.abs(x(best)-plotX) ? row : best);
          const titles = {grill:'Grill', probe1:'Probe 1', probe2:'Probe 2', pellets:'Pellets'};
          const tip = $('chart-tooltip');
          tip.textContent = titles[field] + ': ' + (field === 'pellets' ? Math.round(nearest[field]) + '%' : Math.round(nearest[field]) + '°F') +
            ' · ' + new Date(nearest.time).toLocaleTimeString([], {hour:'numeric', minute:'2-digit'});
          const card = tip.parentElement;
          const bounds = card.getBoundingClientRect();
          tip.hidden = false;
          tip.style.left = Math.max(8, Math.min(card.clientWidth - tip.offsetWidth - 8, event.clientX - bounds.left + 12)) + 'px';
          tip.style.top = Math.max(8, event.clientY - bounds.top - 44) + 'px';
        });
        hit.addEventListener('pointerleave', () => { $('chart-tooltip').hidden = true; });
      }
      points = [];
    };
    rows.forEach(r => { if (r[field] !== null && (field === 'pellets' ? r[field] >= 0 : r[field] > 0)) points.push(x(r).toFixed(1) + ',' + (field === 'pellets' ? pelletY(r[field]) : y(r[field])).toFixed(1)); else flush(); });
    flush();
  }
  const start = add('text', {x: 45, y: 246, fill:'#98a4ab', 'font-size':12});
  start.textContent = new Date(rows[0].time).toLocaleTimeString([], {hour:'numeric', minute:'2-digit'});
  const end = add('text', {x: 750, y: 246, 'text-anchor':'end', fill:'#98a4ab', 'font-size':12});
  end.textContent = new Date(rows[rows.length - 1].time).toLocaleTimeString([], {hour:'numeric', minute:'2-digit'});
}
async function refresh() {
  try {
    const response = await fetch('api/readings', {cache:'no-store'});
    if (!response.ok) throw new Error('Readings unavailable');
    const data = await response.json();
    refreshMs = Math.max(2000, Math.min(60000, (data.refresh_seconds || 15) * 1000));
    $('live-status').textContent = data.stale ? 'Readings delayed' : 'Live';
    $('live-status').classList.toggle('stale', data.stale);
    $('wifi-name').textContent = data.wifi_name || 'Not connected';
    const cook = data.active_cook;
    $('cook-name').textContent = cook ? cook.name : 'No cook preset active';
    $('cook-targets').textContent = cook ? 'Grill ' + cook.grill + '°F' +
      (cook.probe1 ? ' · Probe 1 ' + cook.probe1 + '°F' : '') +
      (cook.probe2 ? ' · Probe 2 ' + cook.probe2 + '°F' : '') :
      'Choose a saved cook to set its temperature targets.';
    if (!data.latest) { $('sample-time').textContent = 'Waiting for the collector'; return; }
    const r = data.latest;
    $('sample-time').textContent = 'Last sample: ' + new Date(r.time).toLocaleString();
    const cookSignature = (cook ? [cook.name,cook.grill,cook.probe1,cook.probe2].join('|') : '') + '|' + (data.session_start || '');
    if (r.time === previousSample && cookSignature === previousCook) return;
    previousSample = r.time;
    previousCook = cookSignature;
    for (const name of ['grill','probe1','probe2']) updateDial(name, r[name], cook ? cook[name] : null);
    $('pellets').textContent = fmt(r.pellets) + '%';
    $('pellet-fill').style.width = Math.max(0, Math.min(100, r.pellets || 0)) + '%';
    $('wifi').textContent = r.wifi || '—';
    $('pi-temp').textContent = fmt(r.pi_temp) + '°F';
    currentHistory = data.history;
    chart(currentHistory);
  } catch (_) {
    $('live-status').textContent = 'Connection lost';
    $('live-status').classList.add('stale');
  } finally {
    setTimeout(refresh, refreshMs);
  }
}
refresh();

try {
for (const name of Object.keys(colors)) {
  try {
    const saved = localStorage.getItem('traeger-ring-' + name);
    if (/^#[0-9a-f]{6}$/i.test(saved || '')) colors[name] = saved;
  } catch (_) { /* Storage may be unavailable in private browsing. */ }
  document.documentElement.style.setProperty('--' + name + '-color', colors[name]);
  const picker = document.querySelector('[data-color="' + name + '"]');
  picker.value = colors[name];
  const colorButton = name === 'pellets' ? document.querySelector('.pellet-color-button') :
    document.querySelector('[data-field="' + name + '"] .dial');
  if (!picker || !colorButton) throw new Error('Missing color control: ' + name);
  colorButton.addEventListener('click', () => picker.click());
  picker.addEventListener('input', () => {
    colors[name] = picker.value;
    document.documentElement.style.setProperty('--' + name + '-color', colors[name]);
    try { localStorage.setItem('traeger-ring-' + name, colors[name]); } catch (_) {}
    if (currentHistory.length) chart(currentHistory, false);
  });
}
} catch (error) {
  document.querySelector(".color-hint").textContent = "Color controls are temporarily unavailable.";
  console.error("Traeger color controls:", error);
}

for (const button of document.querySelectorAll('.legend-toggle')) {
  const name = button.dataset.series;
  try {
    visible[name] = localStorage.getItem('traeger-series-' + name) !== 'hidden';
  } catch (_) {}
  button.setAttribute('aria-pressed', String(visible[name]));
  button.addEventListener('click', () => {
    visible[name] = !visible[name];
    button.setAttribute('aria-pressed', String(visible[name]));
    try { localStorage.setItem('traeger-series-' + name, visible[name] ? 'shown' : 'hidden'); } catch (_) {}
    chart(currentHistory, false);
  });
}
