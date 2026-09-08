/**
 * therealbonz.com - Interactive Launchpad, 3D Studio, Secure Auth & CMS Controller
 */

// Global State
const state = {
  user: null, // { username, display_name, role, can_add_admins }
  clientIp: '',
  isIpTrusted: false,
  isSuperadmin: false,
  token: localStorage.getItem('bonz_admin_token') || '',

  repos: [],
  selectedLanguage: 'all',
  searchQuery: '',
  projects: [],
  serverCurrentPath: '',
  serverBaseDir: '',

  // 3D Cube physics
  isAutoRotating: true,
  rotationX: -15,
  rotationY: 25,
  velocityX: 0,
  velocityY: 0,
  isDragging: false,
  lastMouseX: 0,
  lastMouseY: 0,
  animationFrameId: null
};

// Language color palette
const LANG_COLORS = {
  'TypeScript': '#3178c6',
  'JavaScript': '#f7df1e',
  'Python': '#3572A5',
  'C#': '#178600',
  'C++': '#f34b7d',
  'HTML': '#e34c26',
  'CSS': '#563d7c',
  'Shell': '#89e051',
  'Dockerfile': '#384d54',
  'Dart': '#00B4AB',
  'default': '#00f0ff'
};

// ==========================================================================
// Authenticated Fetch Helper
// ==========================================================================

async function authFetch(url, options = {}) {
  options.headers = options.headers || {};
  if (state.token) {
    options.headers['Authorization'] = `Bearer ${state.token}`;
    options.headers['X-Admin-Token'] = state.token;
  }
  return fetch(url, options);
}

// ==========================================================================
// Initialization
// ==========================================================================

document.addEventListener('DOMContentLoaded', async () => {
  await initAuth();
  initSystemStatus();
  init3DCube();
  initProjectsCMS();
  initGitHubRepos();
  initServerFileManager();
  initModals();
  initAdminPanelTabs();
});

// ==========================================================================
// Toast System
// ==========================================================================

function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `
    <div class="toast-content">
      <p>${escapeHtml(message)}</p>
    </div>
  `;

  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(50px)';
    setTimeout(() => toast.remove(), 250);
  }, 4000);
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

// ==========================================================================
// Authentication & Access Control
// ==========================================================================

async function initAuth() {
  try {
    const res = await authFetch('/api/auth/me');
    if (res.ok) {
      const data = await res.json();
      state.clientIp = data.client_ip;
      state.isIpTrusted = data.is_ip_trusted;
      state.user = data.authenticated ? data.user : null;
      state.isSuperadmin = Boolean(data.is_superadmin);
    }
  } catch (err) {
    state.user = null;
  }

  updateAuthUI();

  // Form login submission
  const loginForm = document.getElementById('form-admin-login');
  if (loginForm) {
    loginForm.addEventListener('submit', handleLogin);
  }

  // Unlock server view button
  const unlockBtn = document.getElementById('btn-unlock-server-view');
  if (unlockBtn) {
    unlockBtn.addEventListener('click', () => openLoginModal());
  }
}

function updateAuthUI() {
  const isLogged = Boolean(state.user);
  document.body.classList.toggle('is-admin', isLogged);

  const authContainer = document.getElementById('auth-state-container');
  const adminStat = document.getElementById('stat-admin-mode');
  const ipPill = document.getElementById('client-ip-pill');

  if (ipPill && state.clientIp) {
    ipPill.textContent = `IP: ${state.clientIp}`;
    ipPill.title = state.isIpTrusted ? 'IP Whitelisted' : 'IP Not Whitelisted';
  }

  if (adminStat) {
    adminStat.textContent = isLogged ? (state.isSuperadmin ? 'Superadmin' : 'Admin') : 'Guest';
    adminStat.style.color = isLogged ? 'var(--neon-emerald)' : 'var(--neon-cyan)';
  }

  // Update header buttons
  if (authContainer) {
    if (isLogged) {
      authContainer.innerHTML = `
        <div class="admin-badge-group">
          <span class="admin-pill" title="Logged in as ${escapeHtml(state.user.username)}">
            👑 ${escapeHtml(state.user.username)}
          </span>
          ${state.isSuperadmin ? `
            <button class="btn btn-sm btn-secondary" id="btn-open-admin-panel" title="Manage Admins & Security">
              <svg class="icon" viewBox="0 0 24 24"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
              <span>Admin Panel</span>
            </button>
          ` : ''}
          <button class="btn btn-sm btn-outline" id="btn-logout" title="Sign Out">
            <span>Log Out</span>
          </button>
        </div>
      `;

      const panelBtn = document.getElementById('btn-open-admin-panel');
      if (panelBtn) panelBtn.addEventListener('click', openAdminPanelModal);

      const logoutBtn = document.getElementById('btn-logout');
      if (logoutBtn) logoutBtn.addEventListener('click', handleLogout);
    } else {
      authContainer.innerHTML = `
        <button class="btn btn-sm btn-glass" id="btn-open-login" title="Admin Login">
          <svg class="icon" viewBox="0 0 24 24"><rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
          <span>Admin Login</span>
        </button>
      `;
      const loginBtn = document.getElementById('btn-open-login');
      if (loginBtn) loginBtn.addEventListener('click', openLoginModal);
    }
  }

  // Server section locked state toggle
  const lockedView = document.getElementById('server-guest-locked');
  const adminBrowser = document.getElementById('server-admin-browser');
  if (lockedView && adminBrowser) {
    if (isLogged) {
      lockedView.style.display = 'none';
      adminBrowser.style.display = 'block';
    } else {
      lockedView.style.display = 'block';
      adminBrowser.style.display = 'none';
    }
  }

  // Re-render project cards to show/hide edit buttons
  renderProjects();
}

