(function(){
  'use strict';

  function detectWeek(){
    const m = window.location.pathname.match(/Week-?(\d+)\.html$/);
    return m ? parseInt(m[1], 10) : null;
  }

  function showError(message){
    const strip = document.getElementById('tldrStrip');
    if(!strip) return;
    let el = strip.querySelector('.tldr-error');
    if(!el){
      el = document.createElement('div');
      el.className = 'tldr-error';
      el.setAttribute('role','alert');
      el.setAttribute('aria-live','polite');
      strip.appendChild(el);
    }
    el.textContent = '⚠️ ' + message;
  }

  async function fetchJson(path){
    try { const r = await fetch(path, { cache: 'no-store' }); return r.ok ? r.json() : null; } catch { return null; }
  }

  async function fetchDataForWeek(weekNum){
    const base = window.location.pathname.includes('/Posts/') ? '../Data' : 'Data';
    // Primary: exact week
    let data = await fetchJson(`${base}/W${weekNum}/master.json`);
    if(data) return data;
    // Fallback 1: previous week (handles early publication when current not yet committed)
    if(weekNum > 1){
      data = await fetchJson(`${base}/W${weekNum-1}/master.json`);
      if(data) return data;
    }
    // Fallback 2: bootstrap seed W0
    data = await fetchJson(`${base}/W0/master.json`);
    if(data) return data;
    // Fallback 3: legacy root master.json (if ever present)
    return await fetchJson(`${base}/master.json`);
  }

  async function populate(){
    const strip = document.getElementById('tldrStrip');
    if(!strip) return;
    const weekNum = detectWeek();
    if(weekNum == null){
      showError('Week not detected from URL');
      return;
    }

    const weekEl = document.getElementById('tldrWeek');
    const totalEl = document.getElementById('tldrTotal');
    const alphaEl = document.getElementById('tldrAlpha');
    const safeSet = (el,val)=>{ if(el) el.textContent = val; };
    const fmt = v => (v==null ? '--' : v.toFixed(2) + '%');

    try {
      const data = await fetchDataForWeek(weekNum);
      if(!data){
        showError('Summary data unavailable');
        safeSet(weekEl,'--'); safeSet(totalEl,'--'); safeSet(alphaEl,'--');
        return;
      }
      const ph = Array.isArray(data.portfolio_history) ? data.portfolio_history : [];
      const spx = data?.benchmarks?.sp500?.history || [];
      if(!ph.length || !spx.length){
        showError('Incomplete data set');
        safeSet(weekEl,'--'); safeSet(totalEl,'--'); safeSet(alphaEl,'--');
        return;
      }
      // Map week number to index if available; fallback to last entry
      const pEntry = ph[weekNum] || ph[ph.length-1];
      const spxEntry = spx[weekNum] || spx[spx.length-1];
      safeSet(weekEl, fmt(pEntry.weekly_pct));
      safeSet(totalEl, fmt(pEntry.total_pct));
      if(alphaEl){
        const alphaVal = (pEntry.total_pct!=null && spxEntry.total_pct!=null) ? (pEntry.total_pct - spxEntry.total_pct) : null;
        alphaEl.textContent = fmt(alphaVal);
        if(alphaVal!=null) alphaEl.classList.add(alphaVal >= 0 ? 'alpha-positive' : 'alpha-negative');
      }
    } catch(e){
      console.warn('TLDR population failed', e);
      showError('Error loading metrics');
      safeSet(weekEl,'--'); safeSet(totalEl,'--'); safeSet(alphaEl,'--');
    }
  }

  if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', populate);
  else populate();
})();