# Password Gate System

## Overview

The password gate system provides simple client-side password protection for static HTML pages. It uses SHA-256 hashing to verify passwords and sessionStorage to maintain authentication state during a browser session.

## How It Works

### 1. **Password Hashing**
- Passwords are never stored in plain text
- When a user enters a password, it's hashed using SHA-256
- The hash is compared against the expected hash stored in the HTML
- Only matching hashes grant access

### 2. **Session Persistence**
- Once authenticated, a flag is set in `sessionStorage`
- The page remains unlocked for the current browser session
- Closing the browser/tab clears the session - requiring re-authentication on next visit

### 3. **UI Overlay**
- A full-screen overlay blocks content until authenticated
- The overlay is removed upon successful password entry
- Error messages display for incorrect password attempts

## Files

- **`js/password-gate.js`** - Core password verification logic
- **Protected Pages** - Any HTML file with the password overlay and script tag

## Adding Password Protection to a New Page

### Step 1: Add the Password Overlay HTML

Insert this code **inside the `<body>` tag at the very top**, before any other content:

```html
<div id="password-gate-overlay" style="position:fixed;inset:0;display:flex;align-items:center;justify-content:center;background:rgba(0,0,0,.9);z-index:9999;">
  <form id="password-gate-form" style="background:#111;padding:2rem;border:1px solid #333;border-radius:.75rem;max-width:320px;width:100%;font-family:system-ui;">
    <h2 style="margin:0 0 1rem;font-size:1.2rem;color:#fff;">Protected Page</h2>
    <p style="font-size:.75rem;color:#999;line-height:1.3;margin:0 0 1rem;">Enter password to view content.</p>
    <input type="password" id="password-gate-input" placeholder="Password" style="width:100%;padding:.6rem .8rem;background:#1a1a1a;border:1px solid #333;border-radius:.5rem;color:#fff;margin-bottom:1rem;" />
    <button type="submit" style="width:100%;background:#7e5bef;border:none;padding:.6rem 1rem;border-radius:.5rem;font-weight:600;cursor:pointer;">Unlock</button>
    <div id="password-gate-error" style="color:#f87171;font-size:.7rem;margin-top:.75rem;display:none;"></div>
    <div style="color:#666;font-size:.65rem;margin-top:1rem;line-height:1.2;">Light obfuscation only. Sensitive content should not rely on this.</div>
  </form>
</div>
```

### Step 2: Add the Script Tag

Insert this code **before the closing `</body>` tag**:

```html
<script src="../js/password-gate.js" data-password-hash="YOUR_PASSWORD_HASH_HERE"></script>
```

**Important:** Adjust the path (`../js/` or `./js/` or `js/`) based on your file location relative to the `js` folder.

### Step 3: Generate the Password Hash

Use Python to generate a SHA-256 hash of your password:

```powershell
python -c "import hashlib; print(hashlib.sha256('YourPasswordHere'.encode()).hexdigest())"
```

Replace `YOUR_PASSWORD_HASH_HERE` in the script tag with the generated hash.

## Changing the Password

### Option 1: Using Python

```powershell
python -c "import hashlib; print(hashlib.sha256('NewPassword123'.encode()).hexdigest())"
```

### Option 2: Using PowerShell

```powershell
$password = 'NewPassword123'
$sha256 = [System.Security.Cryptography.SHA256]::Create()
$bytes = [System.Text.Encoding]::UTF8.GetBytes($password)
$hash = $sha256.ComputeHash($bytes)
($hash | ForEach-Object { $_.ToString('x2') }) -join ''
```

### Option 3: Using Online Tools

Visit a SHA-256 generator like:
- https://emn178.github.io/online-tools/sha256.html
- https://xorbin.com/tools/sha256-hash-calculator

**Then update the `data-password-hash` attribute in your HTML file with the new hash.**