function openLoginModal() {
  const modal = document.getElementById('modal-login');
  const ipText = document.getElementById('login-ip-text');
  const ipDot = document.getElementById('login-ip-dot');

  if (ipText && ipDot) {
    if (state.isIpTrusted) {
      ipText.innerHTML = `Connected from whitelisted IP: <strong>${escapeHtml(state.clientIp)}</strong>`;
      ipDot.className = 'ip-dot';
    } else {
      ipText.innerHTML = `Warning: Your IP (<strong>${escapeHtml(state.clientIp)}</strong>) is not on the admin whitelist.`;
      ipDot.className = 'ip-dot danger';
    }
  }

  if (modal) modal.classList.add('active');
}

async function handleLogin(e) {
  e.preventDefault();
  const submitBtn = document.getElementById('btn-submit-login');
  const btnText = submitBtn.querySelector('.btn-text');
  const spinner = submitBtn.querySelector('.btn-spinner');

  const username = document.getElementById('login-username').value.trim();
  const password = document.getElementById('login-password').value;

  btnText.textContent = 'Verifying...';
  spinner.style.display = 'inline-block';
  submitBtn.disabled = true;

  try {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password })
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Login failed');

    state.token = data.token;
    localStorage.setItem('bonz_admin_token', data.token);
    state.user = data.user;
    state.isSuperadmin = data.user.username.toLowerCase() === 'bonz' || data.user.role === 'superadmin';

    showToast(`Welcome back, ${data.user.display_name}!`, 'success');
    document.getElementById('modal-login').classList.remove('active');
    updateAuthUI();

    // Reload server folder explorer now that we are authenticated
    await loadServerFolders('');
  } catch (err) {
    showToast(`Auth Error: ${err.message}`, 'error');
  } finally {
    btnText.textContent = 'Sign In as Admin';
    spinner.style.display = 'none';
    submitBtn.disabled = false;
  }
}

async function handleLogout() {
  try {
    await authFetch('/api/auth/logout', { method: 'POST' });
  } catch (_) {}

  state.token = '';
  localStorage.removeItem('bonz_admin_token');
  state.user = null;
  state.isSuperadmin = false;

  showToast('Logged out.', 'info');
  updateAuthUI();
}

// ==========================================================================
// Admin Panel Management (bonz Superadmin)
// ==========================================================================

function initAdminPanelTabs() {
  document.querySelectorAll('.admin-panel-tabs .tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const tabId = btn.dataset.tab;
      document.querySelectorAll('.admin-panel-tabs .tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.admin-panel-body .tab-content').forEach(c => c.classList.remove('active'));

      btn.classList.add('active');
      const target = document.getElementById(tabId);
      if (target) target.classList.add('active');
    });
  });

  // Forms in admin panel
  const addAdminForm = document.getElementById('form-add-admin');
  if (addAdminForm) addAdminForm.addEventListener('submit', handleAddAdmin);

  const addIpForm = document.getElementById('form-add-ip');
  if (addIpForm) addIpForm.addEventListener('submit', handleAddIp);

  const whitelistCurrentBtn = document.getElementById('btn-whitelist-current-ip');
  if (whitelistCurrentBtn) whitelistCurrentBtn.addEventListener('click', handleWhitelistCurrentIp);

  const changePassForm = document.getElementById('form-change-password');
  if (changePassForm) changePassForm.addEventListener('submit', handleChangePassword);
}

async function openAdminPanelModal() {
  const modal = document.getElementById('modal-admin-panel');
  const currentIpLabel = document.getElementById('admin-panel-current-ip');
  if (currentIpLabel) currentIpLabel.textContent = state.clientIp;

  if (modal) {
    modal.classList.add('active');
    await loadAdminUsersList();
    await loadSecuritySettings();
  }
}

