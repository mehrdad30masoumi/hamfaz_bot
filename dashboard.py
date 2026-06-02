"""
داشبورد وب ادمین هم‌فاز
اجرا: python dashboard.py
آدرس: http://localhost:5000
"""

from flask import Flask, render_template_string, jsonify, request, session, redirect
import sqlite3
import os
import json
from datetime import datetime, timedelta
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get('DASHBOARD_SECRET', 'hamfaz-secret-2024')

DB_PATH        = os.environ.get('DB_PATH', 'hamfaz.db')
ADMIN_PASSWORD = os.environ.get('DASHBOARD_PASS', 'admin1234')
BOT_TOKEN      = os.environ.get('TOKEN', '')

# ══════════════════════════════════════════════════════════
#  توابع دیتابیس
# ══════════════════════════════════════════════════════════
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def query(sql, params=()):
    with get_db() as conn:
        return conn.execute(sql, params).fetchall()

def query_one(sql, params=()):
    with get_db() as conn:
        return conn.execute(sql, params).fetchone()

# ══════════════════════════════════════════════════════════
#  Auth
# ══════════════════════════════════════════════════════════
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated

# ══════════════════════════════════════════════════════════
#  HTML داشبورد
# ══════════════════════════════════════════════════════════
DASHBOARD_HTML = '''<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>پنل ادمین هم‌فاز</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js"></script>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@300;400;500;600;700;900&display=swap');

  :root {
    --bg:       #0a0a0f;
    --surface:  #12121a;
    --card:     #1a1a26;
    --border:   #2a2a3a;
    --accent:   #7c3aed;
    --accent2:  #a855f7;
    --green:    #10b981;
    --red:      #ef4444;
    --yellow:   #f59e0b;
    --blue:     #3b82f6;
    --text:     #e2e8f0;
    --muted:    #64748b;
  }

  * { margin:0; padding:0; box-sizing:border-box; }

  body {
    font-family: 'Vazirmatn', sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
  }

  /* Sidebar */
  .sidebar {
    position: fixed; right:0; top:0;
    width: 240px; height: 100vh;
    background: var(--surface);
    border-left: 1px solid var(--border);
    padding: 24px 16px;
    z-index: 100;
  }

  .logo {
    font-size: 22px; font-weight: 900;
    background: linear-gradient(135deg, var(--accent), var(--accent2));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 32px;
    display: block;
    text-align: center;
  }

  .nav-item {
    display: flex; align-items: center; gap: 10px;
    padding: 12px 16px; border-radius: 10px;
    cursor: pointer; margin-bottom: 4px;
    color: var(--muted); font-size: 14px;
    transition: all 0.2s;
    border: none; background: none;
    width: 100%; text-align: right;
  }
  .nav-item:hover, .nav-item.active {
    background: rgba(124,58,237,0.15);
    color: var(--accent2);
  }
  .nav-item .icon { font-size: 18px; }

  /* Main */
  .main {
    margin-right: 240px;
    padding: 32px;
    min-height: 100vh;
  }

  .page { display: none; }
  .page.active { display: block; }

  .page-title {
    font-size: 24px; font-weight: 700;
    margin-bottom: 24px;
    display: flex; align-items: center; gap: 10px;
  }

  /* Cards */
  .cards-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 16px; margin-bottom: 24px;
  }

  .stat-card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 20px;
    position: relative;
    overflow: hidden;
  }

  .stat-card::before {
    content: '';
    position: absolute;
    top: 0; right: 0;
    width: 80px; height: 80px;
    border-radius: 50%;
    opacity: 0.08;
  }

  .stat-card.purple::before { background: var(--accent); }
  .stat-card.green::before  { background: var(--green); }
  .stat-card.blue::before   { background: var(--blue); }
  .stat-card.red::before    { background: var(--red); }
  .stat-card.yellow::before { background: var(--yellow); }

  .stat-icon { font-size: 28px; margin-bottom: 12px; }
  .stat-value {
    font-size: 32px; font-weight: 900;
    line-height: 1;
  }
  .stat-label {
    font-size: 13px; color: var(--muted);
    margin-top: 6px;
  }
  .stat-change {
    font-size: 12px; margin-top: 8px;
    display: flex; align-items: center; gap: 4px;
  }
  .stat-change.up   { color: var(--green); }
  .stat-change.down { color: var(--red); }

  /* Charts */
  .charts-grid {
    display: grid;
    grid-template-columns: 2fr 1fr;
    gap: 16px; margin-bottom: 24px;
  }

  .chart-card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 20px;
  }

  .chart-title {
    font-size: 15px; font-weight: 600;
    margin-bottom: 16px; color: var(--muted);
  }

  /* Table */
  .table-card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 16px;
    overflow: hidden;
    margin-bottom: 24px;
  }

  .table-header {
    padding: 16px 20px;
    display: flex; justify-content: space-between; align-items: center;
    border-bottom: 1px solid var(--border);
  }

  .table-title { font-size: 15px; font-weight: 600; }

  table { width: 100%; border-collapse: collapse; }
  th {
    padding: 12px 16px; text-align: right;
    font-size: 12px; color: var(--muted);
    background: rgba(255,255,255,0.02);
    font-weight: 500;
  }
  td {
    padding: 12px 16px; font-size: 13px;
    border-top: 1px solid var(--border);
  }
  tr:hover td { background: rgba(255,255,255,0.02); }

  .badge {
    display: inline-flex; align-items: center;
    padding: 3px 10px; border-radius: 999px;
    font-size: 11px; font-weight: 600;
  }
  .badge.male   { background: rgba(59,130,246,0.15); color: var(--blue); }
  .badge.female { background: rgba(236,72,153,0.15); color: #ec4899; }
  .badge.banned { background: rgba(239,68,68,0.15);  color: var(--red); }
  .badge.active { background: rgba(16,185,129,0.15); color: var(--green); }

  /* Filters */
  .filters {
    display: flex; gap: 12px; flex-wrap: wrap;
    margin-bottom: 16px;
  }

  .filter-input, .filter-select {
    background: var(--card);
    border: 1px solid var(--border);
    color: var(--text);
    padding: 8px 14px; border-radius: 8px;
    font-family: 'Vazirmatn', sans-serif;
    font-size: 13px;
  }

  .filter-input { flex: 1; min-width: 200px; }

  /* Buttons */
  .btn {
    padding: 10px 20px; border-radius: 10px;
    font-family: 'Vazirmatn', sans-serif;
    font-size: 13px; font-weight: 600;
    cursor: pointer; border: none;
    transition: all 0.2s;
  }
  .btn-primary {
    background: var(--accent);
    color: white;
  }
  .btn-primary:hover { background: var(--accent2); }
  .btn-danger {
    background: rgba(239,68,68,0.15);
    color: var(--red); border: 1px solid rgba(239,68,68,0.3);
  }
  .btn-danger:hover { background: rgba(239,68,68,0.25); }
  .btn-sm { padding: 5px 12px; font-size: 12px; border-radius: 7px; }

  /* Broadcast form */
  .form-group { margin-bottom: 16px; }
  .form-label {
    display: block; font-size: 13px;
    color: var(--muted); margin-bottom: 8px;
  }
  .form-control {
    width: 100%;
    background: var(--bg);
    border: 1px solid var(--border);
    color: var(--text);
    padding: 10px 14px; border-radius: 10px;
    font-family: 'Vazirmatn', sans-serif;
    font-size: 13px;
  }
  textarea.form-control { min-height: 120px; resize: vertical; }

  /* Ads table */
  .ad-status-active  { color: var(--green); }
  .ad-status-paused  { color: var(--yellow); }

  /* Toast */
  .toast {
    position: fixed; bottom: 24px; left: 24px;
    background: var(--card); border: 1px solid var(--border);
    padding: 14px 20px; border-radius: 12px;
    font-size: 13px; z-index: 999;
    transform: translateY(100px); opacity: 0;
    transition: all 0.3s;
  }
  .toast.show { transform: translateY(0); opacity: 1; }
  .toast.success { border-color: var(--green); color: var(--green); }
  .toast.error   { border-color: var(--red);   color: var(--red); }

  /* Loading */
  .loading {
    display: inline-block; width: 16px; height: 16px;
    border: 2px solid rgba(255,255,255,0.2);
    border-top-color: white;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }
  @keyframes spin { to { transform: rotate(360deg); } }

  /* Scrollbar */
  ::-webkit-scrollbar { width: 6px; }
  ::-webkit-scrollbar-track { background: var(--bg); }
  ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }

  .divider {
    height: 1px; background: var(--border);
    margin: 16px 0;
  }

  .text-muted { color: var(--muted); font-size: 13px; }
  .text-green  { color: var(--green); }
  .text-red    { color: var(--red); }
  .fw-bold     { font-weight: 700; }

  .online-dot {
    width: 8px; height: 8px; border-radius: 50%;
    background: var(--green);
    display: inline-block;
    animation: pulse 2s infinite;
  }
  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50%       { opacity: 0.4; }
  }
</style>
</head>
<body>

<!-- Sidebar -->
<div class="sidebar">
  <span class="logo">🌀 هم‌فاز</span>

  <button class="nav-item active" onclick="showPage('dashboard')">
    <span class="icon">📊</span> داشبورد
  </button>
  <button class="nav-item" onclick="showPage('users')">
    <span class="icon">👥</span> کاربران
  </button>
  <button class="nav-item" onclick="showPage('broadcast')">
    <span class="icon">📢</span> پیام همگانی
  </button>
  <button class="nav-item" onclick="showPage('ads')">
    <span class="icon">💼</span> تبلیغات
  </button>

  <div class="divider"></div>

  <button class="nav-item" onclick="logout()" style="color:var(--red)">
    <span class="icon">🚪</span> خروج
  </button>
</div>

<!-- Main -->
<div class="main">

  <!-- ══ DASHBOARD ══ -->
  <div class="page active" id="page-dashboard">
    <div class="page-title">
      📊 داشبورد
      <span class="online-dot"></span>
      <span class="text-muted" style="font-size:13px;font-weight:400">لایو</span>
    </div>

    <div class="cards-grid" id="stat-cards">
      <div class="stat-card purple">
        <div class="stat-icon">👥</div>
        <div class="stat-value" id="s-total">...</div>
        <div class="stat-label">کل کاربران</div>
      </div>
      <div class="stat-card green">
        <div class="stat-icon">🆕</div>
        <div class="stat-value" id="s-today">...</div>
        <div class="stat-label">ثبت‌نام امروز</div>
      </div>
      <div class="stat-card blue">
        <div class="stat-icon">💬</div>
        <div class="stat-value" id="s-online">...</div>
        <div class="stat-label">در حال چت</div>
      </div>
      <div class="stat-card yellow">
        <div class="stat-icon">⏳</div>
        <div class="stat-value" id="s-queue">...</div>
        <div class="stat-label">در صف انتظار</div>
      </div>
      <div class="stat-card red">
        <div class="stat-icon">🚫</div>
        <div class="stat-value" id="s-banned">...</div>
        <div class="stat-label">بن‌شده</div>
      </div>
    </div>

    <div class="charts-grid">
      <div class="chart-card">
        <div class="chart-title">📈 ثبت‌نام ۷ روز اخیر</div>
        <canvas id="chart-growth" height="120"></canvas>
      </div>
      <div class="chart-card">
        <div class="chart-title">⚧ توزیع جنسیت</div>
        <canvas id="chart-gender" height="160"></canvas>
      </div>
    </div>

    <div class="charts-grid">
      <div class="chart-card">
        <div class="chart-title">🎯 محبوب‌ترین علایق</div>
        <canvas id="chart-interests" height="120"></canvas>
      </div>
      <div class="chart-card">
        <div class="chart-title">📍 توزیع شهری</div>
        <canvas id="chart-location" height="160"></canvas>
      </div>
    </div>
  </div>

  <!-- ══ USERS ══ -->
  <div class="page" id="page-users">
    <div class="page-title">👥 مدیریت کاربران</div>

    <div class="filters">
      <input class="filter-input" type="text" id="search-input"
             placeholder="🔍 جستجو در یوزرنیم..." oninput="loadUsers()">
      <select class="filter-select" id="filter-gender" onchange="loadUsers()">
        <option value="">همه جنسیت‌ها</option>
        <option value="Male">پسر 👦</option>
        <option value="Female">دختر 👧</option>
      </select>
      <select class="filter-select" id="filter-age" onchange="loadUsers()">
        <option value="">همه سنین</option>
        <option value="-18">زیر ۱۸</option>
        <option value="18-25">۱۸-۲۵</option>
        <option value="25-35">۲۵-۳۵</option>
        <option value="+35">بالای ۳۵</option>
      </select>
      <select class="filter-select" id="filter-status" onchange="loadUsers()">
        <option value="">همه وضعیت‌ها</option>
        <option value="0">فعال</option>
        <option value="1">بن‌شده</option>
      </select>
      <button class="btn btn-primary" onclick="exportCSV()">⬇️ خروجی CSV</button>
    </div>

    <div class="table-card">
      <div class="table-header">
        <span class="table-title">لیست کاربران</span>
        <span class="text-muted" id="users-count">در حال بارگذاری...</span>
      </div>
      <div style="overflow-x:auto">
        <table>
          <thead>
            <tr>
              <th>یوزرنیم</th>
              <th>جنسیت</th>
              <th>سن</th>
              <th>شهر</th>
              <th>علاقه</th>
              <th>سکه</th>
              <th>کارما</th>
              <th>ریپورت</th>
              <th>وضعیت</th>
              <th>عملیات</th>
            </tr>
          </thead>
          <tbody id="users-table-body">
            <tr><td colspan="10" style="text-align:center;color:var(--muted);padding:40px">در حال بارگذاری...</td></tr>
          </tbody>
        </table>
      </div>
      <div style="padding:16px;display:flex;gap:8px;justify-content:center" id="pagination"></div>
    </div>
  </div>

  <!-- ══ BROADCAST ══ -->
  <div class="page" id="page-broadcast">
    <div class="page-title">📢 پیام همگانی هدفمند</div>

    <div class="chart-card" style="max-width:600px">
      <div class="form-group">
        <label class="form-label">🎯 مخاطبان هدف</label>
        <select class="form-control" id="bc-gender">
          <option value="all">همه کاربران</option>
          <option value="Male">فقط پسرها 👦</option>
          <option value="Female">فقط دخترها 👧</option>
        </select>
      </div>

      <div class="form-group">
        <label class="form-label">📅 بازه سنی</label>
        <select class="form-control" id="bc-age">
          <option value="all">همه سنین</option>
          <option value="-18">زیر ۱۸ سال</option>
          <option value="18-25">۱۸ تا ۲۵ سال</option>
          <option value="25-35">۲۵ تا ۳۵ سال</option>
          <option value="+35">بالای ۳۵ سال</option>
        </select>
      </div>

      <div class="form-group">
        <label class="form-label">🎮 علاقه</label>
        <select class="form-control" id="bc-interest">
          <option value="all">همه علایق</option>
          <option value="Game">گیم و تکنولوژی 🎮</option>
          <option value="Movie">فیلم و سریال 🎬</option>
          <option value="Art">هنر و موزیک 🎨</option>
          <option value="Tech">برنامه‌نویسی 💻</option>
          <option value="Sport">ورزش ⚽</option>
          <option value="Trade">بیزنس و ترید 📈</option>
        </select>
      </div>

      <div class="form-group">
        <label class="form-label">✍️ متن پیام</label>
        <textarea class="form-control" id="bc-text"
                  placeholder="متن پیام همگانی را اینجا بنویسید..."></textarea>
      </div>

      <div style="display:flex;align-items:center;gap:12px">
        <button class="btn btn-primary" onclick="sendBroadcast()" id="bc-btn">
          📤 ارسال پیام
        </button>
        <span class="text-muted" id="bc-preview"></span>
      </div>

      <div class="divider"></div>
      <div id="bc-result"></div>
    </div>
  </div>

  <!-- ══ ADS ══ -->
  <div class="page" id="page-ads">
    <div class="page-title">💼 مدیریت تبلیغات</div>

    <div class="chart-card" style="margin-bottom:24px">
      <div class="table-title" style="margin-bottom:16px">➕ افزودن آگهی جدید</div>

      <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
        <div class="form-group">
          <label class="form-label">نام آگهی‌دهنده</label>
          <input class="form-control" type="text" id="ad-name" placeholder="مثال: تاج‌گامون">
        </div>
        <div class="form-group">
          <label class="form-label">لینک</label>
          <input class="form-control" type="text" id="ad-link" placeholder="https://...">
        </div>
        <div class="form-group">
          <label class="form-label">فیلتر جنسیت</label>
          <select class="form-control" id="ad-gender">
            <option value="all">همه</option>
            <option value="Male">پسرها</option>
            <option value="Female">دخترها</option>
          </select>
        </div>
        <div class="form-group">
          <label class="form-label">فیلتر سن</label>
          <select class="form-control" id="ad-age">
            <option value="all">همه</option>
            <option value="18-25">۱۸-۲۵</option>
            <option value="25-35">۲۵-۳۵</option>
            <option value="+35">بالای ۳۵</option>
          </select>
        </div>
      </div>

      <div class="form-group">
        <label class="form-label">متن آگهی</label>
        <textarea class="form-control" id="ad-text" rows="3"
                  placeholder="📢 متن تبلیغ رو اینجا بنویس..."></textarea>
      </div>

      <button class="btn btn-primary" onclick="addAd()">➕ افزودن آگهی</button>
    </div>

    <div class="table-card">
      <div class="table-header">
        <span class="table-title">آگهی‌های فعال</span>
      </div>
      <table>
        <thead>
          <tr>
            <th>نام</th>
            <th>جنسیت</th>
            <th>سن</th>
            <th>نمایش</th>
            <th>کلیک</th>
            <th>وضعیت</th>
            <th>عملیات</th>
          </tr>
        </thead>
        <tbody id="ads-table-body">
          <tr><td colspan="7" style="text-align:center;color:var(--muted);padding:40px">در حال بارگذاری...</td></tr>
        </tbody>
      </table>
    </div>
  </div>

</div><!-- /main -->

<!-- Toast -->
<div class="toast" id="toast"></div>

<script>
// ══════════════════════════════════════════════════════
//  Navigation
// ══════════════════════════════════════════════════════
function showPage(name) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  document.getElementById('page-' + name).classList.add('active');
  event.currentTarget.classList.add('active');

  if (name === 'dashboard') loadDashboard();
  if (name === 'users')     loadUsers();
  if (name === 'ads')       loadAds();
}

// ══════════════════════════════════════════════════════
//  Toast
// ══════════════════════════════════════════════════════
function toast(msg, type='success') {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = `toast ${type} show`;
  setTimeout(() => t.classList.remove('show'), 3000);
}

// ══════════════════════════════════════════════════════
//  Dashboard
// ══════════════════════════════════════════════════════
let charts = {};

async function loadDashboard() {
  const r = await fetch('/api/stats');
  const d = await r.json();

  document.getElementById('s-total').textContent  = d.total.toLocaleString('fa');
  document.getElementById('s-today').textContent  = d.today.toLocaleString('fa');
  document.getElementById('s-online').textContent = d.online.toLocaleString('fa');
  document.getElementById('s-queue').textContent  = d.queue.toLocaleString('fa');
  document.getElementById('s-banned').textContent = d.banned.toLocaleString('fa');

  drawGrowth(d.growth);
  drawGender(d.males, d.females);
  drawInterests(d.interests);
  drawLocations(d.locations);
}

function drawGrowth(data) {
  if (charts.growth) charts.growth.destroy();
  const ctx = document.getElementById('chart-growth').getContext('2d');
  charts.growth = new Chart(ctx, {
    type: 'line',
    data: {
      labels: data.map(d => d.date),
      datasets: [{
        label: 'ثبت‌نام',
        data: data.map(d => d.count),
        borderColor: '#7c3aed',
        backgroundColor: 'rgba(124,58,237,0.1)',
        fill: true, tension: 0.4,
        pointBackgroundColor: '#7c3aed',
        pointRadius: 4,
      }]
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: '#64748b' }, grid: { color: 'rgba(255,255,255,0.05)' } },
        y: { ticks: { color: '#64748b' }, grid: { color: 'rgba(255,255,255,0.05)' } }
      }
    }
  });
}

function drawGender(males, females) {
  if (charts.gender) charts.gender.destroy();
  const ctx = document.getElementById('chart-gender').getContext('2d');
  charts.gender = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: ['پسر 👦', 'دختر 👧'],
      datasets: [{
        data: [males, females],
        backgroundColor: ['#3b82f6', '#ec4899'],
        borderWidth: 0,
      }]
    },
    options: {
      responsive: true,
      plugins: {
        legend: { position: 'bottom', labels: { color: '#e2e8f0', font: { family: 'Vazirmatn' } } }
      }
    }
  });
}

function drawInterests(data) {
  if (charts.interests) charts.interests.destroy();
  const ctx = document.getElementById('chart-interests').getContext('2d');
  const colors = ['#7c3aed','#3b82f6','#10b981','#f59e0b','#ef4444','#ec4899'];
  charts.interests = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: data.map(d => d.label),
      datasets: [{
        data: data.map(d => d.count),
        backgroundColor: colors,
        borderRadius: 6,
      }]
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: '#64748b' }, grid: { display: false } },
        y: { ticks: { color: '#64748b' }, grid: { color: 'rgba(255,255,255,0.05)' } }
      }
    }
  });
}

function drawLocations(data) {
  if (charts.location) charts.location.destroy();
  const ctx = document.getElementById('chart-location').getContext('2d');
  charts.location = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: data.map(d => d.label),
      datasets: [{
        data: data.map(d => d.count),
        backgroundColor: ['#7c3aed','#3b82f6','#10b981','#f59e0b'],
        borderWidth: 0,
      }]
    },
    options: {
      responsive: true,
      plugins: {
        legend: { position: 'bottom', labels: { color: '#e2e8f0', font: { family: 'Vazirmatn' } } }
      }
    }
  });
}

// ══════════════════════════════════════════════════════
//  Users
// ══════════════════════════════════════════════════════
let currentPage = 1;

async function loadUsers(page=1) {
  currentPage = page;
  const search = document.getElementById('search-input').value;
  const gender = document.getElementById('filter-gender').value;
  const age    = document.getElementById('filter-age').value;
  const status = document.getElementById('filter-status').value;

  const r = await fetch(`/api/users?page=${page}&search=${search}&gender=${gender}&age=${age}&status=${status}`);
  const d = await r.json();

  document.getElementById('users-count').textContent = `${d.total} کاربر`;

  const TRANS = {
    'Male':'پسر','Female':'دختر',
    '-18':'زیر ۱۸','18-25':'۱۸-۲۵','25-35':'۲۵-۳۵','+35':'بالای ۳۵',
    'Tehran':'تهران','City':'مراکز استان','Other':'سایر','Abroad':'خارج',
    'Game':'گیم','Movie':'فیلم','Art':'هنر','Tech':'تک','Sport':'ورزش','Trade':'ترید'
  };

  const tbody = document.getElementById('users-table-body');
  if (!d.users.length) {
    tbody.innerHTML = '<tr><td colspan="10" style="text-align:center;color:var(--muted);padding:40px">کاربری یافت نشد</td></tr>';
    return;
  }

  tbody.innerHTML = d.users.map(u => `
    <tr>
      <td class="fw-bold">${u.username || '—'}</td>
      <td><span class="badge ${u.gender==='Male'?'male':'female'}">${TRANS[u.gender]||u.gender}</span></td>
      <td>${TRANS[u.age]||u.age}</td>
      <td>${TRANS[u.location]||u.location}</td>
      <td>${TRANS[u.interest]||u.interest}</td>
      <td>💰 ${u.coins}</td>
      <td>⭐ ${u.karma}</td>
      <td>${u.reports > 0 ? `<span class="text-red">🚨 ${u.reports}</span>` : '—'}</td>
      <td><span class="badge ${u.is_banned?'banned':'active'}">${u.is_banned?'بن‌شده':'فعال'}</span></td>
      <td>
        <button class="btn btn-danger btn-sm" onclick="${u.is_banned?`unbanUser(${u.user_id})`:`banUser(${u.user_id})`}">
          ${u.is_banned ? '✅ رفع بن' : '🚫 بن'}
        </button>
      </td>
    </tr>
  `).join('');

  // Pagination
  const pages  = Math.ceil(d.total / 20);
  const pag    = document.getElementById('pagination');
  pag.innerHTML = '';
  for (let i = 1; i <= Math.min(pages, 10); i++) {
    const btn = document.createElement('button');
    btn.className = `btn btn-sm ${i===page?'btn-primary':''}`;
    btn.style.background = i===page ? 'var(--accent)' : 'var(--card)';
    btn.style.color = 'white';
    btn.textContent = i;
    btn.onclick = () => loadUsers(i);
    pag.appendChild(btn);
  }
}

async function banUser(uid) {
  await fetch(`/api/ban/${uid}`, {method:'POST'});
  toast('کاربر بن شد 🚫');
  loadUsers(currentPage);
}

async function unbanUser(uid) {
  await fetch(`/api/unban/${uid}`, {method:'POST'});
  toast('بن رفع شد ✅');
  loadUsers(currentPage);
}

async function exportCSV() {
  const gender = document.getElementById('filter-gender').value;
  const age    = document.getElementById('filter-age').value;
  window.location.href = `/api/export?gender=${gender}&age=${age}`;
}

// ══════════════════════════════════════════════════════
//  Broadcast
// ══════════════════════════════════════════════════════
async function sendBroadcast() {
  const text     = document.getElementById('bc-text').value.trim();
  const gender   = document.getElementById('bc-gender').value;
  const age      = document.getElementById('bc-age').value;
  const interest = document.getElementById('bc-interest').value;

  if (!text) { toast('متن پیام رو بنویس!', 'error'); return; }

  const btn = document.getElementById('bc-btn');
  btn.innerHTML = '<span class="loading"></span> در حال ارسال...';
  btn.disabled = true;

  const r = await fetch('/api/broadcast', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({text, gender, age, interest})
  });
  const d = await r.json();

  btn.innerHTML = '📤 ارسال پیام';
  btn.disabled = false;

  document.getElementById('bc-result').innerHTML = `
    <div style="padding:16px;background:rgba(16,185,129,0.1);border-radius:10px;border:1px solid rgba(16,185,129,0.2)">
      ✅ ارسال تموم شد!<br>
      <span class="text-green">✔️ موفق: ${d.sent}</span> |
      <span class="text-red">❌ ناموفق: ${d.failed}</span>
    </div>
  `;
  toast(`پیام به ${d.sent} کاربر ارسال شد ✅`);
}

// ══════════════════════════════════════════════════════
//  Ads
// ══════════════════════════════════════════════════════
async function loadAds() {
  const r = await fetch('/api/ads');
  const d = await r.json();
  const tbody = document.getElementById('ads-table-body');
  if (!d.length) {
    tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--muted);padding:40px">آگهی‌ای وجود ندارد</td></tr>';
    return;
  }
  tbody.innerHTML = d.map(a => `
    <tr>
      <td class="fw-bold">${a.name}</td>
      <td>${a.gender_filter==='all'?'همه':a.gender_filter}</td>
      <td>${a.age_filter==='all'?'همه':a.age_filter}</td>
      <td>${a.impressions.toLocaleString('fa')}</td>
      <td>${a.clicks.toLocaleString('fa')}</td>
      <td class="${a.is_active?'ad-status-active':'ad-status-paused'}">${a.is_active?'● فعال':'○ متوقف'}</td>
      <td style="display:flex;gap:6px">
        <button class="btn btn-sm" style="background:var(--card);color:var(--text)"
                onclick="toggleAd(${a.id}, ${a.is_active})">${a.is_active?'⏸ توقف':'▶️ فعال'}</button>
        <button class="btn btn-danger btn-sm" onclick="deleteAd(${a.id})">🗑</button>
      </td>
    </tr>
  `).join('');
}

async function addAd() {
  const payload = {
    name:          document.getElementById('ad-name').value,
    text:          document.getElementById('ad-text').value,
    link:          document.getElementById('ad-link').value,
    gender_filter: document.getElementById('ad-gender').value,
    age_filter:    document.getElementById('ad-age').value,
  };
  if (!payload.name || !payload.text) { toast('نام و متن آگهی رو پر کن!', 'error'); return; }
  await fetch('/api/ads', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
  toast('آگهی اضافه شد ✅');
  loadAds();
  ['ad-name','ad-text','ad-link'].forEach(id => document.getElementById(id).value='');
}

async function toggleAd(id, current) {
  await fetch(`/api/ads/${id}/toggle`, {method:'POST'});
  loadAds();
}

async function deleteAd(id) {
  if (!confirm('آگهی حذف بشه؟')) return;
  await fetch(`/api/ads/${id}`, {method:'DELETE'});
  toast('آگهی حذف شد');
  loadAds();
}

async function logout() {
  await fetch('/logout', {method:'POST'});
  location.href = '/login';
}

// Auto-refresh dashboard every 30s
setInterval(() => {
  if (document.getElementById('page-dashboard').classList.contains('active'))
    loadDashboard();
}, 30000);

// Init
loadDashboard();
</script>
</body>
</html>'''

