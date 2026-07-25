function formatPrice(value) {
  const n = Number(value);
  if (Number.isNaN(n)) return value;
  return n.toLocaleString('vi-VN') + 'đ';
}

function resolveImage(path) {
  if (!path) return '/static/images/placeholder.jpg';
  return '/static/' + path.replace(/^\/+/, '');
}

function stripHtml(html) {
  const div = document.createElement('div');
  div.innerHTML = html || '';
  return div.textContent || div.innerText || '';
}

/* ===== Navbar toggle ===== */
function initNav() {
  const toggle = document.querySelector('.nav-toggle');
  const links = document.querySelector('.nav-links');
  if (!toggle || !links) return;
  toggle.addEventListener('click', () => {
    links.classList.toggle('open');
  });
  links.querySelectorAll('a').forEach((a) =>
    a.addEventListener('click', () => links.classList.remove('open'))
  );
}

/* ===== Carousel ===== */
function initCarousel(slides) {
  const root = document.querySelector('.carousel');
  if (!root || !slides.length) return;

  const track = root.querySelector('.carousel-track');
  const dotsWrap = root.querySelector('.carousel-dots');
  track.innerHTML = slides
    .map(
      (p) => `
      <div class="carousel-slide">
        <img src="${resolveImage(p.image)}" alt="${p.name}">
        <div class="carousel-caption">
          <h2>${p.name}</h2>
          <p>${formatPrice(p.price)}</p>
        </div>
      </div>`
    )
    .join('');

  dotsWrap.innerHTML = slides
    .map((_, i) => `<button data-index="${i}" class="${i === 0 ? 'active' : ''}"></button>`)
    .join('');

  let current = 0;
  const total = slides.length;

  function goTo(index) {
    current = (index + total) % total;
    track.style.transform = `translateX(-${current * 100}%)`;
    dotsWrap.querySelectorAll('button').forEach((b, i) => b.classList.toggle('active', i === current));
  }

  root.querySelector('.carousel-btn.prev').addEventListener('click', () => goTo(current - 1));
  root.querySelector('.carousel-btn.next').addEventListener('click', () => goTo(current + 1));
  dotsWrap.querySelectorAll('button').forEach((b) =>
    b.addEventListener('click', () => goTo(Number(b.dataset.index)))
  );

  let timer = setInterval(() => goTo(current + 1), 5000);
  root.addEventListener('mouseenter', () => clearInterval(timer));
  root.addEventListener('mouseleave', () => {
    timer = setInterval(() => goTo(current + 1), 5000);
  });
}

/* ===== Product card ===== */
function productCardHTML(product, isNew) {
  return `
    <article class="product-card fade-in" data-id="${product.id}">
      <div class="product-thumb">
        <img src="${resolveImage(product.image)}" alt="${product.name}" loading="lazy">
      </div>
      <div class="product-info">
        ${isNew ? '<span class="product-badge">Mới</span>' : ''}
        <h3>${product.name}</h3>
        <p class="product-price">${formatPrice(product.price)}</p>
        <button type="button" class="product-quick-add" data-action="quick-add">+ Giỏ hàng</button>
      </div>
    </article>`;
}

function attachProductCardEvents(container, products) {
  container.querySelectorAll('.product-card').forEach((card) => {
    card.addEventListener('click', (e) => {
      if (e.target.closest('[data-action="quick-add"]')) return;
      const product = products.find((p) => String(p.id) === card.dataset.id);
      if (product) openProductModal(product);
    });

    const quickAddBtn = card.querySelector('[data-action="quick-add"]');
    if (quickAddBtn) {
      quickAddBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        addToCart(Number(card.dataset.id), 1);
        quickAddBtn.textContent = 'Đã thêm ✓';
        setTimeout(() => {
          quickAddBtn.textContent = '+ Giỏ hàng';
        }, 1200);
      });
    }
  });
}

/* ===== Modal ===== */
function ensureModal() {
  let overlay = document.querySelector('.modal-overlay');
  if (overlay) return overlay;
  overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  overlay.innerHTML = `
    <div class="modal-box">
      <button class="modal-close" aria-label="Đóng">&times;</button>
      <div class="modal-content"></div>
    </div>`;
  document.body.appendChild(overlay);
  overlay.addEventListener('click', (e) => {
    if (e.target === overlay || e.target.classList.contains('modal-close')) {
      overlay.classList.remove('open');
    }
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') overlay.classList.remove('open');
  });
  return overlay;
}

function openProductModal(product) {
  const overlay = ensureModal();
  overlay.querySelector('.modal-content').innerHTML = `
    <img src="${resolveImage(product.image)}" alt="${product.name}">
    <div class="modal-body">
      <h2>${product.name}</h2>
      <p class="modal-price">${formatPrice(product.price)}</p>
      <div>${product.description || 'Đang cập nhật mô tả sản phẩm.'}</div>
      <div class="modal-cart-actions">
        <div class="qty-stepper">
          <button type="button" class="qty-btn" data-action="decrease" aria-label="Giảm">−</button>
          <span id="modal-qty">1</span>
          <button type="button" class="qty-btn" data-action="increase" aria-label="Tăng">+</button>
        </div>
        <button type="button" class="btn" id="modal-add-to-cart">Thêm vào giỏ hàng</button>
      </div>
    </div>`;
  overlay.classList.add('open');

  let qty = 1;
  const qtyLabel = overlay.querySelector('#modal-qty');
  overlay.querySelector('[data-action="increase"]').addEventListener('click', () => {
    qty += 1;
    qtyLabel.textContent = qty;
  });
  overlay.querySelector('[data-action="decrease"]').addEventListener('click', () => {
    if (qty > 1) qty -= 1;
    qtyLabel.textContent = qty;
  });

  const addBtn = overlay.querySelector('#modal-add-to-cart');
  addBtn.addEventListener('click', () => {
    addToCart(product.id, qty);
    addBtn.textContent = 'Đã thêm vào giỏ ✓';
    setTimeout(() => {
      addBtn.textContent = 'Thêm vào giỏ hàng';
    }, 1200);
  });
}