async function loadAdminUsersList() {
  const container = document.getElementById('admin-users-list');
  if (!container) return;

  try {
    const res = await authFetch('/api/admin/users');
    if (!res.ok) throw new Error('Failed to load admins');
    const data = await res.json();

    container.innerHTML = data.users.map(u => `
      <div class="admin-user-row">
        <div class="admin-user-meta">
          <div class="admin-user-name">
            <span>${escapeHtml(u.display_name || u.username)}</span>
            <span class="card-badge-pill ${u.is_owner ? 'badge-emerald' : 'badge-violet'}">
              ${u.is_owner ? 'Superadmin (Owner)' : 'Admin'}
            </span>
          </div>
          <span class="admin-user-created">@${escapeHtml(u.username)} • Added: ${escapeHtml(u.created_at || 'Default')}</span>
        </div>
        ${!u.is_owner ? `
          <button class="btn-danger-sm" onclick="removeAdminUser('${escapeHtml(u.username)}')">Remove</button>
        ` : '<span class="text-muted" style="font-size:0.75rem;">Primary</span>'}
      </div>
    `).join('');
  } catch (err) {
    container.innerHTML = `<p class="form-hint">Could not load users: ${err.message}</p>`;
  }
}

async function handleAddAdmin(e) {
  e.preventDefault();
  const username = document.getElementById('new-admin-user').value.trim();
  const displayName = document.getElementById('new-admin-display').value.trim();
  const password = document.getElementById('new-admin-pass').value;

  try {
    const res = await authFetch('/api/admin/users', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, display_name: displayName, password, role: 'admin' })
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Could not add admin');

    showToast(`Admin user '${username}' added!`, 'success');
    e.target.reset();
    await loadAdminUsersList();
  } catch (err) {
    showToast(`Error: ${err.message}`, 'error');
  }
}

window.removeAdminUser = async function(username) {
  if (!confirm(`Are you sure you want to revoke admin privileges from ${username}?`)) return;

  try {
    const res = await authFetch(`/api/admin/users/${encodeURIComponent(username)}`, { method: 'DELETE' });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to remove admin');
    }
    showToast(`Admin '${username}' removed.`, 'info');
    await loadAdminUsersList();
  } catch (err) {
    showToast(`Error: ${err.message}`, 'error');
  }
};

async function loadSecuritySettings() {
  const container = document.getElementById('trusted-ips-list');
  if (!container) return;

  try {
    const res = await authFetch('/api/admin/security');
    if (!res.ok) throw new Error('Failed to load security config');
    const data = await res.json();

    container.innerHTML = data.trusted_ips.map(ip => `
      <span class="ip-chip">
        <span>${escapeHtml(ip)}</span>
        ${!['127.0.0.1', '::1', 'localhost'].includes(ip) ? `
          <button class="chip-del-btn" onclick="removeTrustedIp('${escapeHtml(ip)}')">&times;</button>
        ` : ''}
      </span>
    `).join('');
  } catch (err) {
    container.innerHTML = `<p class="form-hint">Could not load trusted IPs: ${err.message}</p>`;
  }
}

async function handleAddIp(e) {
  e.preventDefault();
  const input = document.getElementById('new-ip-pattern');
  const pattern = input.value.trim();

  try {
    const res = await authFetch('/api/admin/security/trusted-ips', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ip_pattern: pattern })
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to add IP');
    }

    showToast(`IP '${pattern}' added to whitelist.`, 'success');
    input.value = '';
    await loadSecuritySettings();
  } catch (err) {
    showToast(`Error: ${err.message}`, 'error');
  }
}

async function handleWhitelistCurrentIp() {
  if (!state.clientIp) return;
  try {
    const res = await authFetch('/api/admin/security/trusted-ips', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ip_pattern: state.clientIp })
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to whitelist IP');
    }
    showToast(`Current IP (${state.clientIp}) is now whitelisted!`, 'success');
    state.isIpTrusted = true;
    await loadSecuritySettings();
    updateAuthUI();
  } catch (err) {
    showToast(`Error: ${err.message}`, 'error');
  }
}

window.removeTrustedIp = async function(ip) {
  try {
    const res = await authFetch(`/api/admin/security/trusted-ips/${encodeURIComponent(ip)}`, { method: 'DELETE' });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to remove IP');
    }
    showToast(`IP '${ip}' removed.`, 'info');
    await loadSecuritySettings();
  } catch (err) {
    showToast(`Error: ${err.message}`, 'error');
  }
};

async function handleChangePassword(e) {
  e.preventDefault();
  const currentPassword = document.getElementById('curr-pass').value;
  const newPassword = document.getElementById('new-pass').value;

  try {
    const res = await authFetch('/api/auth/change-password', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ current_password: currentPassword, new_password: newPassword })
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Could not update password');
    }
    showToast('Password updated successfully!', 'success');
    e.target.reset();
  } catch (err) {
    showToast(`Error: ${err.message}`, 'error');
  }
}

// ==========================================================================
// System Status & Metrics
// ==========================================================================