LOGIN_HTML = '''<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="UTF-8">
<title>ورود — هم‌فاز ادمین</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;700;900&display=swap');
  * { margin:0; padding:0; box-sizing:border-box; }
  body {
    font-family: 'Vazirmatn', sans-serif;
    background: #0a0a0f;
    color: #e2e8f0;
    min-height: 100vh;
    display: flex; align-items: center; justify-content: center;
  }
  .card {
    background: #1a1a26;
    border: 1px solid #2a2a3a;
    border-radius: 20px;
    padding: 40px;
    width: 360px;
    text-align: center;
  }
  .logo { font-size: 48px; margin-bottom: 8px; }
  h1 { font-size: 22px; font-weight: 900; margin-bottom: 4px; }
  p  { color: #64748b; font-size: 13px; margin-bottom: 28px; }
  input {
    width: 100%; padding: 12px 16px;
    background: #0a0a0f;
    border: 1px solid #2a2a3a;
    border-radius: 10px;
    color: #e2e8f0;
    font-family: 'Vazirmatn', sans-serif;
    font-size: 14px; margin-bottom: 12px;
  }
  button {
    width: 100%; padding: 12px;
    background: #7c3aed; color: white;
    border: none; border-radius: 10px;
    font-family: 'Vazirmatn', sans-serif;
    font-size: 15px; font-weight: 700;
    cursor: pointer; margin-top: 4px;
  }
  button:hover { background: #a855f7; }
  .error { color: #ef4444; font-size: 13px; margin-top: 10px; }
</style>
</head>
<body>
<div class="card">
  <div class="logo">🌀</div>
  <h1>پنل ادمین هم‌فاز</h1>
  <p>با رمز عبور وارد شوید</p>
  <form method="POST">
    <input type="password" name="password" placeholder="رمز عبور" autofocus>
    <button type="submit">ورود به پنل</button>
  </form>
  {% if error %}<p class="error">{{ error }}</p>{% endif %}
</div>
</body>
</html>'''