/* ===== Data loading ===== */
async function fetchShopData() {
  const [categories, products] = await Promise.all([
    fetch('/api/categories').then((r) => r.json()),
    fetch('/api/products').then((r) => r.json()),
  ]);
  return { categories, products };
}

/* ===== Home page ===== */
async function initHomePage() {
  const grid = document.querySelector('#latest-products');
  if (!grid) return;
  try {
    const { products } = await fetchShopData();
    const sorted = [...products].sort(
      (a, b) => new Date(b.published_date) - new Date(a.published_date)
    );
    const latest = sorted.slice(0, 8);
    initCarousel(sorted.slice(0, 5));
    grid.innerHTML = latest.map((p) => productCardHTML(p, true)).join('');
    attachProductCardEvents(grid, products);
  } catch (err) {
    grid.innerHTML = `<p class="empty-state">Không thể tải dữ liệu sản phẩm.</p>`;
    console.error(err);
  }
}

/* ===== Products page ===== */
async function initProductsPage() {
  const grid = document.querySelector('#product-grid');
  const filterBar = document.querySelector('#filter-bar');
  if (!grid || !filterBar) return;

  try {
    const { categories, products } = await fetchShopData();

    function render(categoryId) {
      const filtered =
        categoryId === 'all'
          ? products
          : products.filter((p) => String(p.category_id) === String(categoryId));
      grid.innerHTML = filtered.length
        ? filtered.map((p) => productCardHTML(p, false)).join('')
        : '<p class="empty-state">Không có sản phẩm trong danh mục này.</p>';
      attachProductCardEvents(grid, products);
    }

    filterBar.innerHTML =
      `<button class="filter-btn active" data-cat="all">Tất cả</button>` +
      categories
        .map((c) => `<button class="filter-btn" data-cat="${c.id}">${c.name}</button>`)
        .join('');

    filterBar.querySelectorAll('.filter-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        filterBar.querySelectorAll('.filter-btn').forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');
        render(btn.dataset.cat);
      });
    });

    const params = new URLSearchParams(window.location.search);
    const initialCat = params.get('cat') || 'all';
    const initialBtn = filterBar.querySelector(`[data-cat="${initialCat}"]`);
    if (initialBtn) {
      filterBar.querySelectorAll('.filter-btn').forEach((b) => b.classList.remove('active'));
      initialBtn.classList.add('active');
    }
    render(initialCat);
  } catch (err) {
    grid.innerHTML = `<p class="empty-state">Không thể tải dữ liệu sản phẩm.</p>`;
    console.error(err);
  }
}

/* ===== Contact page ===== */
function initContactForm() {
  const form = document.querySelector('#contact-form');
  if (!form) return;

  const feedback = document.querySelector('#form-feedback');

  function setError(field, message) {
    const el = form.querySelector(`[data-error-for="${field}"]`);
    if (el) el.textContent = message || '';
  }

  function validate() {
    let valid = true;
    const name = form.name.value.trim();
    const email = form.email.value.trim();
    const message = form.message.value.trim();

    if (!name) {
      setError('name', 'Vui lòng nhập họ tên.');
      valid = false;
    } else {
      setError('name', '');
    }

    const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!email || !emailPattern.test(email)) {
      setError('email', 'Vui lòng nhập email hợp lệ.');
      valid = false;
    } else {
      setError('email', '');
    }

    if (!message || message.length < 10) {
      setError('message', 'Nội dung góp ý cần tối thiểu 10 ký tự.');
      valid = false;
    } else {
      setError('message', '');
    }

    return valid;
  }

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!validate()) return;

    const payload = {
      name: form.name.value.trim(),
      email: form.email.value.trim(),
      message: form.message.value.trim(),
    };

    try {
      const res = await fetch('/api/contact', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      feedback.textContent = res.ok
        ? data.message
        : data.error || 'Đã có lỗi xảy ra, vui lòng thử lại.';
      feedback.classList.add('show');
      if (res.ok) form.reset();
      setTimeout(() => feedback.classList.remove('show'), 6000);
    } catch (err) {
      feedback.textContent = 'Không thể gửi góp ý, vui lòng thử lại sau.';
      feedback.classList.add('show');
      console.error(err);
    }
  });

  ['input', 'blur'].forEach((evt) => {
    form.addEventListener(evt, () => {}, true);
  });
}

document.addEventListener('DOMContentLoaded', () => {
  initNav();
  initHomePage();
  initProductsPage();
  initContactForm();
});