async function initSystemStatus() {
  try {
    const res = await fetch('/api/system/status');
    if (!res.ok) throw new Error('Status endpoint failed');
    const data = await res.json();

    const statusPill = document.getElementById('system-status-text');
    const userText = document.getElementById('system-user-text');
    const diskStat = document.getElementById('stat-disk-free');

    if (statusPill) statusPill.textContent = 'Server Online';
    if (userText) userText.textContent = `@${data.github.user}`;
    if (diskStat && data.disk) {
      diskStat.textContent = `${data.disk.free_gb} GB`;
    }
  } catch (err) {
    const statusPill = document.getElementById('system-status-text');
    if (statusPill) statusPill.textContent = 'Standby Mode';
  }
}

// ==========================================================================
// Interactive 3D Cube Viewer
// ==========================================================================

function init3DCube() {
  const cube = document.getElementById('interactive-cube');
  const dragArea = document.getElementById('cube-drag-area');
  const toggleBtn = document.getElementById('btn-toggle-rotation');
  const resetBtn = document.getElementById('btn-reset-cube');
  const rotText = document.getElementById('cube-rot-text');

  if (!cube || !dragArea) return;

  function updateCubeTransform() {
    cube.style.transform = `rotateX(${state.rotationX}deg) rotateY(${state.rotationY}deg)`;
  }

  function animateCube() {
    if (!state.isDragging) {
      if (state.isAutoRotating) {
        state.rotationY += 0.28;
      }
      if (Math.abs(state.velocityX) > 0.01 || Math.abs(state.velocityY) > 0.01) {
        state.rotationY += state.velocityX;
        state.rotationX -= state.velocityY;
        state.velocityX *= 0.92;
        state.velocityY *= 0.92;
      }
      updateCubeTransform();
    }
    state.animationFrameId = requestAnimationFrame(animateCube);
  }
  state.animationFrameId = requestAnimationFrame(animateCube);

  function startDrag(clientX, clientY) {
    state.isDragging = true;
    state.lastMouseX = clientX;
    state.lastMouseY = clientY;
    state.velocityX = 0;
    state.velocityY = 0;
  }

  function moveDrag(clientX, clientY) {
    if (!state.isDragging) return;
    const deltaX = clientX - state.lastMouseX;
    const deltaY = clientY - state.lastMouseY;

    state.velocityX = deltaX * 0.45;
    state.velocityY = deltaY * 0.45;

    state.rotationY += state.velocityX;
    state.rotationX -= state.velocityY;

    state.lastMouseX = clientX;
    state.lastMouseY = clientY;
    updateCubeTransform();
  }

  function endDrag() {
    state.isDragging = false;
  }

  dragArea.addEventListener('mousedown', (e) => {
    if (e.button === 0) startDrag(e.clientX, e.clientY);
  });
  window.addEventListener('mousemove', (e) => moveDrag(e.clientX, e.clientY));
  window.addEventListener('mouseup', endDrag);

  dragArea.addEventListener('touchstart', (e) => {
    if (e.touches.length === 1) startDrag(e.touches[0].clientX, e.touches[0].clientY);
  }, { passive: true });

  window.addEventListener('touchmove', (e) => {
    if (e.touches.length === 1) moveDrag(e.touches[0].clientX, e.touches[0].clientY);
  }, { passive: true });

  window.addEventListener('touchend', endDrag);

  if (toggleBtn) {
    toggleBtn.addEventListener('click', () => {
      state.isAutoRotating = !state.isAutoRotating;
      rotText.textContent = state.isAutoRotating ? 'Pause Spin' : 'Resume Spin';
    });
  }

  if (resetBtn) {
    resetBtn.addEventListener('click', () => {
      state.rotationX = -15;
      state.rotationY = 25;
      state.velocityX = 0;
      state.velocityY = 0;
      updateCubeTransform();
    });
  }

  document.querySelectorAll('.cube-face').forEach((face) => {
    face.addEventListener('click', () => {
      if (Math.abs(state.velocityX) > 1.5 || Math.abs(state.velocityY) > 1.5) return;
      const target = face.dataset.target;
      if (!target) return;

      if (target.startsWith('#')) {
        const el = document.querySelector(target);
        if (el) el.scrollIntoView({ behavior: 'smooth' });
      } else {
        window.open(target, '_blank', 'noopener');
      }
    });
  });
}

// ==========================================================================
// CMS Launchpad Projects
// ==========================================================================

async function initProjectsCMS() {
  await loadProjects();

  const addBtn = document.getElementById('btn-add-project-banner');
  if (addBtn) addBtn.addEventListener('click', () => openProjectModal());

  const form = document.getElementById('form-edit-project');
  if (form) form.addEventListener('submit', handleSaveProject);
}

