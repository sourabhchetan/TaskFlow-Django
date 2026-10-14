// To-Do List — small progressive-enhancement JS layer.
// The app works with plain HTML forms/links; everything here is additive
// polish (theme persistence, sidebar collapse, mobile nav, delete
// confirmation, toast animation, debounced search, entrance animations,
// button loading states). Nothing here is required for the app to function,
// and every animation respects prefers-reduced-motion.

var REDUCED_MOTION = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

document.addEventListener('DOMContentLoaded', function () {
  initThemeToggle();
  initSidebarCollapse();
  initMobileNav();
  initUserMenu();
  initNotifDropdown();
  initConfirmations(); // must run before initFormLoadingState so it can intercept submit first
  initToastAutoDismiss();
  initSearchAutoSubmit();
  initFormLoadingState();
  animateProgressBars();
  animateStatNumbers();
  initAjaxTaskActions();
  initBulkSelection();
  initFilterPanelToggle();
  initKeyboardShortcuts();
  initPasswordToggles();
});

function initThemeToggle() {
  var toggle = document.getElementById('themeToggle');
  if (!toggle) return;
  toggle.addEventListener('click', function () {
    var root = document.documentElement;
    var next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
    root.setAttribute('data-theme', next);
    localStorage.setItem('todo-theme', next);
  });
}

function initSidebarCollapse() {
  // Desktop-only affordance (hidden on tablet/mobile via CSS); persists the
  // user's choice per-device the same way the theme toggle does.
  var btn = document.getElementById('sidebarCollapseBtn');
  var sidebar = document.getElementById('sidebar');
  if (!btn || !sidebar) return;

  function apply(collapsed) {
    sidebar.classList.toggle('collapsed', collapsed);
    // The button now sits in the topbar rather than inside #sidebar, so its
    // own chevron-flip state (see .sidebar-collapse-btn.collapsed in the
    // CSS) needs its own class instead of inheriting from a .sidebar
    // ancestor selector.
    btn.classList.toggle('collapsed', collapsed);
    btn.setAttribute('aria-label', collapsed ? 'Expand sidebar' : 'Collapse sidebar');
    btn.setAttribute('title', collapsed ? 'Expand sidebar' : 'Collapse sidebar');

    // Move the native `title` onto `data-tooltip` permanently. The browser's
    // grey tooltip rectangle is never wanted here: when expanded the label
    // is already visible (so a tooltip is pure noise), and when collapsed we
    // draw our own styled tooltip from data-tooltip. The title is NOT
    // restored on expand — doing so made the OS box appear on hover over
    // fully-labelled nav items. aria-label below keeps it screen-reader safe.
    sidebar.querySelectorAll('.filter-btn').forEach(function (item) {
      var label = item.getAttribute('title');
      if (label) {
        item.setAttribute('data-tooltip', label);
        if (!item.getAttribute('aria-label')) item.setAttribute('aria-label', label);
        item.removeAttribute('title');
      }
    });
  }

  apply(localStorage.getItem('todo-sidebar-collapsed') === 'true');

  btn.addEventListener('click', function () {
    var collapsed = !sidebar.classList.contains('collapsed');
    apply(collapsed);
    localStorage.setItem('todo-sidebar-collapsed', collapsed);
  });
}

function initMobileNav() {
  var hamburger = document.getElementById('hamburgerBtn');
  var sidebar = document.getElementById('sidebar');
  var backdrop = document.getElementById('sidebarBackdrop');
  if (!hamburger || !sidebar || !backdrop) return;

  function open() {
    sidebar.classList.add('open');
    backdrop.classList.add('open');
    document.body.classList.add('no-scroll'); // prevent background scroll while drawer is open
  }
  function close() {
    sidebar.classList.remove('open');
    backdrop.classList.remove('open');
    document.body.classList.remove('no-scroll');
  }
  hamburger.addEventListener('click', function () {
    sidebar.classList.contains('open') ? close() : open();
  });
  backdrop.addEventListener('click', close);
  sidebar.querySelectorAll('a').forEach(function (link) {
    link.addEventListener('click', close);
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') close();
  });
}