# ══════════════════════════════════════════════════════════
#  Routes
# ══════════════════════════════════════════════════════════
@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_PASSWORD:
            session['logged_in'] = True
            return redirect('/')
        return render_template_string(LOGIN_HTML, error='رمز عبور اشتباه است')
    return render_template_string(LOGIN_HTML, error=None)

@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return '', 200

@app.route('/')
@login_required
def index():
    return render_template_string(DASHBOARD_HTML)

# ── API: Stats ──
@app.route('/api/stats')
@login_required
def api_stats():
    total   = query_one("SELECT COUNT(*) FROM users WHERE is_banned=0")[0]
    males   = query_one("SELECT COUNT(*) FROM users WHERE gender='Male' AND is_banned=0")[0]
    females = query_one("SELECT COUNT(*) FROM users WHERE gender='Female' AND is_banned=0")[0]
    today   = query_one("SELECT COUNT(*) FROM users WHERE joined_at>=datetime('now','-1 day') AND is_banned=0")[0]
    banned  = query_one("SELECT COUNT(*) FROM users WHERE is_banned=1")[0]

    # رشد ۷ روز
    growth = []
    for i in range(6, -1, -1):
        row = query_one(
            "SELECT COUNT(*) FROM users WHERE date(joined_at)=date('now', ?)",
            (f'-{i} days',)
        )
        from datetime import date, timedelta
        d = date.today() - timedelta(days=i)
        growth.append({'date': d.strftime('%m/%d'), 'count': row[0]})

    # علایق
    interest_map = {
        'Game':'گیم','Movie':'فیلم','Art':'هنر',
        'Tech':'تک','Sport':'ورزش','Trade':'ترید'
    }
    interests_raw = query("SELECT interest, COUNT(*) c FROM users WHERE is_banned=0 GROUP BY interest ORDER BY c DESC LIMIT 6")
    interests = [{'label': interest_map.get(r[0], r[0] or '?'), 'count': r[1]} for r in interests_raw]

    # شهر
    loc_map = {'Tehran':'تهران','City':'استان','Other':'سایر','Abroad':'خارج'}
    locs_raw = query("SELECT location, COUNT(*) c FROM users WHERE is_banned=0 GROUP BY location ORDER BY c DESC")
    locations = [{'label': loc_map.get(r[0], r[0] or '?'), 'count': r[1]} for r in locs_raw]

    return jsonify({
        'total': total, 'males': males, 'females': females,
        'today': today, 'banned': banned,
        'online': 0, 'queue': 0,
        'growth': growth, 'interests': interests, 'locations': locations
    })

