/**
 * admin.js — admin dashboard stats, product management table, and the
 * create/edit product forms. Runs only on /admin/* pages.
 */
(function (global) {
  'use strict';

  const { formatPrice, debounce, escapeHtml } = global.AppUI;

  // ---- Dashboard ---------------------------------------------------
  async function initDashboard() {
    const el = document.getElementById('admin-dashboard-stats');
    if (!el) return;

    try {
      const stats = await global.Api.adminDashboard();
      el.querySelector('[data-stat="total_users"]').textContent = stats.total_users.toLocaleString();
      el.querySelector('[data-stat="total_products"]').textContent = stats.total_products.toLocaleString();
      el.querySelector('[data-stat="total_events"]').textContent = stats.total_events.toLocaleString();
      el.querySelector('[data-stat="total_recommendations"]').textContent = stats.total_recommendations.toLocaleString();
    } catch (err) {
      global.Flash && global.Flash.show('Could not load dashboard stats.', 'error');
    }

    const eventsList = document.getElementById('admin-event-stats');
    if (eventsList) {
      try {
        const byType = await global.Api.adminEventStats();
        const entries = Object.entries(byType).sort((a, b) => b[1] - a[1]);
        eventsList.innerHTML = entries.length
          ? entries.map(([type, count]) => `
              <li class="row between" style="padding:8px 0;border-bottom:1px solid var(--border)">
                <span>${escapeHtml(type)}</span>
                <strong>${count.toLocaleString()}</strong>
              </li>`).join('')
          : '<li>No events recorded yet.</li>';
      } catch (err) {
        eventsList.innerHTML = '<li>Event stats unavailable.</li>';
      }
    }
  }

  // ---- Product management table -------------------------------------
  async function initProductTable() {
    const tbody = document.getElementById('admin-products-tbody');
    if (!tbody) return;

    const searchInput = document.getElementById('admin-product-search');
    const state = { page: 1, limit: 20, search: '' };

    async function load() {
      tbody.innerHTML = `<tr><td colspan="5"><span class="spinner"></span> Loading…</td></tr>`;
      try {
        const data = await global.Api.adminListProducts({ page: state.page, limit: state.limit, search: state.search || undefined });
        renderRows(data.items || []);
        renderTablePagination(data.meta);
      } catch (err) {
        tbody.innerHTML = `<tr><td colspan="5">Could not load products. Please refresh.</td></tr>`;
      }
    }

    function renderRows(items) {
      if (items.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5">No products match your search.</td></tr>`;
        return;
      }
      tbody.innerHTML = items.map((p) => `
        <tr>
          <td><strong>${escapeHtml(p.title)}</strong></td>
          <td><span class="badge badge-category">${escapeHtml(p.category)}</span></td>
          <td>${formatPrice(p.price)}</td>
          <td><span class="badge ${p.is_active ? 'badge-active' : 'badge-inactive'}">${p.is_active ? 'Active' : 'Inactive'}</span></td>
          <td>
            <div class="table-actions">
              <a class="btn btn-outline btn-sm" href="/admin/products/${encodeURIComponent(p.id)}/edit">Edit</a>
              <button class="btn btn-danger btn-sm" data-delete-id="${escapeHtml(p.id)}" data-delete-title="${escapeHtml(p.title)}">Delete</button>
            </div>
          </td>
        </tr>
      `).join('');
    }

    function renderTablePagination(meta) {
      const el = document.getElementById('admin-products-pagination');
      if (!el || !meta) return;
      if (meta.total_pages <= 1) { el.innerHTML = ''; return; }
      let html = '';
      for (let p = 1; p <= meta.total_pages; p++) {
        html += `<button data-page="${p}" class="${p === meta.page ? 'active' : ''}">${p}</button>`;
      }
      el.innerHTML = html;
      el.querySelectorAll('button').forEach((btn) => btn.addEventListener('click', () => {
        state.page = Number(btn.dataset.page);
        load();
      }));
    }

    tbody.addEventListener('click', (e) => {
      const btn = e.target.closest('[data-delete-id]');
      if (!btn) return;
      openDeleteModal(btn.dataset.deleteId, btn.dataset.deleteTitle, load);
    });

    if (searchInput) {
      searchInput.addEventListener('input', debounce((e) => {
        state.search = e.target.value.trim();
        state.page = 1;
        load();
      }, 400));
    }

    load();
  }

  function openDeleteModal(productId, title, onDeleted) {
    const overlay = document.getElementById('delete-modal');
    if (!overlay) return;
    overlay.hidden = false;
    overlay.querySelector('[data-modal-title]').textContent = title;

    const confirmBtn = overlay.querySelector('[data-confirm-delete]');
    const cancelBtn = overlay.querySelector('[data-cancel-delete]');

    const cleanup = () => {
      overlay.hidden = true;
      confirmBtn.removeEventListener('click', onConfirm);
      cancelBtn.removeEventListener('click', cleanup);
    };
    const onConfirm = async () => {
      confirmBtn.disabled = true;
      try {
        await global.Api.adminDeleteProduct(productId);
        global.Flash && global.Flash.show('Product deleted.', 'success');
        onDeleted();
      } catch (err) {
        global.Flash && global.Flash.show('Could not delete product.', 'error');
      } finally {
        confirmBtn.disabled = false;
        cleanup();
      }
    };
    confirmBtn.addEventListener('click', onConfirm);
    cancelBtn.addEventListener('click', cleanup);
  }

  // ---- Create / edit form ---------------------------------------------
  function collectProductForm(form) {
    const tags = form.tags.value.trim();
    return {
      title: form.title.value.trim(),
      description: form.description.value.trim() || null,
      category: form.category.value.trim(),
      product_type: form.product_type.value,
      price: Number(form.price.value),
      image_url: form.image_url.value.trim() || null,
      rating: form.rating.value ? Number(form.rating.value) : null,
      stock: form.stock.value ? Number(form.stock.value) : null,
      tags: tags ? tags.split(',').map((t) => t.trim()).filter(Boolean) : null,
      is_active: form.is_active.checked,
    };
  }

  function validateProductForm(form) {
    let valid = true;
    const requiredFields = [
      ['title', 'Title is required.'],
      ['category', 'Category is required.'],
      ['price', 'Price is required.'],
    ];
    requiredFields.forEach(([name, message]) => {
      const field = form[name].closest('.field');
      if (!form[name].value.trim()) {
        field.classList.add('has-error');
        field.querySelector('.error-text').textContent = message;
        valid = false;
      } else {
        field.classList.remove('has-error');
      }
    });
    if (form.price.value && Number(form.price.value) < 0) {
      const field = form.price.closest('.field');
      field.classList.add('has-error');
      field.querySelector('.error-text').textContent = 'Price cannot be negative.';
      valid = false;
    }
    return valid;
  }

  function initCreateForm() {
    const form = document.getElementById('product-create-form');
    if (!form) return;
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      if (!validateProductForm(form)) return;
      const submitBtn = form.querySelector('button[type="submit"]');
      submitBtn.disabled = true;
      try {
        await global.Api.adminCreateProduct(collectProductForm(form));
        global.Flash && global.Flash.show('Product created.', 'success');
        location.href = '/admin/products';
      } catch (err) {
        global.Flash && global.Flash.show(err.message || 'Could not create product.', 'error');
      } finally {
        submitBtn.disabled = false;
      }
    });
  }

  function initEditForm() {
    const form = document.getElementById('product-edit-form');
    if (!form || form.dataset.boundSubmit) return;
    form.dataset.boundSubmit = 'true';
    const productId = form.dataset.productId;

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      if (!validateProductForm(form)) return;
      const submitBtn = form.querySelector('button[type="submit"]');
      submitBtn.disabled = true;
      try {
        await global.Api.adminUpdateProduct(productId, collectProductForm(form));
        global.Flash && global.Flash.show('Product updated.', 'success');
        location.href = '/admin/products';
      } catch (err) {
        global.Flash && global.Flash.show(err.message || 'Could not update product.', 'error');
      } finally {
        submitBtn.disabled = false;
      }
    });
  }

  // The edit page's form is rendered asynchronously (product data is
  // fetched client-side), so it may not exist yet at DOMContentLoaded.
  // Listen for the page's "ready" signal too.
  document.addEventListener('arp:edit-form-ready', initEditForm);

  document.addEventListener('DOMContentLoaded', () => {
    initDashboard();
    initProductTable();
    initCreateForm();
    initEditForm();
  });
})(window);