function initUserMenu() {
  var btn = document.getElementById('userMenuBtn');
  var dropdown = document.getElementById('userDropdown');
  if (!btn || !dropdown) return;
  btn.addEventListener('click', function (e) {
    e.stopPropagation();
    dropdown.classList.toggle('open');
    btn.setAttribute('aria-expanded', dropdown.classList.contains('open'));
  });
  document.addEventListener('click', function () {
    dropdown.classList.remove('open');
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      dropdown.classList.remove('open');
      btn.setAttribute('aria-expanded', 'false');
    }
  });
}

function initNotifDropdown() {
  var btn = document.getElementById('notifBtn');
  var dropdown = document.getElementById('notifDropdown');
  if (!btn || !dropdown) return;
  btn.addEventListener('click', function (e) {
    e.stopPropagation();
    dropdown.classList.toggle('open');
    btn.setAttribute('aria-expanded', dropdown.classList.contains('open'));
  });
  document.addEventListener('click', function () {
    dropdown.classList.remove('open');
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      dropdown.classList.remove('open');
      btn.setAttribute('aria-expanded', 'false');
    }
  });
}

function initConfirmations() {
  // Replaces window.confirm() with the custom modal in base.html, for any
  // form carrying data-confirm (e.g. category delete), or any form with a
  // specific submit *button* carrying data-confirm (e.g. the bulk-action
  // toolbar, where only its Delete button needs confirming — Complete/Pin
  // etc. on the same form must not be interrupted).
  //
  // .ajax-task-form elements (single-task complete/pin/delete) are handled
  // inline inside initAjaxTaskActions() instead, since those already run
  // through an async fetch flow rather than a real form submission.
  document.querySelectorAll('form').forEach(function (form) {
    if (form.classList.contains('ajax-task-form')) return;
    var hasFormConfirm = !!form.dataset.confirm;
    var hasButtonConfirm = !!form.querySelector('[data-confirm]');
    if (!hasFormConfirm && !hasButtonConfirm) return;

    form.addEventListener('submit', function (e) {
      if (form.dataset.skipConfirm) {
        delete form.dataset.skipConfirm;
        return; // this is our own re-submit after the user already confirmed
      }
      var submitter = e.submitter;
      var message = (submitter && submitter.dataset.confirm) || form.dataset.confirm;
      if (!message) return; // this particular submit button isn't destructive

      e.preventDefault();
      e.stopImmediatePropagation(); // don't let e.g. the loading-spinner handler fire yet
      showConfirmModal(message).then(function (confirmed) {
        if (!confirmed) return;
        form.dataset.skipConfirm = '1';
        if (form.requestSubmit) {
          form.requestSubmit(submitter || undefined);
        } else {
          HTMLFormElement.prototype.submit.call(form);
        }
      });
    });
  });
}

function showConfirmModal(message, options) {
  options = options || {};
  var overlay = document.getElementById('confirmOverlay');
  var titleEl = document.getElementById('confirmTitle');
  var bodyEl = document.getElementById('confirmBody');
  var cancelBtn = document.getElementById('confirmCancelBtn');
  var acceptBtn = document.getElementById('confirmAcceptBtn');

  // Logged-out pages (login/register) don't render the modal markup at
  // all — fall back to the native dialog rather than silently doing
  // nothing (this path shouldn't normally be reachable, since nothing on
  // those pages carries data-confirm, but it's a safe default regardless).
  if (!overlay || !cancelBtn || !acceptBtn) {
    return Promise.resolve(window.confirm(message));
  }

  return new Promise(function (resolve) {
    titleEl.textContent = options.title || 'Are you sure?';
    bodyEl.textContent = message;
    acceptBtn.textContent = options.confirmLabel || 'Confirm';
    acceptBtn.disabled = false;

    var previouslyFocused = document.activeElement;
    var focusable = [cancelBtn, acceptBtn];

    function cleanup(result) {
      overlay.classList.remove('open');
      document.body.classList.remove('no-scroll');
      document.removeEventListener('keydown', onKeydown, true);
      cancelBtn.removeEventListener('click', onCancel);
      acceptBtn.removeEventListener('click', onAccept);
      overlay.removeEventListener('mousedown', onBackdrop);
      if (previouslyFocused && typeof previouslyFocused.focus === 'function') {
        previouslyFocused.focus();
      }
      resolve(result);
    }
    function onCancel() { cleanup(false); }
    function onAccept() {
      acceptBtn.disabled = true; // guard against a double-click submitting twice
      cleanup(true);
    }
    function onBackdrop(e) { if (e.target === overlay) cleanup(false); }
    function onKeydown(e) {
      if (e.key === 'Escape') {
        e.stopPropagation();
        cleanup(false);
        return;
      }
      if (e.key === 'Tab') {
        e.preventDefault();
        var idx = focusable.indexOf(document.activeElement);
        var step = e.shiftKey ? -1 : 1;
        var next = (idx + step + focusable.length) % focusable.length;
        focusable[next].focus();
      }
    }

    cancelBtn.addEventListener('click', onCancel);
    acceptBtn.addEventListener('click', onAccept);
    overlay.addEventListener('mousedown', onBackdrop);
    document.addEventListener('keydown', onKeydown, true); // capture: wins over other Escape handlers

    overlay.classList.add('open');
    document.body.classList.add('no-scroll');
    cancelBtn.focus();
  });
}