# ── API: Users ──
@app.route('/api/users')
@login_required
def api_users():
    page   = int(request.args.get('page', 1))
    search = request.args.get('search', '')
    gender = request.args.get('gender', '')
    age    = request.args.get('age', '')
    status = request.args.get('status', '')
    offset = (page - 1) * 20

    conditions = []
    params     = []
    if search: conditions.append("username LIKE ?"); params.append(f'%{search}%')
    if gender: conditions.append("gender=?");        params.append(gender)
    if age:    conditions.append("age=?");            params.append(age)
    if status != '': conditions.append("is_banned=?"); params.append(int(status))

    where = ('WHERE ' + ' AND '.join(conditions)) if conditions else ''
    total = query_one(f"SELECT COUNT(*) FROM users {where}", params)[0]
    rows  = query(f"SELECT * FROM users {where} ORDER BY joined_at DESC LIMIT 20 OFFSET {offset}", params)

    users = []
    for r in rows:
        users.append({
            'user_id': r['user_id'], 'username': r['username'],
            'gender': r['gender'],   'age': r['age'],
            'location': r['location'], 'interest': r['interest'],
            'coins': r['coins'],     'karma': r['karma'],
            'reports': r['reports'], 'is_banned': r['is_banned'],
        })
    return jsonify({'users': users, 'total': total})