async function loadProjects() {
  const grid = document.getElementById('launchpad-grid');
  try {
    const res = await fetch('/api/cms/projects');
    if (!res.ok) throw new Error('Failed to load projects');
    const data = await res.json();
    state.projects = data.projects || [];
    renderProjects();

    const countStat = document.getElementById('stat-projects-count');
    if (countStat) countStat.textContent = state.projects.length;
  } catch (err) {
    if (grid) grid.innerHTML = `<div class="loading-spinner-wrapper"><p>Could not load projects: ${err.message}</p></div>`;
  }
}

function renderProjects() {
  const grid = document.getElementById('launchpad-grid');
  if (!grid) return;

  if (state.projects.length === 0) {
    grid.innerHTML = `<div class="loading-spinner-wrapper"><p>No projects configured yet.</p></div>`;
    return;
  }

  const isLogged = Boolean(state.user);

  grid.innerHTML = state.projects.map((p) => {
    const badgeColor = p.badge_color || 'cyan';
    const hasGitHub = Boolean(p.github_url);

    return `
      <div class="project-card" data-id="${escapeHtml(p.id)}">
        <div class="card-top">
          <span class="card-badge-pill badge-${escapeHtml(badgeColor)}">${escapeHtml(p.badge || 'Project')}</span>
          ${isLogged ? `
            <div class="card-actions-quick">
              <button class="card-menu-btn" onclick="editProject('${p.id}')" title="Edit Card">
                <svg class="icon" viewBox="0 0 24 24"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>
              </button>
              <button class="card-menu-btn" onclick="deleteProject('${p.id}')" title="Delete Card">
                <svg class="icon" viewBox="0 0 24 24"><path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
              </button>
            </div>
          ` : ''}
        </div>

        <div class="card-body">
          <h3 class="card-title">${escapeHtml(p.title)}</h3>
          ${p.subtitle ? `<div class="card-subtitle">${escapeHtml(p.subtitle)}</div>` : ''}
          <p class="card-desc">${escapeHtml(p.description || '')}</p>
        </div>

        <div class="card-footer-actions">
          <a href="${escapeHtml(p.url)}" target="${p.url.startsWith('#') ? '_self' : '_blank'}" rel="noopener" class="btn btn-primary card-launch-btn">
            <span>Launch App</span>
            <svg class="icon" viewBox="0 0 24 24"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6M15 3h6v6M10 14L21 3"/></svg>
          </a>
          ${hasGitHub ? `
            <a href="${escapeHtml(p.github_url)}" target="_blank" rel="noopener" class="btn btn-outline btn-sm" title="View Source on GitHub">
              <svg class="icon" viewBox="0 0 24 24"><path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22"/></svg>
            </a>
          ` : ''}
        </div>
      </div>
    `;
  }).join('');
}

function openProjectModal(project = null) {
  if (!state.user) {
    showToast('Admin authentication required to manage project cards.', 'error');
    openLoginModal();
    return;
  }

  const modal = document.getElementById('modal-edit-project');
  const title = document.getElementById('modal-project-title');
  const form = document.getElementById('form-edit-project');
  if (!modal || !form) return;

  form.reset();

  if (project) {
    title.textContent = 'Edit Launchpad Project';
    document.getElementById('project-edit-id').value = project.id;
    document.getElementById('proj-title').value = project.title || '';
    document.getElementById('proj-category').value = project.category || '';
    document.getElementById('proj-subtitle').value = project.subtitle || '';
    document.getElementById('proj-desc').value = project.description || '';
    document.getElementById('proj-url').value = project.url || '';
    document.getElementById('proj-github').value = project.github_url || '';
    document.getElementById('proj-badge').value = project.badge || '';
    document.getElementById('proj-color').value = project.badge_color || 'cyan';
    document.getElementById('proj-priority').value = project.priority || 5;
  } else {
    title.textContent = 'Add Launchpad Project';
    document.getElementById('project-edit-id').value = '';
    document.getElementById('proj-priority').value = state.projects.length + 1;
  }

  modal.classList.add('active');
}

window.editProject = function(id) {
  const proj = state.projects.find(p => p.id === id);
  if (proj) openProjectModal(proj);
};

window.deleteProject = async function(id) {
  if (!confirm(`Are you sure you want to delete this project card?`)) return;
  try {
    const res = await authFetch(`/api/cms/projects/${encodeURIComponent(id)}`, { method: 'DELETE' });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to delete project');
    }
    showToast('Project card removed.', 'info');
    await loadProjects();
  } catch (err) {
    showToast(`Error: ${err.message}`, 'error');
  }
};

