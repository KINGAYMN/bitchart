(function(){
const startBtn = document.getElementById('startBtn');
const symbolInput = document.getElementById('symbol');
const wsStatus = document.getElementById('wsStatus');
const apiStatus = document.getElementById('apiStatus');
const signalsEl = document.getElementById('signals');

let ws=null;
let lastSentClose=null;
const BACKEND_API = (location.hostname === 'localhost' || location.hostname === '127.0.0.1') ? 'http://localhost:8000' : (location.origin.replace(/^http/, 'http'));

function addSignalEl(text, cls){
  const d = document.createElement('div');
  d.className = 'signal ' + cls;
  d.innerHTML = `<div>${text}</div><div class="meta">${new Date().toLocaleString()}</div>`;
  signalsEl.prepend(d);
}

// Build Binance kline websocket for 1m candles
function wsUrlFor(symbol){
  return `wss://stream.binance.com:9443/ws/${symbol.toLowerCase()}@kline_1m`;
}

async function postToBackend(payload){
  try{
    const res = await fetch(BACKEND_API + '/api/price', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify(payload)
    });
    if(!res.ok) throw new Error('backend error '+res.status);
    apiStatus.textContent = 'متصل';
    const data = await res.json();
    // data example: { signal: 'BUY', details: {...} }
    const cls = data.signal === 'BUY' ? 'buy' : (data.signal === 'SELL' ? 'sell' : 'wait');
    addSignalEl(`${payload.symbol} @ ${payload.close} → ${data.signal} — ${data.reasons.join(' | ')}`, cls);
  }catch(err){
    apiStatus.textContent = 'خطأ';
    addSignalEl('خطأ في الاتصال بالخادم الخلفي: '+err.message, 'wait');
    console.error(err);
  }
}

startBtn.addEventListener('click', ()=>{
  const symbol = (symbolInput.value||'').trim();
  if(!symbol){ alert('أدخل رمز العملة'); return; }
  if(ws){ try{ ws.close(); }catch(e){} ws=null; wsStatus.textContent='مغلق'; }
  const url = wsUrlFor(symbol);
  ws = new WebSocket(url);
  ws.onopen = ()=>{ wsStatus.textContent='متصل'; addSignalEl('WebSocket مفتوح لـ '+symbol, 'wait'); };
  ws.onclose = ()=>{ wsStatus.textContent='مغلق'; addSignalEl('WebSocket مغلق', 'wait'); };
  ws.onerror = (e)=>{ wsStatus.textContent='خطأ'; addSignalEl('خطأ في WebSocket', 'wait'); console.error(e); };
  ws.onmessage = (evt)=>{
    try{
      const msg = JSON.parse(evt.data);
      if(!msg.k) return;
      const k = msg.k;
      if(!k.x) return; // only closed candles
      const close = parseFloat(k.c);
      lastSentClose = close;
      const payload = { symbol: symbol.toUpperCase(), close: close, timestamp: k.T, raw: k };
      postToBackend(payload);
    }catch(err){
      console.error('parse error', err);
    }
  };
});
})();