document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('form[data-confirm]').forEach((form) => {
    form.addEventListener('submit', (e) => {
      if (!confirm(form.dataset.confirm)) e.preventDefault();
    });
  });

  document.querySelectorAll('tr[data-href]').forEach((row) => {
    row.addEventListener('click', (e) => {
      if (e.target.closest('a, button, form')) return;
      window.location.href = row.dataset.href;
    });
  });

  const toggle = document.querySelector('#admin-menu-toggle');
  const sidebar = document.querySelector('#admin-sidebar');
  if (toggle && sidebar) {
    toggle.addEventListener('click', () => sidebar.classList.toggle('open'));
    document.addEventListener('click', (e) => {
      if (sidebar.classList.contains('open') && !sidebar.contains(e.target) && e.target !== toggle) {
        sidebar.classList.remove('open');
      }
    });
  }
});
