// Global CSRF helper for fetch requests
window.getCsrfToken = () => {
  const el = document.querySelector('input[name="csrf_token"]');
  return el ? el.value : '';
};

// Confirm dialogs for consequential actions
document.querySelectorAll('[data-confirm]').forEach(el => {
  el.addEventListener('click', e => {
    if (!confirm(el.dataset.confirm)) { e.preventDefault(); }
  });
});