function initToastAutoDismiss() {
  var toasts = document.querySelectorAll('.toast');
  toasts.forEach(function (toast) {
    setTimeout(function () {
      toast.classList.add('is-leaving');
      setTimeout(function () { toast.remove(); }, REDUCED_MOTION ? 0 : 220);
    }, 4000);
  });
}

function initSearchAutoSubmit() {
  var input = document.getElementById('searchInput');
  if (!input) return;
  var timer = null;
  input.addEventListener('input', function () {
    clearTimeout(timer);
    timer = setTimeout(function () {
      input.form.requestSubmit ? input.form.requestSubmit() : input.form.submit();
    }, 450);
  });
}

function initFormLoadingState() {
  // Purely visual feedback on submit (spinner + disabled state) for forms
  // that navigate to a new page — the normal full-page-load form flow is
  // unchanged, this just avoids a "did my click register?" dead moment.
  // Forms handled by initAjaxTaskActions() manage their own button state,
  // since they don't navigate away.
  document.querySelectorAll('form').forEach(function (form) {
    if (form.classList.contains('ajax-task-form')) return;
    form.addEventListener('submit', function (e) {
      if (e.defaultPrevented) return; // e.g. a delete confirmation was cancelled
      var submitBtn = form.querySelector('button[type="submit"]');
      if (!submitBtn || submitBtn.disabled) return;
      var label = submitBtn.textContent;
      submitBtn.dataset.originalLabel = label;
      submitBtn.disabled = true;
      submitBtn.innerHTML = '<span class="btn-spinner" aria-hidden="true"></span>' + label;
    });
  });
}

function animateStatNumbers() {
  // Count up from 0 to the server-rendered value on first paint. Skipped
  // entirely under reduced motion, in which case the static number (already
  // correct in the HTML) is simply left alone.
  if (REDUCED_MOTION) return;

  document.querySelectorAll('.stat-card strong').forEach(function (el) {
    var target = parseInt(el.textContent.replace(/[^0-9-]/g, ''), 10);
    if (isNaN(target)) return; // e.g. a "50%" or non-numeric value — leave as-is
    var isPercent = el.textContent.trim().endsWith('%');
    var duration = 500;
    var start = null;

    function step(timestamp) {
      if (start === null) start = timestamp;
      var progress = Math.min((timestamp - start) / duration, 1);
      var eased = 1 - Math.pow(1 - progress, 3); // ease-out cubic
      var current = Math.round(target * eased);
      el.textContent = isPercent ? current + '%' : String(current);
      if (progress < 1) {
        requestAnimationFrame(step);
      } else {
        el.textContent = isPercent ? target + '%' : String(target);
      }
    }
    requestAnimationFrame(step);
  });
}

function animateProgressBars() {
  // Bars/tracks are rendered server-side with their final width/height
  // already inline (so the page is correct with JS disabled); when JS is
  // available and motion isn't reduced, we animate from zero to that value
  // for a subtle "filling in" effect on page load.
  if (REDUCED_MOTION) return;

  document.querySelectorAll('.progress-bar, .bar-fill, .priority-bar-fill').forEach(function (el) {
    var target = el.style.width;
    if (!target) return;
    el.style.width = '0%';
    requestAnimationFrame(function () {
      requestAnimationFrame(function () { el.style.width = target; });
    });
  });

  document.querySelectorAll('.weekly-bar').forEach(function (el) {
    var target = el.style.height;
    if (!target) return;
    el.style.height = '0%';
    requestAnimationFrame(function () {
      requestAnimationFrame(function () { el.style.height = target; });
    });
  });
}

