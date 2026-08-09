/**
 * auth.js — authentication flows and navbar state.
 *
 * Handles login/register/logout forms where present, and on every page
 * resolves the current user (if any) to adjust the navbar and gate
 * admin-only UI. The frontend never trusts a locally cached role for
 * anything security-sensitive — the backend re-checks on every request —
 * this is purely for showing/hiding navigation.
 */
(function (global) {
  'use strict';

  const Auth = {
    currentUser: null,

    async resolveCurrentUser() {
      if (!global.Api.TokenStore.isAuthenticated()) {
        this.currentUser = null;
        return null;
      }
      try {
        this.currentUser = await global.Api.getCurrentUser();
      } catch (err) {
        // Token invalid/expired — clear it quietly.
        global.Api.TokenStore.clear();
        this.currentUser = null;
      }
      return this.currentUser;
    },

    isAdmin() {
      return !!this.currentUser && this.currentUser.role === 'admin';
    },

    logout() {
      global.Api.logout();
      global.location.href = '/login';
    },
  };

  function setFieldError(fieldEl, message) {
    fieldEl.classList.toggle('has-error', !!message);
    const errorEl = fieldEl.querySelector('.error-text');
    if (errorEl) errorEl.textContent = message || '';
  }

  function clearFormErrors(form) {
    form.querySelectorAll('.field').forEach((f) => setFieldError(f, ''));
  }

  function bindLoginForm() {
    const form = document.getElementById('login-form');
    if (!form) return;

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      clearFormErrors(form);
      const submitBtn = form.querySelector('button[type="submit"]');
      const email = form.email.value.trim();
      const password = form.password.value;

      submitBtn.disabled = true;
      submitBtn.querySelector('.btn-label').textContent = 'Signing in…';

      try {
        await global.Api.login({ email, password });
        global.Flash && global.Flash.show('Welcome back!', 'success');
        const redirectTo = new URLSearchParams(location.search).get('next') || '/';
        location.href = redirectTo;
      } catch (err) {
        const field = form.closest('.auth-shell').querySelector('.field:has(#password)') || form.querySelector('.field');
        const message = err instanceof global.Api.ApiError ? err.message : 'Something went wrong. Please try again.';
        global.Flash ? global.Flash.show(message, 'error') : alert(message);
      } finally {
        submitBtn.disabled = false;
        submitBtn.querySelector('.btn-label').textContent = 'Sign in';
      }
    });
  }

  function bindRegisterForm() {
    const form = document.getElementById('register-form');
    if (!form) return;

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      clearFormErrors(form);
      const submitBtn = form.querySelector('button[type="submit"]');

      const name = form.name.value.trim();
      const email = form.email.value.trim();
      const password = form.password.value;
      const confirmPassword = form.confirm_password.value;

      let hasError = false;
      if (password.length < 8) {
        setFieldError(form.password.closest('.field'), 'Password must be at least 8 characters.');
        hasError = true;
      }
      if (password !== confirmPassword) {
        setFieldError(form.confirm_password.closest('.field'), 'Passwords do not match.');
        hasError = true;
      }
      if (hasError) return;

      submitBtn.disabled = true;
      submitBtn.querySelector('.btn-label').textContent = 'Creating account…';

      try {
        await global.Api.register({ name, email, password });
        await global.Api.login({ email, password });
        global.Flash && global.Flash.show('Account created — welcome!', 'success');
        location.href = '/';
      } catch (err) {
        const message = err instanceof global.Api.ApiError ? err.message : 'Something went wrong. Please try again.';
        global.Flash ? global.Flash.show(message, 'error') : alert(message);
      } finally {
        submitBtn.disabled = false;
        submitBtn.querySelector('.btn-label').textContent = 'Create account';
      }
    });
  }

  function bindLogoutButtons() {
    document.querySelectorAll('[data-action="logout"]').forEach((btn) => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        Auth.logout();
      });
    });
  }

  /** Show/hide navbar sections based on auth state + role. */
  function renderNavAuthState(user) {
    const guestEls = document.querySelectorAll('[data-auth="guest"]');
    const userEls = document.querySelectorAll('[data-auth="user"]');
    const adminEls = document.querySelectorAll('[data-auth="admin"]');
    const userNameEls = document.querySelectorAll('[data-user-name]');
    const userInitialEls = document.querySelectorAll('[data-user-initial]');

    const isAuthed = !!user;
    const isAdmin = isAuthed && user.role === 'admin';

    guestEls.forEach((el) => (el.hidden = isAuthed));
    userEls.forEach((el) => (el.hidden = !isAuthed));
    adminEls.forEach((el) => (el.hidden = !isAdmin));

    if (isAuthed) {
      userNameEls.forEach((el) => (el.textContent = user.name));
      userInitialEls.forEach((el) => (el.textContent = (user.name || '?').trim().charAt(0).toUpperCase()));
    }
  }

  async function init() {
    bindLoginForm();
    bindRegisterForm();
    bindLogoutButtons();
    const user = await Auth.resolveCurrentUser();
    renderNavAuthState(user);
    document.dispatchEvent(new CustomEvent('arp:auth-resolved', { detail: { user } }));
  }

  global.Auth = Auth;
  document.addEventListener('DOMContentLoaded', init);
})(window);