async function handleSaveProject(e) {
  e.preventDefault();
  const editId = document.getElementById('project-edit-id').value.trim();

  const payload = {
    title: document.getElementById('proj-title').value.trim(),
    category: document.getElementById('proj-category').value.trim(),
    subtitle: document.getElementById('proj-subtitle').value.trim(),
    description: document.getElementById('proj-desc').value.trim(),
    url: document.getElementById('proj-url').value.trim(),
    github_url: document.getElementById('proj-github').value.trim() || null,
    badge: document.getElementById('proj-badge').value.trim() || 'Project',
    badge_color: document.getElementById('proj-color').value,
    priority: parseInt(document.getElementById('proj-priority').value, 10) || 5,
    featured: true
  };

  const isEdit = Boolean(editId);
  const endpoint = isEdit ? `/api/cms/projects/${encodeURIComponent(editId)}` : '/api/cms/projects';
  const method = isEdit ? 'PUT' : 'POST';

  try {
    const res = await authFetch(endpoint, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!res.ok) {
      const errData = await res.json();
      throw new Error(errData.detail || 'Could not save project');
    }

    showToast(`Project ${isEdit ? 'updated' : 'created'} successfully!`, 'success');
    document.getElementById('modal-edit-project').classList.remove('active');
    await loadProjects();
  } catch (err) {
    showToast(`Error: ${err.message}`, 'error');
  }
}

// ==========================================================================
// GitHub Repositories Hub
// ==========================================================================

async function initGitHubRepos() {
  await loadGitHubRepos();

  const refreshBtn = document.getElementById('btn-refresh-repos');
  const refreshIcon = document.getElementById('refresh-icon');
  if (refreshBtn) {
    refreshBtn.addEventListener('click', async () => {
      if (refreshIcon) refreshIcon.classList.add('spinning');
      await loadGitHubRepos(true);
      if (refreshIcon) refreshIcon.classList.remove('spinning');
      showToast('GitHub repositories synced.', 'success');
    });
  }

  const createRepoAction = document.getElementById('btn-create-repo-action');
  if (createRepoAction) {
    createRepoAction.addEventListener('click', () => {
      if (!state.user) {
        showToast('Admin login required to create GitHub repositories.', 'error');
        openLoginModal();
      } else {
        document.getElementById('modal-new-repo').classList.add('active');
      }
    });
  }

  const searchInput = document.getElementById('repo-search-input');
  const clearBtn = document.getElementById('btn-clear-search');
  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      state.searchQuery = e.target.value.toLowerCase().trim();
      if (clearBtn) clearBtn.style.display = state.searchQuery ? 'block' : 'none';
      filterAndRenderRepos();
    });
  }

  if (clearBtn && searchInput) {
    clearBtn.addEventListener('click', () => {
      searchInput.value = '';
      state.searchQuery = '';
      clearBtn.style.display = 'none';
      filterAndRenderRepos();
    });
  }

  const createForm = document.getElementById('form-create-repo');
  if (createForm) createForm.addEventListener('submit', handleCreateRepo);
}

async function loadGitHubRepos(force = false) {
  const grid = document.getElementById('repos-grid');
  try {
    const res = await fetch(`/api/repos?force=${force}`);
    if (!res.ok) throw new Error('Failed to fetch repositories from GitHub');
    const data = await res.json();
    state.repos = data.repos || [];

    const reposStat = document.getElementById('stat-repos-count');
    if (reposStat) reposStat.textContent = state.repos.length;

    populateLanguageChips();
    filterAndRenderRepos();
  } catch (err) {
    if (grid) {
      grid.innerHTML = `
        <div class="loading-spinner-wrapper">
          <p>Unable to sync GitHub repositories at this time.</p>
          <p class="form-hint">${err.message}</p>
        </div>
      `;
    }
  }
}

function populateLanguageChips() {
  const container = document.getElementById('repo-language-chips');
  if (!container) return;

  const langSet = new Set();
  state.repos.forEach(r => {
    if (r.language && r.language !== 'Code') langSet.add(r.language);
  });

  const languages = ['all', ...Array.from(langSet).sort()];
  container.innerHTML = languages.map(lang => `
    <button class="filter-chip ${state.selectedLanguage === lang ? 'active' : ''}" data-lang="${lang}">
      ${lang === 'all' ? 'All' : lang}
    </button>
  `).join('');

  container.querySelectorAll('.filter-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      state.selectedLanguage = chip.dataset.lang;
      container.querySelectorAll('.filter-chip').forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
      filterAndRenderRepos();
    });
  });
}

