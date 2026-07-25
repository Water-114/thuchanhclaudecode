const CART_KEY = 'coffeeshop_cart';

function getCart() {
  try {
    return JSON.parse(localStorage.getItem(CART_KEY)) || [];
  } catch (err) {
    return [];
  }
}

function saveCart(cart) {
  localStorage.setItem(CART_KEY, JSON.stringify(cart));
  updateCartBadge();
}

function addToCart(productId, quantity = 1) {
  const cart = getCart();
  const existing = cart.find((item) => item.product_id === productId);
  if (existing) {
    existing.quantity += quantity;
  } else {
    cart.push({ product_id: productId, quantity });
  }
  saveCart(cart);
}

function removeFromCart(productId) {
  saveCart(getCart().filter((item) => item.product_id !== productId));
}

function updateCartQuantity(productId, quantity) {
  const cart = getCart();
  const item = cart.find((i) => i.product_id === productId);
  if (!item) return;
  if (quantity <= 0) {
    saveCart(cart.filter((i) => i.product_id !== productId));
  } else {
    item.quantity = quantity;
    saveCart(cart);
  }
}

function clearCart() {
  saveCart([]);
}

function cartItemCount() {
  return getCart().reduce((sum, item) => sum + item.quantity, 0);
}

function updateCartBadge() {
  const badge = document.querySelector('#nav-cart-count');
  if (badge) badge.textContent = cartItemCount();
}

/* ===== Cart page ===== */
async function initCartPage() {
  const root = document.querySelector('#cart-page-root');
  if (!root) return;

  if (!getCart().length) {
    root.innerHTML = '<p class="empty-state">Giỏ hàng của bạn đang trống. <a href="/products">Xem sản phẩm</a></p>';
    return;
  }

  let productMap;
  try {
    const { products } = await fetchShopData();
    productMap = new Map(products.map((p) => [p.id, p]));
  } catch (err) {
    root.innerHTML = '<p class="empty-state">Không thể tải giỏ hàng, vui lòng thử lại.</p>';
    return;
  }

  function render() {
    const items = getCart()
      .map((item) => ({ ...item, product: productMap.get(item.product_id) }))
      .filter((item) => item.product);

    if (!items.length) {
      root.innerHTML = '<p class="empty-state">Giỏ hàng của bạn đang trống. <a href="/products">Xem sản phẩm</a></p>';
      return;
    }

    const subtotal = items.reduce((sum, item) => sum + item.product.price * item.quantity, 0);

    root.innerHTML = `
      <div class="cart-table-wrap">
        <table class="cart-table">
          <thead>
            <tr><th></th><th>Sản phẩm</th><th>Đơn giá</th><th>Số lượng</th><th>Thành tiền</th><th></th></tr>
          </thead>
          <tbody>
            ${items
              .map(
                (item) => `
              <tr data-id="${item.product.id}">
                <td><img class="cart-thumb" src="${resolveImage(item.product.image)}" alt="${item.product.name}"></td>
                <td>${item.product.name}</td>
                <td>${formatPrice(item.product.price)}</td>
                <td>
                  <div class="qty-stepper">
                    <button type="button" class="qty-btn" data-action="decrease" aria-label="Giảm">−</button>
                    <span>${item.quantity}</span>
                    <button type="button" class="qty-btn" data-action="increase" aria-label="Tăng">+</button>
                  </div>
                </td>
                <td>${formatPrice(item.product.price * item.quantity)}</td>
                <td><button type="button" class="cart-remove-btn" data-action="remove" aria-label="Xóa">🗑️</button></td>
              </tr>`
              )
              .join('')}
          </tbody>
        </table>
      </div>
      <div class="cart-summary">
        <div class="cart-subtotal">Tổng cộng: <strong>${formatPrice(subtotal)}</strong></div>
        <a href="/checkout" class="btn">Tiến hành thanh toán</a>
      </div>
    `;

    root.querySelectorAll('tr[data-id]').forEach((row) => {
      const productId = Number(row.dataset.id);
      row.querySelector('[data-action="increase"]').addEventListener('click', () => {
        const item = getCart().find((i) => i.product_id === productId);
        updateCartQuantity(productId, (item ? item.quantity : 0) + 1);
        render();
      });
      row.querySelector('[data-action="decrease"]').addEventListener('click', () => {
        const item = getCart().find((i) => i.product_id === productId);
        updateCartQuantity(productId, (item ? item.quantity : 0) - 1);
        render();
      });
      row.querySelector('[data-action="remove"]').addEventListener('click', () => {
        removeFromCart(productId);
        render();
      });
    });
  }

  render();
}

/* ===== Checkout page ===== */
async function initCheckoutPage() {
  const itemsRoot = document.querySelector('#checkout-items-root');
  if (!itemsRoot) return;

  const cart = getCart();
  if (!cart.length) {
    window.location.href = '/cart';
    return;
  }

  let productMap;
  try {
    const { products } = await fetchShopData();
    productMap = new Map(products.map((p) => [p.id, p]));
  } catch (err) {
    itemsRoot.innerHTML = '<p class="empty-state">Không thể tải giỏ hàng.</p>';
    return;
  }

  const items = cart
    .map((item) => ({ ...item, product: productMap.get(item.product_id) }))
    .filter((item) => item.product);

  if (!items.length) {
    window.location.href = '/cart';
    return;
  }

  const subtotal = items.reduce((sum, item) => sum + item.product.price * item.quantity, 0);

  itemsRoot.innerHTML = `
    <div class="cart-table-wrap">
      <table class="cart-table">
        <thead><tr><th></th><th>Sản phẩm</th><th>Số lượng</th><th>Thành tiền</th></tr></thead>
        <tbody>
          ${items
            .map(
              (item) => `
            <tr>
              <td><img class="cart-thumb" src="${resolveImage(item.product.image)}" alt="${item.product.name}"></td>
              <td>${item.product.name}</td>
              <td>${item.quantity}</td>
              <td>${formatPrice(item.product.price * item.quantity)}</td>
            </tr>`
            )
            .join('')}
        </tbody>
      </table>
    </div>`;

  const totalEl = document.querySelector('#checkout-total');
  if (totalEl) totalEl.textContent = `Tổng cộng: ${formatPrice(subtotal)}`;

  const submitBtn = document.querySelector('#checkout-submit-btn');
  submitBtn.addEventListener('click', async () => {
    submitBtn.disabled = true;
    submitBtn.textContent = 'Đang xử lý...';

    const payload = {
      items: items.map((item) => ({ product_id: item.product_id, quantity: item.quantity })),
      note: document.querySelector('#order-note').value.trim(),
    };

    try {
      const res = await fetch('/api/checkout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Đặt hàng thất bại.');

      clearCart();
      window.location.href = `/orders/${data.order_id}?placed=1`;
    } catch (err) {
      alert(err.message);
      submitBtn.disabled = false;
      submitBtn.textContent = 'Xác nhận đặt hàng';
    }
  });
}

document.addEventListener('DOMContentLoaded', () => {
  updateCartBadge();
  initCartPage();
  initCheckoutPage();
});