// ---------------------------------------------------------------------------
// Quick task actions (AJAX) — Feature 1
//
// Each of the three per-task forms (complete/reopen, pin/unpin, delete)
// still works as a normal form post: if fetch isn't available, or the
// request fails, we simply let the browser submit the form for real and
// the page reloads with the change applied (the exact old behavior). When
// fetch succeeds, we update the DOM in place instead — no reload.
// ---------------------------------------------------------------------------
function initAjaxTaskActions() {
  if (!window.fetch) return; // no fetch => every form just submits normally

  document.querySelectorAll('.ajax-task-form').forEach(function (form) {
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var action = form.dataset.ajaxAction;

      function proceed() {
        var card = form.closest('.task-card');
        var submitBtn = form.querySelector('button[type="submit"]');
        if (submitBtn) submitBtn.disabled = true;

        fetch(form.action, {
          method: 'POST',
          body: new FormData(form),
          headers: { 'X-Requested-With': 'XMLHttpRequest' },
          credentials: 'same-origin',
        })
          .then(function (response) {
            if (!response.ok) throw new Error('Request failed');
            return response.json();
          })
          .then(function (data) {
            if (!data.ok) throw new Error(data.message || 'Request failed');
            applyDashboardCounters(data);
            showClientToast(data.message, 'success');

            if (action === 'toggle') {
              applyTaskToggleResult(card, form, data);
              maybeCelebrateCompletion(data);
            } else if (action === 'pin') {
              applyTaskPinResult(card, form, data);
            } else if (action === 'delete') {
              removeTaskCard(card);
            }
          })
          .catch(function () {
            // Fall back to a real submit so the action still completes.
            if (submitBtn) submitBtn.disabled = false;
            HTMLFormElement.prototype.submit.call(form);
          });
      }

      if (action === 'delete' && form.dataset.confirm) {
        showConfirmModal(form.dataset.confirm).then(function (confirmed) {
          if (confirmed) proceed();
        });
      } else {
        proceed();
      }
    });
  });
}

function applyTaskToggleResult(card, form, data) {
  if (!card) return;
  card.classList.toggle('is-completed', data.completed);
  var checkbox = form.querySelector('.task-checkbox');
  if (checkbox) {
    checkbox.innerHTML = data.completed ? (checkbox.dataset.checkIcon || '') : '';
    checkbox.setAttribute('aria-label', data.completed ? 'Mark active again' : 'Mark complete');
  }
  var countdown = card.querySelector('.countdown');
  if (countdown && data.countdown_text !== undefined) {
    countdown.textContent = data.countdown_text;
    countdown.classList.toggle('overdue-tag', !!data.is_overdue);
  }
  if (form.querySelector('button[type="submit"]')) {
    form.querySelector('button[type="submit"]').disabled = false;
  }
}

function applyTaskPinResult(card, form, data) {
  if (!card) return;
  var pinBtn = form.querySelector('button[type="submit"]');
  if (pinBtn) {
    pinBtn.classList.toggle('active', !!data.pinned);
    pinBtn.disabled = false;
    pinBtn.setAttribute('aria-label', data.pinned ? 'Unpin task' : 'Pin task');
  }
}

function removeTaskCard(card) {
  if (!card) return;
  if (REDUCED_MOTION) {
    card.remove();
    return;
  }
  card.classList.add('is-removing');
  card.addEventListener('animationend', function () { card.remove(); }, { once: true });
}