function filterAndRenderRepos() {
  const grid = document.getElementById('repos-grid');
  if (!grid) return;

  const filtered = state.repos.filter(r => {
    const matchesLang = state.selectedLanguage === 'all' || r.language === state.selectedLanguage;
    const matchesSearch = !state.searchQuery ||
      r.name.toLowerCase().includes(state.searchQuery) ||
      (r.description && r.description.toLowerCase().includes(state.searchQuery));
    return matchesLang && matchesSearch;
  });

  if (filtered.length === 0) {
    grid.innerHTML = `<div class="loading-spinner-wrapper"><p>No matching repositories found.</p></div>`;
    return;
  }

  grid.innerHTML = filtered.map(r => {
    const langColor = LANG_COLORS[r.language] || LANG_COLORS.default;
    const formattedDate = new Date(r.updated_at).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric'
    });

    return `
      <div class="repo-card">
        <div>
          <div class="repo-card-header">
            <a href="${escapeHtml(r.html_url)}" target="_blank" rel="noopener" class="repo-name-link">
              ${escapeHtml(r.name)}
            </a>
            ${r.private ? '<span class="card-badge-pill badge-rose">Private</span>' : '<span class="card-badge-pill badge-cyan">Public</span>'}
          </div>
          <p class="repo-desc">${escapeHtml(r.description)}</p>
        </div>

        <div class="repo-card-meta">
          <div class="repo-meta-left">
            <span class="repo-lang">
              <span class="lang-dot" style="background-color: ${langColor};"></span>
              <span>${escapeHtml(r.language)}</span>
            </span>
            <span title="Last updated">${formattedDate}</span>
          </div>
          <div class="repo-stats">
            <span class="repo-stat-item" title="Stars">
              <svg class="icon" viewBox="0 0 24 24"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
              <span>${r.stars}</span>
            </span>
            <button class="btn-sm btn-glass" style="padding: 2px 6px;" onclick="copyCloneUrl('${escapeHtml(r.clone_url)}')" title="Copy Clone URL">
              <svg class="icon" viewBox="0 0 24 24"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>
            </button>
          </div>
        </div>
      </div>
    `;
  }).join('');
}

window.copyCloneUrl = function(url) {
  navigator.clipboard.writeText(url).then(() => {
    showToast('Clone URL copied to clipboard!', 'info');
  }).catch(() => {
    prompt('Clone URL:', url);
  });
};

async function handleCreateRepo(e) {
  e.preventDefault();
  const submitBtn = document.getElementById('btn-submit-create-repo');
  const btnText = submitBtn.querySelector('.btn-text');
  const spinner = submitBtn.querySelector('.btn-spinner');

  const payload = {
    name: document.getElementById('new-repo-name').value.trim(),
    description: document.getElementById('new-repo-desc').value.trim() || null,
    private: document.getElementById('new-repo-private').checked,
    auto_init: document.getElementById('new-repo-autoinit').checked
  };

  btnText.textContent = 'Creating...';
  spinner.style.display = 'inline-block';
  submitBtn.disabled = true;

  try {
    const res = await authFetch('/api/repos/create', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Repo creation failed');

    showToast(`Repository ${data.repo.name} created!`, 'success');
    document.getElementById('modal-new-repo').classList.remove('active');
    e.target.reset();

    await loadGitHubRepos(true);
  } catch (err) {
    showToast(`GitHub Error: ${err.message}`, 'error');
  } finally {
    btnText.textContent = 'Create Repository';
    spinner.style.display = 'none';
    submitBtn.disabled = false;
  }
}

// ==========================================================================
// Server File & Folder Manager (CMS)
// ==========================================================================

async function initServerFileManager() {
  if (state.user) {
    await loadServerFolders('');
  }

  const refreshBtn = document.getElementById('btn-refresh-server-folders');
  if (refreshBtn) {
    refreshBtn.addEventListener('click', () => loadServerFolders(state.serverCurrentPath));
  }

  const createFolderBtn = document.getElementById('btn-server-create-folder');
  if (createFolderBtn) {
    createFolderBtn.addEventListener('click', () => openCreateFolderModal(state.serverCurrentPath));
  }

  const form = document.getElementById('form-create-folder');
  if (form) form.addEventListener('submit', handleCreateFolder);
}

async function loadServerFolders(subpath = '') {
  if (!state.user) return;

  const listEl = document.getElementById('server-file-list');
  try {
    const res = await authFetch(`/api/server/folders?subpath=${encodeURIComponent(subpath)}`);
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Could not read server folder');
    }
    const data = await res.json();

    state.serverCurrentPath = data.current_path;
    state.serverBaseDir = data.base_dir;

    renderBreadcrumbs(data.current_path);
    renderFileList(data.items);
  } catch (err) {
    if (listEl) {
      listEl.innerHTML = `
        <div class="loading-spinner-wrapper">
          <p>Failed to inspect server directories.</p>
          <span class="form-hint">${err.message}</span>
        </div>
      `;
    }
  }
}

