'use strict';
/* Browser-only readings for the public interactive demo. No network or grill access. */
(() => {
  const presets = {
    smoke: {name:'Smoked chicken', grill:225, probe1:165, probe2:null},
    roast: {name:'Roast', grill:350, probe1:145, probe2:null},
    sear: {name:'Sear', grill:400, probe1:130, probe2:null}
  };
  let chosen = 'smoke';
  let minute = 9;
  let rows = [];
  let paused = false;
  let showEta = true;
  let gaugeTicks = true;
  let speed = 1;
  let started = Date.now() - 3 * 60 * 60 * 1000;
  function reading(m) {
    const cook = presets[chosen];
    const grill = 70 + (cook.grill + 5 - 70) * (1 - Math.exp(-m / 18)) + 2 * Math.sin(m / 5);
    const probe = 42 + (cook.probe1 + 5 - 42) * (1 - Math.exp(-m / 52));
    return {
      time: new Date(started + m * 60000).toISOString(),
      grill: Math.round(grill * 10) / 10,
      probe1: Math.round(probe * 10) / 10,
      probe2: null,
      pellets: Math.max(45, Math.round(94 - m * 0.12)),
      wifi: '-62 dBm',
      pi_temp: 91
    };
  }
  function reset() {
    minute = 9;
    started = Date.now() - 3 * 60 * 60 * 1000;
    rows = [];
    for (let i = 0; i <= minute; i++) rows.push(reading(i));
  }
  function prediction(field) {
    const cook = presets[chosen], current = rows[rows.length - 1][field], target = cook[field];
    if (!target || !current) return {state:'unavailable'};
    if (current >= target) return {state:'reached'};
    if (field !== 'grill' && rows[rows.length - 1].grill <= target + 5) return {state:'calculating'};
    const window = field === 'grill' ? 20 : 60;
    const points = rows.slice(-window - 1);
    const span = points.length - 1;
    if (span < (field === 'grill' ? 2 : 4)) return {state:'calculating'};
    const recent = points.slice(-13);
    if (recent[recent.length - 1][field] < recent[0][field] + (field === 'grill' ? 0.5 : 0.25)) return {state:'calculating'};
    const mx = span / 2, my = points.reduce((sum, row) => sum + row[field], 0) / points.length;
    let xy = 0, xx = 0;
    points.forEach((row, i) => { xy += (i-mx) * (row[field]-my); xx += (i-mx) ** 2; });
    const slope = xx ? xy / xx : 0;
    const remaining = slope > 0 ? (target-current) / slope : Infinity;
    if (slope < (field === 'grill' ? 0.1 : 0.02) || remaining < 0.5 || remaining > 1440) return {state:'calculating'};
    return {state:'estimate', minutes:Math.max(1, Math.round(remaining))};
  }
  function payload() {
    const cook = presets[chosen];
    return {
      latest: rows[rows.length - 1], history: rows.slice(-180), active_cook:cook,
      session_start:new Date(started).toISOString(), refresh_seconds:2,
      gauge_ticks:gaugeTicks, show_eta:showEta, stale:false, wifi_name:'Demo Wi-Fi',
      eta:showEta ? {grill:prediction('grill'), probe1:prediction('probe1'), probe2:{state:'unavailable'}} : {}
    };
  }
  // The real dashboard's fetch sees only in-memory sample readings.
  window.fetch = async () => ({ok:true, json:async () => payload()});
  reset();
  document.getElementById('demo-pause').addEventListener('click', event => {
    paused = !paused;
    event.currentTarget.textContent = paused ? 'Resume simulation' : 'Pause simulation';
  });
  document.getElementById('demo-reset').addEventListener('click', reset);
  document.getElementById('demo-speed').addEventListener('change', event => { speed = Number(event.target.value) || 1; });
  document.getElementById('demo-preset').addEventListener('change', event => { chosen = event.target.value; reset(); });
  document.getElementById('demo-eta').addEventListener('change', event => { showEta = event.target.checked; });
  document.getElementById('demo-ticks').addEventListener('change', event => { gaugeTicks = event.target.checked; });
  setInterval(() => {
    if (paused) return;
    for (let i = 0; i < speed; i++) { minute++; rows.push(reading(minute)); }
  }, 2000);
})();
