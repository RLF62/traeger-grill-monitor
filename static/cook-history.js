'use strict';
const svg = document.getElementById('saved-chart');
const status = document.getElementById('saved-chart-status');
const ns = 'http://www.w3.org/2000/svg';
function add(tag, attributes) {
  const node = document.createElementNS(ns, tag);
  for (const [name, value] of Object.entries(attributes)) node.setAttribute(name, String(value));
  svg.appendChild(node);
  return node;
}
async function render() {
  try {
    const response = await fetch(svg.dataset.url, {cache:'no-store'});
    if (!response.ok) throw new Error('Could not load this session');
    const data = await response.json();
    const rows = data.rows;
    if (!rows.length) { status.textContent = 'No sensor samples were recorded during this cook.'; return; }
    const unit = data.temperature_unit === 'C' ? 'C' : 'F';
    const display = value => unit === 'C' ? Math.round((value - 32) * 5 / 9) : Math.round(value);
    const values = rows.flatMap(row => [row.grill,row.probe1,row.probe2]).filter(value => value !== null && value > 0);
    const low = values.length ? Math.max(0, Math.floor(Math.min(...values) / 25) * 25 - 10) : 0;
    const high = values.length ? Math.max(low + 25, Math.ceil(Math.max(...values) / 25) * 25 + 10) : 500;
    const start = new Date(rows[0].time).getTime();
    const span = Math.max(1, new Date(rows[rows.length - 1].time).getTime() - start);
    const x = row => 45 + (new Date(row.time).getTime() - start) / span * 705;
    const y = value => 220 - (value - low) / (high - low) * 190;
    for (let n=0; n<=4; n++) {
      const value = low + (high - low) * n / 4;
      add('line', {x1:45,y1:y(value),x2:750,y2:y(value),stroke:'#3d454c'});
      add('text', {x:38,y:y(value)+4,'text-anchor':'end',fill:'#aab7c0','font-size':12}).textContent = values.length ? display(value) : '';
      add('text', {x:790,y:220-n*47.5+4,'text-anchor':'end',fill:'#a9ca8e','font-size':12}).textContent = n*25+'%';
    }
    for (const [name,color] of Object.entries({grill:'#ffad48',probe1:'#69c9c0',probe2:'#9da8ff',pellets:'#a4dc74'})) {
      let part=[];
      const flush=()=>{if(part.length>1)add('polyline',{points:part.join(' '),fill:'none',stroke:color,'stroke-width':3,'stroke-linecap':'round','stroke-linejoin':'round'});part=[];};
      for (const row of rows) {
        const value=row[name];
        if (value===null || (name==='pellets' ? value<0 : value<=0)) {flush();continue;}
        const py=name==='pellets' ? 220-Math.max(0,Math.min(100,value))*1.9 : y(value);
        part.push(x(row).toFixed(1)+','+py.toFixed(1));
      }
      flush();
    }
    status.textContent = rows.length+' plotted samples · Temperature in °'+unit+' (left scale); pellets in % (right scale).';
    svg.addEventListener('pointermove', event => {
      const rect=svg.getBoundingClientRect();
      const px=(event.clientX-rect.left)*800/rect.width;
      const row=rows.reduce((best,item)=>Math.abs(x(item)-px)<Math.abs(x(best)-px)?item:best);
      const value=name=>row[name]===null || row[name]<=0?'—':display(row[name])+'°'+unit;
      status.textContent=new Date(row.time).toLocaleString()+' · Grill '+value('grill')+' · Probe 1 '+value('probe1')+' · Probe 2 '+value('probe2')+' · Pellets '+(row.pellets===null?'—':Math.round(row.pellets)+'%');
    });
  } catch (error) { status.textContent = error.message; }
}
render();