# ── API: Ban/Unban ──
@app.route('/api/ban/<int:uid>', methods=['POST'])
@login_required
def api_ban(uid):
    with get_db() as conn:
        conn.execute("UPDATE users SET is_banned=1 WHERE user_id=?", (uid,))
        conn.commit()
    return jsonify({'ok': True})

@app.route('/api/unban/<int:uid>', methods=['POST'])
@login_required
def api_unban(uid):
    with get_db() as conn:
        conn.execute("UPDATE users SET is_banned=0, reports=0 WHERE user_id=?", (uid,))
        conn.commit()
    return jsonify({'ok': True})

# ── API: Export ──
@app.route('/api/export')
@login_required
def api_export():
    import csv, io
    from flask import Response
    gender = request.args.get('gender','')
    age    = request.args.get('age','')
    conds  = []; params = []
    if gender: conds.append("gender=?"); params.append(gender)
    if age:    conds.append("age=?");    params.append(age)
    where = ('WHERE ' + ' AND '.join(conds)) if conds else ''
    rows  = query(f"SELECT * FROM users {where} ORDER BY joined_at DESC", params)
    output = io.StringIO()
    w = csv.writer(output)
    w.writerow(['user_id','username','gender','age','location','status','interest',
                'music','personality','vacation','phone','coins','invites','karma','reports','is_banned','joined_at'])
    for r in rows:
        w.writerow(list(r))
    output.seek(0)
    return Response(
        '\ufeff' + output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=hamfaz_users.csv'}
    )

