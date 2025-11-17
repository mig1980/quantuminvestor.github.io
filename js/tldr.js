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
    // Load from consolidated master data folder
    const base = window.location.pathname.includes('/Posts/') ? '../master data' : 'master data';
    let data = await fetchJson(`${base}/master.json`);
    if(data) return data;
    
    // Fallback to legacy weekly folders if consolidated file not available
    const legacyBase = window.location.pathname.includes('/Posts/') ? '../Data' : 'Data';
    data = await fetchJson(`${legacyBase}/W${weekNum}/master.json`);
    if(data) return data;
    
    // Fallback to previous week (handles early publication)
    if(weekNum > 1){
      data = await fetchJson(`${legacyBase}/W${weekNum-1}/master.json`);
      if(data) return data;
    }
    
    return null;
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
      // Extract week-specific entry
      // Index 0 = inception (W0), Week 1 = index 1, Week 2 = index 2, etc.
      // Week number maps directly to array index
      const weekIndex = weekNum;
      const pEntry = ph[weekIndex] || ph[ph.length-1];
      const spxEntry = spx[weekIndex] || spx[spx.length-1];
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