function renderBreadcrumbs(currentPath) {
  const container = document.getElementById('server-breadcrumbs');
  const baseLabel = document.getElementById('base-dir-label');
  if (!container) return;

  if (baseLabel && state.serverBaseDir) {
    baseLabel.textContent = state.serverBaseDir;
  }

  const parts = currentPath ? currentPath.split('/') : [];
  let html = `
    <span class="breadcrumb-item" onclick="navigateToFolder('')">
      <svg class="icon-inline" viewBox="0 0 24 24"><path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>
      <span>${state.serverBaseDir || 'Root'}</span>
    </span>
  `;

  let accumulated = '';
  parts.forEach((p) => {
    if (!p) return;
    accumulated = accumulated ? `${accumulated}/${p}` : p;
    html += `
      <span class="breadcrumb-sep">/</span>
      <span class="breadcrumb-item" onclick="navigateToFolder('${escapeHtml(accumulated)}')">${escapeHtml(p)}</span>
    `;
  });

  container.innerHTML = html;
}

window.navigateToFolder = function(path) {
  loadServerFolders(path);
};

function renderFileList(items) {
  const container = document.getElementById('server-file-list');
  if (!container) return;

  if (!items || items.length === 0) {
    container.innerHTML = `<div class="loading-spinner-wrapper"><p>This directory is currently empty.</p></div>`;
    return;
  }

  container.innerHTML = items.map(item => {
    const isDir = item.is_dir;
    const sizeFormatted = isDir ? '-' : formatBytes(item.size_bytes);
    const clickHandler = isDir ? `onclick="navigateToFolder('${escapeHtml(item.relative_path)}')"` : '';

    return `
      <div class="file-item-row ${isDir ? 'is-dir' : ''}" ${clickHandler}>
        <div class="item-icon">
          ${isDir ? `
            <svg viewBox="0 0 24 24"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
          ` : `
            <svg viewBox="0 0 24 24"><path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/></svg>
          `}
        </div>
        <div class="item-name">${escapeHtml(item.name)}</div>
        <div class="item-size">${sizeFormatted}</div>
        <div class="item-date">${escapeHtml(item.modified)}</div>
      </div>
    `;
  }).join('');
}

function formatBytes(bytes) {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function openCreateFolderModal(parentPath = '') {
  if (!state.user) {
    showToast('Admin login required to create server folders.', 'error');
    openLoginModal();
    return;
  }

  const modal = document.getElementById('modal-new-folder');
  const targetPreview = document.getElementById('modal-folder-target-preview');
  const hiddenInput = document.getElementById('folder-parent-path');
  const nameInput = document.getElementById('new-folder-name');

  if (!modal) return;
  hiddenInput.value = parentPath;
  targetPreview.textContent = parentPath ? `${state.serverBaseDir}/${parentPath}` : state.serverBaseDir;
  nameInput.value = '';
  modal.classList.add('active');
  setTimeout(() => nameInput.focus(), 50);
}

async function handleCreateFolder(e) {
  e.preventDefault();
  const submitBtn = document.getElementById('btn-submit-create-folder');
  const btnText = submitBtn.querySelector('.btn-text');
  const spinner = submitBtn.querySelector('.btn-spinner');

  const payload = {
    folder_name: document.getElementById('new-folder-name').value.trim(),
    parent_path: document.getElementById('folder-parent-path').value.trim()
  };

  btnText.textContent = 'Creating...';
  spinner.style.display = 'inline-block';
  submitBtn.disabled = true;

  try {
    const res = await authFetch('/api/server/folders/create', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Folder creation failed');

    showToast(`Folder '${payload.folder_name}' created on server!`, 'success');
    document.getElementById('modal-new-folder').classList.remove('active');
    e.target.reset();

    await loadServerFolders(payload.parent_path);
  } catch (err) {
    showToast(`Error: ${err.message}`, 'error');
  } finally {
    btnText.textContent = 'Create Folder';
    spinner.style.display = 'none';
    submitBtn.disabled = false;
  }
}

// ==========================================================================
// Modals System
// ==========================================================================

function initModals() {
  const openRepoBtn = document.getElementById('btn-open-new-repo');
  const openFolderBtn = document.getElementById('btn-open-new-folder');
  const openAddProjectBtn = document.getElementById('btn-open-add-project');

  if (openRepoBtn) openRepoBtn.addEventListener('click', () => {
    if (!state.user) {
      showToast('Admin login required to create GitHub repositories.', 'error');
      openLoginModal();
    } else {
      document.getElementById('modal-new-repo').classList.add('active');
    }
  });

  if (openFolderBtn) openFolderBtn.addEventListener('click', () => openCreateFolderModal(state.serverCurrentPath));
  if (openAddProjectBtn) openAddProjectBtn.addEventListener('click', () => openProjectModal());

  document.querySelectorAll('[data-close]').forEach(btn => {
    btn.addEventListener('click', () => {
      const modalId = btn.dataset.close;
      const modal = document.getElementById(modalId);
      if (modal) modal.classList.remove('active');
    });
  });

  document.querySelectorAll('.modal-overlay').forEach(modal => {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) modal.classList.remove('active');
    });
  });

  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      document.querySelectorAll('.modal-overlay.active').forEach(m => m.classList.remove('active'));
    }
  });
}