# ── API: Broadcast ──
@app.route('/api/broadcast', methods=['POST'])
@login_required
def api_broadcast():
    import requests as req
    data     = request.get_json()
    text     = data.get('text','')
    gender   = data.get('gender','all')
    age      = data.get('age','all')
    interest = data.get('interest','all')

    conds  = ["is_banned=0"]; params = []
    if gender   != 'all': conds.append("gender=?");   params.append(gender)
    if age      != 'all': conds.append("age=?");       params.append(age)
    if interest != 'all': conds.append("interest=?");  params.append(interest)
    where = 'WHERE ' + ' AND '.join(conds)
    ids = [r[0] for r in query(f"SELECT user_id FROM users {where}", params)]

    sent = failed = 0
    for uid in ids:
        try:
            r = req.post(
                f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage',
                json={'chat_id': uid, 'text': text, 'parse_mode': 'HTML'},
                timeout=5
            )
            if r.status_code == 200: sent += 1
            else: failed += 1
        except:
            failed += 1
    return jsonify({'sent': sent, 'failed': failed})

# ── API: Ads ──
def init_ads_db():
    with get_db() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS ads (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                name          TEXT,
                text          TEXT,
                link          TEXT,
                gender_filter TEXT DEFAULT 'all',
                age_filter    TEXT DEFAULT 'all',
                impressions   INTEGER DEFAULT 0,
                clicks        INTEGER DEFAULT 0,
                is_active     INTEGER DEFAULT 1,
                created_at    TEXT DEFAULT (datetime('now'))
            )
        ''')
        conn.commit()

@app.route('/api/ads', methods=['GET'])
@login_required
def api_ads_get():
    rows = query("SELECT * FROM ads ORDER BY created_at DESC")
    return jsonify([dict(r) for r in rows])

@app.route('/api/ads', methods=['POST'])
@login_required
def api_ads_post():
    d = request.get_json()
    with get_db() as conn:
        conn.execute(
            "INSERT INTO ads (name, text, link, gender_filter, age_filter) VALUES (?,?,?,?,?)",
            (d['name'], d['text'], d.get('link',''), d.get('gender_filter','all'), d.get('age_filter','all'))
        )
        conn.commit()
    return jsonify({'ok': True})

@app.route('/api/ads/<int:aid>/toggle', methods=['POST'])
@login_required
def api_ads_toggle(aid):
    with get_db() as conn:
        conn.execute("UPDATE ads SET is_active = 1 - is_active WHERE id=?", (aid,))
        conn.commit()
    return jsonify({'ok': True})

@app.route('/api/ads/<int:aid>', methods=['DELETE'])
@login_required
def api_ads_delete(aid):
    with get_db() as conn:
        conn.execute("DELETE FROM ads WHERE id=?", (aid,))
        conn.commit()
    return jsonify({'ok': True})

if __name__ == '__main__':
    init_ads_db()
    port = int(os.environ.get('DASHBOARD_PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