## Example: Protected Page Structure

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Protected Page</title>
</head>
<body>
  <!-- PASSWORD OVERLAY - ADD FIRST -->
  <div id="password-gate-overlay" style="position:fixed;inset:0;display:flex;align-items:center;justify-content:center;background:rgba(0,0,0,.9);z-index:9999;">
    <form id="password-gate-form" style="background:#111;padding:2rem;border:1px solid #333;border-radius:.75rem;max-width:320px;width:100%;font-family:system-ui;">
      <h2 style="margin:0 0 1rem;font-size:1.2rem;color:#fff;">Protected Page</h2>
      <p style="font-size:.75rem;color:#999;line-height:1.3;margin:0 0 1rem;">Enter password to view content.</p>
      <input type="password" id="password-gate-input" placeholder="Password" style="width:100%;padding:.6rem .8rem;background:#1a1a1a;border:1px solid #333;border-radius:.5rem;color:#fff;margin-bottom:1rem;" />
      <button type="submit" style="width:100%;background:#7e5bef;border:none;padding:.6rem 1rem;border-radius:.5rem;font-weight:600;cursor:pointer;">Unlock</button>
      <div id="password-gate-error" style="color:#f87171;font-size:.7rem;margin-top:.75rem;display:none;"></div>
    </form>
  </div>

  <!-- YOUR PAGE CONTENT HERE -->
  <h1>My Protected Content</h1>
  <p>This content is hidden behind the password gate.</p>

  <!-- PASSWORD SCRIPT - ADD LAST, BEFORE </body> -->
  <script src="../js/password-gate.js" data-password-hash="18ae8ef593e3ad19525954a455f81cc50b0b5e6462dc95468eb4d43f9d8ea17d"></script>
</body>
</html>
```

## Pages Currently Protected

- `Posts/social-card-generator.html`

## Security Considerations

⚠️ **This is CLIENT-SIDE obfuscation only** - suitable for light protection:

### What it DOES:
- Prevents casual visitors from viewing content
- Hides content from search engines
- Provides a simple authentication barrier

### What it DOES NOT do:
- Prevent determined users from accessing content (hash visible in source)
- Protect sensitive/confidential information
- Provide server-side security
- Prevent content scraping or direct file access

### Recommendations:
- **Good for:** Draft content, private notes, work-in-progress pages
- **NOT good for:** Confidential data, personal information, payment details
- For true security, use server-side authentication or a proper CMS with access control

## Troubleshooting

### Password overlay doesn't appear
- Check that the overlay HTML is inside `<body>` and before other content
- Verify z-index is high enough (9999)
- Check browser console for JavaScript errors

### Password not working
- Verify the hash matches your password exactly
- Check that `data-password-hash` attribute is set correctly
- Test hash generation: run the Python command and compare outputs

### Page unlocks but closes on refresh
- This is expected behavior - sessionStorage clears on tab close
- For persistent login, you'd need to use localStorage (less secure)

### Script path errors
- Adjust the relative path in the script tag based on file location
- From `Posts/` folder: use `../js/password-gate.js`
- From root folder: use `js/password-gate.js`
- From nested folders: adjust accordingly

## Technical Details

### Password Gate Script (`password-gate.js`)

```javascript
// Extracts password hash from script tag data attribute
const expectedHash = scriptEl.dataset.passwordHash;

// SHA-256 hashing function using Web Crypto API
function sha256Hex(str) {
  const enc = new TextEncoder().encode(str);
  return crypto.subtle.digest('SHA-256', enc).then(buf => {
    const bytes = Array.from(new Uint8Array(buf));
    return bytes.map(b => b.toString(16).padStart(2,'0')).join('');
  });
}

// Unlock function - hides overlay and sets session flag
function unlock() {
  overlay.style.display = 'none';
  sessionStorage.setItem('pageUnlocked', '1');
}

// Check if already unlocked this session
if(sessionStorage.getItem('pageUnlocked') === '1') {
  unlock();
}
```

### Browser Compatibility

- Modern browsers with Web Crypto API support (Chrome 37+, Firefox 34+, Safari 11+, Edge 79+)
- sessionStorage support (all modern browsers)
- SHA-256 hashing via SubtleCrypto

---

**Last Updated:** November 17, 2025  

