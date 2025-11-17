(function(){
  const overlay = document.getElementById('password-gate-overlay');
  if(!overlay) return;
  const form = document.getElementById('password-gate-form');
  const input = document.getElementById('password-gate-input');
  const errorBox = document.getElementById('password-gate-error');
  const scriptEl = document.querySelector('script[data-password-hash]');
  const expectedHash = scriptEl ? scriptEl.dataset.passwordHash : '';

  function sha256Hex(str){
    const enc = new TextEncoder().encode(str);
    return crypto.subtle.digest('SHA-256', enc).then(buf => {
      const bytes = Array.from(new Uint8Array(buf));
      return bytes.map(b => b.toString(16).padStart(2,'0')).join('');
    });
  }

  function unlock(){
    overlay.style.display = 'none';
    sessionStorage.setItem('pageUnlocked', '1');
  }

  // Already unlocked this session
  if(sessionStorage.getItem('pageUnlocked') === '1'){
    unlock();
    return;
  }

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    errorBox.style.display = 'none';
    const val = input.value.trim();
    if(!val) return;
    try {
      const hash = await sha256Hex(val);
      if(hash === expectedHash){
        unlock();
      } else {
        errorBox.textContent = 'Incorrect password.';
        errorBox.style.display = 'block';
      }
    } catch(err){
      console.error(err);
      errorBox.textContent = 'Error verifying password.';
      errorBox.style.display = 'block';
    }
  });
})();
