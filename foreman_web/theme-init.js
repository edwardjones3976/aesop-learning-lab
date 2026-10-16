// Apply the saved appearance before the stylesheet paints the page.
(() => {
  let mode = 'system';
  try {
    const saved = JSON.parse(localStorage.getItem('aesop.foreman.preferences.v1') || '{}');
    if (['system', 'light', 'dark'].includes(saved.theme)) mode = saved.theme;
  } catch (_) { /* Browser storage may be disabled. */ }
  document.documentElement.dataset.theme = mode === 'system'
    ? (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
    : mode;
})();