function applyDashboardCounters(data) {
  if (data.stats) {
    setStatNumber('statTotal', data.stats.total);
    setStatNumber('statActive', data.stats.active);
    setStatNumber('statCompleted', data.stats.completed);
    setStatNumber('statOverdue', data.stats.overdue);
  }
  if (typeof data.progress_pct === 'number') {
    var bar = document.getElementById('progressBarFill');
    if (bar) bar.style.width = data.progress_pct + '%';
    var text = document.getElementById('progressText');
    if (text && data.stats) {
      text.textContent = data.stats.completed + ' / ' + data.stats.total + ' tasks completed (' + data.progress_pct + '%)';
    }
  }
  if (data.sidebar_counts) {
    var map = {
      all: 'sidebarCountAll', today: 'sidebarCountToday', upcoming: 'sidebarCountUpcoming',
      overdue: 'sidebarCountOverdue', high: 'sidebarCountHigh', pinned: 'sidebarCountPinned',
      completed: 'sidebarCountCompleted',
    };
    Object.keys(map).forEach(function (key) {
      setStatNumber(map[key], data.sidebar_counts[key]);
    });
  }
}

function setStatNumber(elementId, value) {
  var el = document.getElementById(elementId);
  if (!el || value === undefined || value === null) return;
  var next = String(value);
  if (el.textContent !== next) {
    el.textContent = next;
    if (!REDUCED_MOTION && el.tagName === 'B') {
      el.classList.remove('is-updating');
      // eslint-disable-next-line no-unused-expressions
      void el.offsetWidth; // restart the animation if it's already mid-pulse
      el.classList.add('is-updating');
    }
  }
}

function showClientToast(message, tone) {
  if (!message) return;
  var stack = document.getElementById('toastStack');
  if (!stack) {
    stack = document.createElement('div');
    stack.className = 'toast-stack';
    stack.id = 'toastStack';
    stack.setAttribute('role', 'status');
    stack.setAttribute('aria-live', 'polite');
    document.body.appendChild(stack);
  }
  var toast = document.createElement('div');
  toast.className = 'toast toast-' + (tone || 'success');
  toast.textContent = message;
  var progress = document.createElement('span');
  progress.className = 'toast-progress';
  toast.appendChild(progress);
  stack.appendChild(toast);
  setTimeout(function () {
    toast.classList.add('is-leaving');
    setTimeout(function () { toast.remove(); }, REDUCED_MOTION ? 0 : 220);
  }, 4000);
}

// ---------------------------------------------------------------------------
// Bulk selection toolbar — Feature 4
//
// The toolbar's <form> already works standalone via a normal POST (see
// dashboard.html — checkboxes are associated to it via the HTML `form=`
// attribute rather than DOM nesting, since task cards have their own
// forms). This just adds the "only appears once something is selected"
// polish on top.
// ---------------------------------------------------------------------------
function initBulkSelection() {
  var toolbar = document.getElementById('bulkActionForm');
  var countLabel = document.getElementById('bulkCount');
  var checkboxes = document.querySelectorAll('.task-select');
  if (!toolbar || checkboxes.length === 0) return;

  function refresh() {
    var checked = document.querySelectorAll('.task-select:checked').length;
    toolbar.classList.toggle('visible', checked > 0);
    if (countLabel) countLabel.textContent = checked + ' selected';
  }

  checkboxes.forEach(function (box) {
    box.addEventListener('change', refresh);
  });
  refresh();
}

// ---------------------------------------------------------------------------
// Advanced filter panel toggle — Feature 3
// ---------------------------------------------------------------------------
function initFilterPanelToggle() {
  var btn = document.getElementById('toggleFiltersBtn');
  var panel = document.getElementById('filterPanel');
  if (!btn || !panel) return;
  btn.addEventListener('click', function (e) {
    e.stopPropagation();
    var open = panel.classList.toggle('open');
    btn.setAttribute('aria-expanded', open);
  });
  document.addEventListener('click', function (e) {
    if (panel.classList.contains('open') && !panel.contains(e.target) && e.target !== btn) {
      panel.classList.remove('open');
      btn.setAttribute('aria-expanded', 'false');
    }
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && panel.classList.contains('open')) {
      panel.classList.remove('open');
      btn.setAttribute('aria-expanded', 'false');
    }
  });
}

