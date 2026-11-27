'use strict';
const $ = (id) => document.getElementById(id);
const escape = (value) => String(value).replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const names = {fixed:'Fixed',inventory:'Inventory-aware',signal:'Signal-aware',touch:'At touch',through:'Trade-through',queue:'Queue proxy',majority:'Majority baseline',imbalance:'Imbalance rule',logistic:'Logistic regression'};
const money = (n) => `${n < 0 ? '−' : ''}$${Math.abs(n).toFixed(3)}`;
const number = (n, digits=3) => Number(n).toFixed(digits);
let research, exchange, position = 0, timer = null, busy = false, pendingOrder = null;
const cancelRequests = new Map();

function message(text, error=false) {
  $('message').hidden = false;
  $('message').className = error ? 'error' : '';
  $('message').textContent = text;
}

async function api(path, body) {
  const response = await fetch(path, body === undefined ? {} : {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const data = await response.json();
  if (!response.ok) {const error = new Error(data.error || `Request failed (${response.status})`);error.status=response.status;throw error;}
  return data;
}

async function task(action) {
  if (busy) return;
  busy = true;
  document.body.classList.add('busy');
  document.querySelectorAll('button, input, select').forEach((e) => {e.disabled = true;});
  try { await action(); }
  catch (error) { message(error.message, true); }
  finally {
    busy = false;
    document.body.classList.remove('busy');
    document.querySelectorAll('button, input, select').forEach((e) => {e.disabled = false;});
  }
}

function stopReplay() {
  clearInterval(timer); timer = null; $('play-button').textContent = 'Play';
  $('play-button').setAttribute('aria-label','Play replay');
}

function selectedStrategy() {
  return research.strategies.find((s) => s.strategy === $('strategy-select').value && s.fill === $('fill-select').value);
}

function metric(label, value, detail, className='') {
  return `<div class="metric"><span>${escape(label)}</span><strong class="${className}">${escape(value)}</strong><small>${escape(detail)}</small></div>`;
}

function renderResearch(data) {
  stopReplay(); research = data; position = data.frames.length - 1;
  $('replay-slider').max = position; $('replay-slider').value = position;
  $('source-label').textContent = data.synthetic ? 'Synthetic demo · seed ' + data.settings.seed : 'Imported CSV · ' + data.audit.symbol;
  $('dataset-label').textContent = `${data.audit.rows.toLocaleString()} events / ${Object.keys(data.audit.sessions).length} sessions`;
  for (const [key, value] of Object.entries(data.settings)) $('settings-form').elements.namedItem(key).value = value;
  $('settings-form').elements.namedItem('seed').title = data.synthetic ? 'Controls synthetic data generation' : 'Controls model randomness; imported data remains the same';
  $('prediction-table').innerHTML = Object.entries(data.predictions).map(([name, m]) => `<tr><td>${names[name]}</td><td>${number(m.macro_f1)}</td><td>${number(m.log_loss)}</td><td>${number(m.brier)}</td><td>${number(m.calibration_error)}</td></tr>`).join('');
  const m = data.predictions.logistic;
  $('class-results').innerHTML = `<p>Logistic regression · C = ${data.selected_C}. Confusion matrix rows = actual; columns = predicted.</p><div class="table-wrap"><table><thead><tr><th>Actual</th><th>Down</th><th>Flat</th><th>Up</th></tr></thead><tbody>${m.confusion.map((row,i) => `<tr><td>${data.labels[i]}</td>${row.map((v) => `<td>${v}</td>`).join('')}</tr>`).join('')}</tbody></table></div><div class="table-wrap"><table><thead><tr><th>Class</th><th>Precision</th><th>Recall</th><th>F1</th><th>Support</th></tr></thead><tbody>${data.labels.map((label) => {const c=m.classes[label];return `<tr><td>${label}</td><td>${number(c.precision)}</td><td>${number(c.recall)}</td><td>${number(c['f1-score'])}</td><td>${c.support}</td></tr>`;}).join('')}</tbody></table></div><p>Confidence calibration · weighted absolute confidence–accuracy gap across five bins.</p><div class="table-wrap"><table><thead><tr><th>Mean confidence</th><th>Accuracy</th><th>Count</th></tr></thead><tbody>${m.calibration.map((b) => `<tr><td>${number(b.confidence)}</td><td>${number(b.accuracy)}</td><td>${b.count}</td></tr>`).join('')}</tbody></table></div>`;
  $('method-content').innerHTML = `<div class="split-strip">${Object.entries(data.splits).map(([name,sessions]) => `<span>${escape(name)} / ${sessions.length} sessions / ${data.sample_counts[name]} labels</span>`).join('')}</div><p>Features: spread, depth imbalance, 1- and 5-event returns, 10-event trailing volatility and signed trade quantity. Standardization uses training data only. Labels stay within sessions; horizons overlapping a split boundary are purged.</p><p>Logistic C selected on validation log loss from 0.1, 1 and 10. Test sessions: ${escape(data.splits.test.join(', '))}. The last horizon is excluded from prediction scoring.</p><p>Touch: an observed trade at or beyond your quote. Through: an observed trade strictly beyond it. Queue proxy: a qualifying trade must also exceed displayed same-side depth. All are approximations.</p><ul>${data.limitations.map((l) => `<li>${escape(l)}</li>`).join('')}</ul><p>Data audit: ${data.audit.large_gaps} intervals exceed 5× the median (${data.audit.typical_interval_ms} ms). No missing values, duplicate timestamps or crossed books accepted. SHA-256: <code>${data.dataset_sha256}</code>.</p>`;
  renderStrategy();
}

function renderStrategy() {
  if (!research) return;
  const s = selectedStrategy();
  $('strategy-metrics').innerHTML = metric('Net simulated P&L',money(s.pnl),'Fees included',s.pnl < 0 ? 'negative' : 'positive') + metric('Max drawdown',money(s.drawdown),'Across held-out sessions') + metric('Executed quotes',s.fills.toLocaleString(),`${number(s.fill_rate*100,1)}% of eligible quotes`) + metric('Peak inventory',`${s.max_inventory} units`,`Limit ${research.settings.position_limit}`);
  $('sensitivity-table').innerHTML = research.strategies.map((row) => `<tr class="${row === s ? 'selected' : ''}"><td>${names[row.strategy]}</td><td>${names[row.fill]}</td><td class="${row.pnl<0?'negative':'positive'}">${money(row.pnl)}</td><td>${money(row.drawdown)}</td><td>${row.fills}</td><td>${row.max_inventory}</td></tr>`).join('');
  renderFrame();
}

function drawEquity(s) {
  const values = s.curve.map((p) => p.equity);
  let min = Math.min(0,...values), max = Math.max(0,...values);
  if (max-min < .02) {min -= .01;max += .01;}
  const margin = (max-min) * .1; min -= margin; max += margin;
  const x = (i) => 67 + i / Math.max(1,values.length-1) * 815;
  const y = (v) => 201 - (v-min)/(max-min)*178;
  const grid = [0,.25,.5,.75,1].map((p) => {const value = min+(max-min)*p;return `<line class="chart-grid" x1="67" y1="${y(value)}" x2="882" y2="${y(value)}"/><text class="chart-label" x="54" y="${y(value)+4}" text-anchor="end">${value.toFixed(2)}</text>`;}).join('');
  const step = Math.max(1,Math.floor(values.length/1100));
  const visible = [];
  for (let i=0;i<=position;i+=step) visible.push([i,values[i]]);
  if (!visible.length || visible[visible.length-1][0] !== position) visible.push([position,values[position]]);
  const line = visible.map(([i,v],n) => `${n?'L':'M'}${x(i).toFixed(2)},${y(v).toFixed(2)}`).join(' ');
  $('equity-chart').innerHTML = `${grid}<line x1="67" x2="882" y1="${y(0)}" y2="${y(0)}" stroke="#a5b7ad" stroke-dasharray="4 4"/><path class="chart-line" d="${line}"/><line class="chart-cursor" x1="${x(position)}" x2="${x(position)}" y1="20" y2="205"/><circle cx="${x(position)}" cy="${y(values[position])}" r="3.5" fill="#146a55"/><text class="chart-label" x="67" y="231">Event 1</text><text class="chart-label" x="882" y="231" text-anchor="end">Event ${values.length}</text>`;
}

function renderFrame() {
  if (!research) return;
  const s = selectedStrategy(), frame = research.frames[position], p = s.curve[position];
  drawEquity(s);
  $('event-label').textContent = `${position+1} / ${research.frames.length}`;
  $('book-time').textContent = frame.session;
  $('book-summary').innerHTML = `<span class="positive">Bid ${frame.bid.toLocaleString()}</span><span>Spread ${frame.ask-frame.bid} ticks</span><span class="negative">Ask ${frame.ask.toLocaleString()}</span>`;
  const total = frame.bid_size+frame.ask_size;
  const bw = 182*frame.bid_size/total, aw = 182*frame.ask_size/total;
  $('depth-chart').innerHTML = `<line x1="210" y1="14" x2="210" y2="79" stroke="#dce4e1"/><rect x="${200-bw}" y="25" width="${bw}" height="28" rx="2" fill="#448d70"/><rect x="220" y="25" width="${aw}" height="28" rx="2" fill="#ce857b"/><text class="chart-label" x="200" y="76" text-anchor="end">${frame.bid_size} bid units</text><text class="chart-label" x="220" y="76">${frame.ask_size} ask units</text>`;
  $('probability-bars').innerHTML = frame.probabilities ? frame.probabilities.map((value,i) => `<div class="prob-row"><span>${research.labels[i]}</span><div class="prob-track"><svg viewBox="0 0 100 7" preserveAspectRatio="none" aria-hidden="true"><rect width="${value*100}" height="7" fill="${i===0?'#ce857b':i===1?'#9aaba3':'#448d70'}"/></svg></div><span>${number(value*100,0)}%</span></div>`).join('') : '<p class="muted">Outside the scored feature window.</p>';
  $('position-label').textContent = `Inventory ${p.inventory} units · session cash ${money(p.cash)} · cumulative P&L ${money(p.equity)} · t = ${frame.timestamp} ms`;
  $('curve-caption').textContent = `${names[s.strategy]} / ${names[s.fill]} · USD`;
}

function empty(columns, text) { return `<tr><td colspan="${columns}" class="empty">${escape(text)}</td></tr>`; }

function renderExchange(data) {
  exchange = data;
  $('exchange-sequence').textContent = `Command sequence ${data.sequence}`;
  $('exchange-book').innerHTML = ['bids','asks'].map((side) => `<div class="panel"><h3 class="${side==='bids'?'positive':'negative'}">${side==='bids'?'Bids':'Asks'}</h3><div class="table-wrap"><table><thead><tr><th>Price (ticks)</th><th>Quantity</th></tr></thead><tbody>${data[side].slice(0,10).map((l) => `<tr><td>${l.price}</td><td>${l.quantity}</td></tr>`).join('')||empty(2,'No resting orders')}</tbody></table></div></div>`).join('');
  $('orders-table').innerHTML = data.orders.map((o) => `<tr><td>${escape(o.order_id)}</td><td>${escape(o.participant)}</td><td>${o.side}</td><td>${o.price}</td><td>${o.quantity}</td><td><button class="cancel" data-cancel="${escape(o.order_id)}">Cancel</button></td></tr>`).join('') || empty(6,'Submit a limit order to start.');
  $('trades-table').innerHTML = data.trades.slice(-50).reverse().map((t) => `<tr><td>${t.trade_id}</td><td>${escape(t.buyer)}</td><td>${escape(t.seller)}</td><td>${t.price}</td><td>${t.quantity}</td></tr>`).join('') || empty(5,'No executions yet.');
  $('balances-table').innerHTML = Object.entries(data.balances).map(([participant,b]) => `<tr><td>${escape(participant)}</td><td>${b.inventory}</td><td>${b.cash.toLocaleString()}</td></tr>`).join('') || empty(3,'Balances appear after a trade.');
}

async function loadHistory() {
  const history = await api('/api/history');
  $('history-table').innerHTML = history.map((r) => {const strategy = r.strategies.find((s) => s.strategy === 'signal' && s.fill === 'through');return `<tr><td>${escape(new Date(r.timestamp).toLocaleString())}</td><td title="${escape(r.dataset_sha256)}">${escape(r.source)} / ${escape(r.dataset_sha256.slice(0,8))}</td><td>${r.settings.seed}</td><td>${r.settings.horizon}</td><td>${r.settings.fee_bps}</td><td>${r.settings.latency}</td><td>${number(r.predictions.logistic.macro_f1)}</td><td>${money(strategy.pnl)}</td></tr>`;}).join('') || empty(8,'No experiments yet.');
}

document.querySelectorAll('.tab').forEach((button) => button.addEventListener('click', () => {
  stopReplay();
  document.querySelectorAll('.tab').forEach((tab) => {const active = tab === button;tab.classList.toggle('active',active);tab.setAttribute('aria-pressed',String(active));});
  ['research','exchange','history'].forEach((name) => {$(name+'-view').hidden = name !== button.dataset.view;});
  if (button.dataset.view === 'exchange') task(async () => renderExchange(await api('/api/exchange')));
  if (button.dataset.view === 'history') task(loadHistory);
}));
$('settings-form').addEventListener('submit',(event) => {
  event.preventDefault(); stopReplay();
  const settings = Object.fromEntries([...new FormData(event.target)].map(([key,value]) => [key,Number(value)]));
  task(async () => {renderResearch(await api('/api/run', settings));message('Experiment complete. Results and settings saved to the local log.');});
});
$('demo-button').addEventListener('click',() => task(async () => {renderResearch(await api('/api/demo',{}));message('Synthetic demo loaded.');}));
$('csv-file').addEventListener('change',(event) => {
  const file = event.target.files[0]; if (!file) return;
  task(async () => {
    if (file.size > 7_000_000) throw new Error('CSV must be smaller than 7 MB before JSON encoding.');
    renderResearch(await api('/api/import',{csv:await file.text()}));
    message('CSV validated and imported. Data stays on this computer.');
  }).finally(() => {event.target.value='';});
});
for (const id of ['strategy-select','fill-select']) $(id).addEventListener('change', renderStrategy);
$('replay-slider').addEventListener('input',(event) => {position=Number(event.target.value);renderFrame();});
$('play-button').addEventListener('click',() => {
  if (!research) return;
  if (timer) {stopReplay();return;}
  if (position >= research.frames.length-1) position = 0;
  $('play-button').textContent='Pause'; $('play-button').setAttribute('aria-label','Pause replay');
  timer=setInterval(() => {if (busy) return;position=Math.min(position+3,research.frames.length-1);$('replay-slider').value=position;renderFrame();if(position>=research.frames.length-1)stopReplay();},100);
});
$('order-form').addEventListener('submit',(event) => {
  event.preventDefault();
  const values = Object.fromEntries(new FormData(event.target));
  task(async () => {
    if (!pendingOrder) {
      const id=crypto.randomUUID();
      pendingOrder={...values,price:Number(values.price),quantity:Number(values.quantity),type:'order',request_id:id,order_id:id.slice(0,8)};
    }
    let data;
    try {data=await api('/api/command',pendingOrder);}
    catch(error) {
      if(error.status && error.status<500)pendingOrder=null;
      else error.message+=' The order may have persisted. Submit again to retry the original saved order; keep this page open.';
      throw error;
    }
    pendingOrder=null;
    renderExchange(data.state);
    message(`Order accepted at sequence ${data.result.sequence}. ${data.result.trades.length} trades, ${data.result.resting} resting, ${data.result.cancelled} cancelled.`);
  });
});
$('orders-table').addEventListener('click',(event) => {
  const button=event.target.closest('[data-cancel]'); if(!button)return;
  const order=exchange.orders.find((o)=>o.order_id===button.dataset.cancel);
  task(async () => {
    if(!cancelRequests.has(order.order_id))cancelRequests.set(order.order_id,crypto.randomUUID());
    const data=await api('/api/command',{request_id:cancelRequests.get(order.order_id),type:'cancel',order_id:order.order_id,participant:order.participant});
    cancelRequests.delete(order.order_id);renderExchange(data.state);message('Order cancelled.');
  });
});
$('snapshot-button').addEventListener('click',()=>task(async()=>{const result=await api('/api/snapshot',{});message(`Snapshot saved at command ${result.sequence}.`);}));
$('flow-button').addEventListener('click',()=>task(async()=>{const result=await api('/api/simulate',{});renderExchange(result.state);message(`${result.commands} commands from four seeded simulated participants processed and journaled.`);}));
$('recover-button').addEventListener('click',()=>task(async()=>{const result=await api('/api/recover',{});renderExchange(result.state);message(result.identical?'Recovery verified: book, trades and balances match.':'Recovered persisted state differs from memory.',!result.identical);}));
$('refresh-history').addEventListener('click',()=>task(loadHistory));
task(async()=>{renderResearch(await api('/api/research'));});