// ---------------------------------------------------------------------------
// Keyboard shortcuts — Feature 10
// ---------------------------------------------------------------------------
function initKeyboardShortcuts() {
  var overlay = document.getElementById('shortcutsOverlay');
  var closeBtn = document.getElementById('shortcutsCloseBtn');

  function isTypingContext(target) {
    var tag = target.tagName;
    if (tag === 'TEXTAREA' || tag === 'SELECT' || target.isContentEditable) return true;
    if (tag === 'INPUT') {
      // Only text-entry input types should suppress shortcuts — a
      // checkbox/radio/button/submit retaining focus (e.g. right after a
      // bulk-select click) must not block "n", "/", or "?".
      var textTypes = ['text', 'search', 'email', 'password', 'number', 'tel', 'url', 'date', 'time'];
      return textTypes.indexOf((target.type || 'text').toLowerCase()) !== -1;
    }
    return false;
  }

  function closeOverlay() {
    if (overlay) overlay.classList.remove('open');
  }
  function openOverlay() {
    if (overlay) overlay.classList.add('open');
  }

  if (closeBtn) closeBtn.addEventListener('click', closeOverlay);
  if (overlay) {
    overlay.addEventListener('click', function (e) {
      if (e.target === overlay) closeOverlay();
    });
  }

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      closeOverlay();
      return; // Escape always works, even while typing.
    }
    if ((e.ctrlKey || e.metaKey) && (e.key === 'k' || e.key === 'K')) {
      // Ctrl/Cmd+K focuses the topbar search — allowed even while typing
      // elsewhere, since it's a deliberate "jump to search" shortcut.
      var topbarSearch = document.getElementById('topbarSearch');
      if (topbarSearch) {
        e.preventDefault();
        topbarSearch.focus();
        topbarSearch.select();
      }
      return;
    }
    if (isTypingContext(e.target)) return;
    if (e.metaKey || e.ctrlKey || e.altKey) return;

    if (e.key === 'n' || e.key === 'N') {
      var url = document.body.dataset.taskCreateUrl;
      if (url) {
        e.preventDefault();
        window.location.href = url;
      }
    } else if (e.key === '/') {
      var search = document.getElementById('searchInput');
      if (search) {
        e.preventDefault();
        search.focus();
      }
    } else if (e.key === '?') {
      e.preventDefault();
      openOverlay();
    }
  });
}

// ---------------------------------------------------------------------------
// Completion celebration — only for a genuinely meaningful moment (clearing
// every active task), never on every single completion, and at most once
// per page load so rapid toggling can't spam it.
// ---------------------------------------------------------------------------
var celebratedThisLoad = false;

function maybeCelebrateCompletion(data) {
  if (!data || !data.completed) return; // only on completing, not reopening
  if (!data.stats || data.stats.active !== 0) return; // only when nothing active remains
  if (celebratedThisLoad) return;
  celebratedThisLoad = true;

  showClientToast("You're all caught up! Nice work.", 'success');
  if (!REDUCED_MOTION) burstConfetti();
}

function burstConfetti() {
  // Lightweight, dependency-free: a handful of small colored squares that
  // fall and fade via a single CSS keyframe. No canvas, no library.
  var colors = ['#4f46e5', '#16a34a', '#d97706', '#0ea5e9'];
  var container = document.createElement('div');
  container.className = 'confetti-burst';
  container.setAttribute('aria-hidden', 'true');
  for (var i = 0; i < 24; i++) {
    var piece = document.createElement('span');
    piece.className = 'confetti-piece';
    piece.style.left = (Math.random() * 100) + '%';
    piece.style.backgroundColor = colors[i % colors.length];
    piece.style.animationDelay = Math.round(Math.random() * 200) + 'ms';
    piece.style.transform = 'rotate(' + Math.floor(Math.random() * 360) + 'deg)';
    container.appendChild(piece);
  }
  document.body.appendChild(container);
  setTimeout(function () { container.remove(); }, 1800);
}

// ---------------------------------------------------------------------------
// Password visibility toggle (login / register forms)
// ---------------------------------------------------------------------------
function initPasswordToggles() {
  document.querySelectorAll('.password-toggle-btn').forEach(function (btn) {
    var input = document.getElementById(btn.dataset.toggleFor);
    if (!input) return;
    btn.addEventListener('click', function () {
      var showing = input.type === 'text';
      input.type = showing ? 'password' : 'text';
      btn.classList.toggle('is-visible', !showing);
      btn.setAttribute('aria-label', showing ? 'Show password' : 'Hide password');
    });
  });
}
