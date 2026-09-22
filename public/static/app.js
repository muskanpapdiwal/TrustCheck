/**
 * TrustCheck - Frontend Application Logic
 * Nature-Toned SaaS Interface with Client-Side Routing and Shared State
 */

import { apiService } from './api-service.js';

// ============================================================================
// 1. Shared Application State
// ============================================================================
export const appState = {
  currentPage: 'home', // 'home' | 'dashboard'
  inputMode: 'single', // 'single' | 'batch' | 'csv' | 'url'
  productInfo: null,   // { platform: 'amazon' | 'flipkart' | null, url: string, title: string }
  analysisResult: null,// Full dashboard data or single review forensics
  benchmarkIntelligence: null,
  isSingleReviewMode: false,

  // Table filter & search state
  tableFilter: 'all',  // 'all' | 'genuine' | 'suspicious' | 'fake'
  tableSearch: '',
  tableSort: 'confidence-desc',
  selectedReview: null
};

// Chart instances for memory cleanup on re-render
const chartInstances = {
  donut: null,
  timeline: null,
  ratingDist: null,
  redFlags: null
};

// ============================================================================
// 2. Client-Side Router
// ============================================================================
export function navigateTo(page) {
  appState.currentPage = page;
  window.location.hash = page;

  document.querySelectorAll('.tc-page').forEach(el => el.classList.remove('active'));
  const target = document.getElementById(page === 'dashboard' ? 'page-dashboard' : 'page-home');
  if (target) {
    target.classList.add('active');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  if (page === 'dashboard') {
    renderDashboard();
  }
}

function handleHashChange() {
  const hash = window.location.hash.replace('#', '') || 'home';
  if (hash === 'dashboard' && !appState.analysisResult) {
    // If no analysis result is in memory yet, load default benchmark data so user sees a live dashboard!
    loadDefaultBenchmarkDashboard();
  } else {
    navigateTo(hash === 'dashboard' ? 'dashboard' : 'home');
  }
}

// ============================================================================
// 3. Multi-Step Loading Orchestration
// ============================================================================
const LOADING_STEPS = [
  { text: 'Collecting reviews...', progress: 25 },
  { text: 'Analyzing language patterns...', progress: 55 },
  { text: 'Checking reviewer behavior...', progress: 80 },
  { text: 'Building report...', progress: 100 }
];

async function runWithMultiStepLoading(taskPromise) {
  const overlay = document.getElementById('loadingOverlay');
  const stepItems = document.querySelectorAll('.tc-step-item');
  const progressBar = document.getElementById('loadingProgressBar');
  const titleEl = document.getElementById('loadingTitle');

  overlay.classList.add('active');
  progressBar.style.width = '0%';

  stepItems.forEach(el => {
    el.classList.remove('active', 'completed');
    const icon = el.querySelector('.tc-step-icon');
    if (icon) icon.innerHTML = '<i class="bi bi-circle"></i>';
  });

  let currentStep = 0;
  const stepInterval = setInterval(() => {
    if (currentStep < LOADING_STEPS.length) {
      const step = LOADING_STEPS[currentStep];
      titleEl.textContent = step.text;
      progressBar.style.width = `${step.progress}%`;

      stepItems.forEach((el, idx) => {
        const icon = el.querySelector('.tc-step-icon');
        if (idx < currentStep) {
          el.className = 'tc-step-item completed';
          if (icon) icon.innerHTML = '<i class="bi bi-check2"></i>';
        } else if (idx === currentStep) {
          el.className = 'tc-step-item active';
          if (icon) icon.innerHTML = '<span class="spinner-border spinner-border-sm" style="width:12px;height:12px;"></span>';
        } else {
          el.className = 'tc-step-item';
          if (icon) icon.innerHTML = '<i class="bi bi-circle"></i>';
        }
      });
      currentStep++;
    }
  }, 450);

  try {
    const result = await taskPromise;
    clearInterval(stepInterval);
    // Mark final step completed
    stepItems.forEach(el => {
      el.className = 'tc-step-item completed';
      const icon = el.querySelector('.tc-step-icon');
      if (icon) icon.innerHTML = '<i class="bi bi-check2"></i>';
    });
    progressBar.style.width = '100%';

    // Brief pause to give user smooth visual completion
    await new Promise(resolve => setTimeout(resolve, 350));
    overlay.classList.remove('active');
    return result;
  } catch (error) {
    clearInterval(stepInterval);
    overlay.classList.remove('active');
    throw error;
  }
}

// ============================================================================
// 4. Client-Side CSV Validation & Sample Generator
// ============================================================================
export function validateAndParseCsv(file) {
  return new Promise((resolve, reject) => {
    if (!file) {
      return reject(new Error('No file selected.'));
    }

    if (!file.name.toLowerCase().endsWith('.csv')) {
      return reject(new Error('Invalid file type. Please upload a standard .csv file.'));
    }

    const MAX_SIZE_BYTES = 5 * 1024 * 1024; // 5MB limit
    if (file.size > MAX_SIZE_BYTES) {
      return reject(new Error('File exceeds the 5MB size limit. Please upload a smaller batch.'));
    }

    if (file.size === 0) {
      return reject(new Error('The uploaded CSV file is empty.'));
    }

    const reader = new FileReader();
    reader.onload = (e) => {
      const content = e.target.result;
      const lines = content.split(/\r?\n/).filter(line => line.trim().length > 0);

      if (lines.length < 2) {
        return reject(new Error('CSV must contain a header row and at least one review.'));
      }

      // Check header columns
      const headerCols = lines[0].toLowerCase().split(',').map(c => c.trim().replace(/^["']|["']$/g, ''));
      const hasReviewCol = headerCols.some(col => ['review', 'review_text', 'text', 'body', 'content'].includes(col));

      if (!hasReviewCol) {
        return reject(new Error("Missing required column. The CSV must have a 'review' or 'review_text' column."));
      }

      const rowCount = lines.length - 1;
      resolve({ file, rowCount });
    };

    reader.onerror = () => reject(new Error('Failed to read CSV file.'));
    reader.readAsText(file.slice(0, 50000)); // Read first chunk for validation
  });
}

export function downloadSampleCsv() {
  const sampleContent =
`review,rating,date,reviewer
"The soundstage is wide and battery lasts well over 8 hours. Very comfortable for long sessions.",5,2026-09-12,DavidK
"AMAZING BEST EVER LIFE CHANGING MUST BUY 10/10 WOW DO NOT WAIT GET IT NOW!!!",5,2026-09-13,Shopper99
"Decent keyboard overall. Tactile feedback is pleasant but spacebar feels slightly mushy.",4,2026-09-14,TechEnthusiast
"Item arrived completely broken and packaging was torn. Customer service was unhelpful.",1,2026-09-15,AlexR
"Excellent quality fast shipping buy again and again super amazing quality!!!",5,2026-09-15,User49182
`;
  const blob = new Blob([sampleContent], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.setAttribute('href', url);
  link.setAttribute('download', 'trustcheck_sample_reviews.csv');
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

// ============================================================================
// 5. URL Domain & Platform Detector
// ============================================================================
export function detectPlatformFromUrl(url) {
  if (!url) return null;
  const clean = url.trim().toLowerCase();
  try {
    const parsed = new URL(clean.startsWith('http') ? clean : 'https://' + clean);
    const host = parsed.hostname;
    if (host.includes('amazon.')) return 'amazon';
    if (host.includes('flipkart.')) return 'flipkart';
    return 'unsupported';
  } catch (e) {
    if (clean.includes('amazon')) return 'amazon';
    if (clean.includes('flipkart')) return 'flipkart';
    return 'unsupported';
  }
}

// ============================================================================
// 6. Semicircular SVG Gauge Generator
// ============================================================================
function updateSemicircularGauge(score) {
  const clampedScore = Math.max(0, Math.min(100, Math.round(score)));
  const gaugeValEl = document.getElementById('gaugeValueText');
  const gaugePathEl = document.getElementById('gaugeActivePath');
  const verdictEl = document.getElementById('gaugeVerdictBadge');
  const summaryEl = document.getElementById('gaugeSummaryText');

  if (!gaugeValEl || !gaugePathEl) return;

  // Semicircle radius = 80, Circumference of half circle = PI * 80 ~= 251.3
  const halfCircumference = Math.PI * 80;
  const strokeDashoffset = halfCircumference * (1 - clampedScore / 100);

  // Smooth number ticker
  gaugeValEl.textContent = clampedScore;

  // Path animated stroke
  gaugePathEl.style.strokeDasharray = `${halfCircumference}`;
  gaugePathEl.style.strokeDashoffset = `${strokeDashoffset}`;

  // Tri-color palette by score band
  if (clampedScore >= 70) {
    gaugePathEl.style.stroke = 'var(--tc-genuine)';
    verdictEl.className = 'tc-verdict-chip tc-verdict-trustworthy';
    verdictEl.innerHTML = '<i class="bi bi-shield-check me-1"></i> Trustworthy';
    summaryEl.textContent = 'High confidence of natural, authentic customer experiences with minimal risk markers.';
  } else if (clampedScore >= 40) {
    gaugePathEl.style.stroke = 'var(--tc-suspicious)';
    verdictEl.className = 'tc-verdict-chip tc-verdict-mixed';
    verdictEl.innerHTML = '<i class="bi bi-exclamation-triangle me-1"></i> Mixed Signals';
    summaryEl.textContent = 'Moderate concentration of promotional superlatives or rating-sentiment divergence detected.';
  } else {
    gaugePathEl.style.stroke = 'var(--tc-fake)';
    verdictEl.className = 'tc-verdict-chip tc-verdict-unreliable';
    verdictEl.innerHTML = '<i class="bi bi-shield-x me-1"></i> Unreliable';
    summaryEl.textContent = 'Significant indicators of automated bot generation or repetitive review clustering.';
  }
}

export function formatSingleReviewAsDashboard(forensics) {
  const isFake = forensics.label === 'Fake';
  const isSuspicious = forensics.classification === 'Suspicious';
  const isGenuine = forensics.label === 'Genuine' && !isSuspicious;

  return {
    total: 1,
    genuine_count: isGenuine ? 1 : 0,
    fake_count: isFake ? 1 : 0,
    pct_genuine: isGenuine ? 100 : 0,
    pct_suspicious: isSuspicious ? 100 : 0,
    pct_fake: isFake ? 100 : 0,
    trust_score: forensics.trust_score || forensics.authenticity || (isGenuine ? 92 : (isSuspicious ? 55 : 15)),
    platform_avg_rating: forensics.rating || (isGenuine ? 5.0 : (isFake ? 5.0 : 3.0)),
    avg_rating_genuine: isGenuine ? (forensics.rating || 5.0) : null,
    rating_distribution: {
      genuine: [0, 0, 0, 0, isGenuine ? 1 : 0],
      fake: [0, 0, 0, 0, !isGenuine ? 1 : 0]
    },
    top_keywords: {
      genuine: isGenuine ? [[forensics.language_pattern || 'Natural Nuance', 1]] : [],
      fake: !isGenuine ? [[forensics.language_pattern || 'Repetitive Pattern', 1]] : []
    },
    reviews: [{
      text: forensics.text,
      rating: forensics.rating || (isGenuine ? 5 : (isFake ? 5 : 3)),
      date: 'Just now',
      label: forensics.label,
      raw_label: forensics.raw_label,
      confidence: forensics.confidence,
      forensics: forensics
    }]
  };
}

// ============================================================================
// 7. Dashboard Rendering & Charts
// ============================================================================
export function renderDashboard() {
  const data = appState.analysisResult;
  if (!data) return;

  const isSingle = appState.isSingleReviewMode;

  // Single review vs batch presentation
  const productCard = document.getElementById('dashProductCard');
  const singleCard = document.getElementById('dashSingleCard');
  const batchGrid = document.getElementById('dashBatchGrid');

  // ALWAYS KEEP THE FULL DASHBOARD VISIBLE!
  if (batchGrid) batchGrid.style.display = 'grid';

  if (isSingle) {
    if (productCard) productCard.style.display = 'none';
    if (singleCard) {
      singleCard.style.display = 'block';
      const singleForensics = (data.reviews && data.reviews[0] && data.reviews[0].forensics) ? data.reviews[0].forensics : data;
      renderSingleReviewDashboard(singleForensics);
    }
  } else {
    if (singleCard) singleCard.style.display = 'none';
  }

  // Product Header Card
  if (productCard) {
    if (appState.productInfo && appState.productInfo.url) {
      productCard.style.display = 'flex';
      const badge = document.getElementById('dashProductBadge');
      const link = document.getElementById('dashProductLink');
      const title = document.getElementById('dashProductTitle');

      const plat = appState.productInfo.platform;
      badge.textContent = plat === 'amazon' ? 'Amazon Product' : (plat === 'flipkart' ? 'Flipkart Product' : 'Verified URL');
      badge.className = `tc-platform-badge ${plat || 'amazon'}`;

      link.href = appState.productInfo.url;
      link.textContent = appState.productInfo.url;
      title.textContent = appState.productInfo.title || (plat === 'amazon' ? 'Amazon Storefront Product' : 'Flipkart Catalog Listing');
    } else {
      productCard.style.display = 'none';
    }
  }

  // 1. Overall Trust Score Gauge
  updateSemicircularGauge(data.trust_score);

  // 2. Stat Cards Row
  const totalReviews = data.total || 0;
  document.getElementById('statTotalReviews').textContent = totalReviews;

  // Calculate 3-part split: Genuine, Suspicious, Fake
  let genuineCount = 0;
  let suspiciousCount = 0;
  let fakeCount = 0;

  if (data.reviews && data.reviews.length > 0) {
    data.reviews.forEach(r => {
      const cls = (r.forensics && r.forensics.classification) ? r.forensics.classification : r.label;
      if (cls === 'Suspicious') {
        suspiciousCount++;
      } else if (r.label === 'Fake' || cls === 'Likely Fake') {
        fakeCount++;
      } else {
        genuineCount++;
      }
    });
  } else {
    genuineCount = data.genuine_count || 0;
    fakeCount = data.fake_count || 0;
  }

  const pctGenuine = totalReviews ? Math.round((genuineCount / totalReviews) * 100) : 0;
  const pctSuspicious = totalReviews ? Math.round((suspiciousCount / totalReviews) * 100) : 0;
  const pctFake = totalReviews ? Math.round((fakeCount / totalReviews) * 100) : 0;

  document.getElementById('statGenuinePct').textContent = `${pctGenuine}%`;
  document.getElementById('statSuspiciousPct').textContent = `${pctSuspicious}%`;
  document.getElementById('statFakePct').textContent = `${pctFake}%`;

  // Average Rating
  const reportedRating = data.platform_avg_rating ? `${data.platform_avg_rating}★` : 'N/A';
  const genuineRating = data.avg_rating_genuine ? `${data.avg_rating_genuine}★` : 'N/A';
  document.getElementById('statReportedRating').textContent = reportedRating;
  document.getElementById('statAdjustedRating').textContent = genuineRating;

  // 3. Genuine vs Fake Donut Chart
  renderDonutChart(pctGenuine, pctSuspicious, pctFake, totalReviews);

  // 4. Rating Distribution Bar Chart
  renderRatingDistChart(data.rating_distribution);

  // 5. Top Red Flags Bar Chart
  renderRedFlagsChart(data.top_keywords, data.reviews);

  // 6. Reviews Over Time Chart
  renderTimelineChart(data.reviews);

  // 7. Reviews Table
  renderReviewsTable();
}

function renderSingleReviewDashboard(forensics) {
  updateSemicircularGauge(forensics.trust_score || forensics.authenticity || 50);

  const quoteEl = document.getElementById('singleReviewQuote');
  const confEl = document.getElementById('singleConfidenceVal');
  const explEl = document.getElementById('singleExplanationText');

  if (quoteEl) quoteEl.textContent = `"${forensics.text}"`;
  if (confEl) confEl.textContent = `${forensics.confidence}%`;
  if (explEl) explEl.textContent = forensics.explanation;

  // Update reason checklist
  const reasonsList = document.getElementById('singleReasonChecklist');
  if (reasonsList) {
    const items = [
      { label: 'Language Pattern', val: forensics.language_pattern, risk: forensics.language_risk },
      { label: 'Sentiment Polarity', val: forensics.sentiment, risk: forensics.sentiment_risk },
      { label: 'Template Overlap', val: forensics.similarity, risk: forensics.similarity_risk },
      { label: 'Behavioral Cadence', val: forensics.posting_behavior, risk: forensics.behavior_risk }
    ];

    reasonsList.innerHTML = items.map(item => `
      <div class="d-flex align-items-center justify-content-between p-3 rounded-3" style="background:#FAF9F5; border:1px solid #EDEDE8;">
        <div>
          <div class="fw-semibold text-dark small">${item.label}</div>
          <div class="text-secondary small">${item.val}</div>
        </div>
        <span class="tc-badge-label ${item.risk > 65 ? 'tc-badge-fake' : (item.risk > 40 ? 'tc-badge-suspicious' : 'tc-badge-genuine')}">
          ${item.risk}% Risk
        </span>
      </div>
    `).join('');
  }
}

// ----------------------------------------------------------------------------
// Charts via Chart.js
// ----------------------------------------------------------------------------
function renderDonutChart(genuinePct, suspiciousPct, fakePct, total) {
  const ctx = document.getElementById('donutChart');
  if (!ctx || typeof Chart === 'undefined') return;

  if (chartInstances.donut) chartInstances.donut.destroy();

  document.getElementById('donutCenterPercent').textContent = `${genuinePct}%`;

  chartInstances.donut = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: ['Genuine', 'Suspicious', 'Fake'],
      datasets: [{
        data: [genuinePct, suspiciousPct, fakePct],
        backgroundColor: ['#16A34A', '#D97706', '#E11D48'],
        hoverBackgroundColor: ['#15803D', '#B45309', '#BE123C'],
        borderWidth: 2,
        borderColor: '#FFFFFF'
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '76%',
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => ` ${ctx.label}: ${ctx.raw}%`
          }
        }
      },
      animation: {
        animateScale: true,
        animateRotate: true
      }
    }
  });
}

function renderRatingDistChart(ratingDist) {
  const ctx = document.getElementById('ratingDistChart');
  if (!ctx || typeof Chart === 'undefined') return;

  if (chartInstances.ratingDist) chartInstances.ratingDist.destroy();

  const labels = ['1 Star', '2 Stars', '3 Stars', '4 Stars', '5 Stars'];
  const genuineData = ratingDist ? ratingDist.genuine : [0, 0, 0, 0, 0];
  const fakeData = ratingDist ? ratingDist.fake : [0, 0, 0, 0, 0];

  chartInstances.ratingDist = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [
        {
          label: 'Genuine',
          data: genuineData,
          backgroundColor: '#16A34A',
          borderRadius: 6
        },
        {
          label: 'Suspicious / Fake',
          data: fakeData,
          backgroundColor: '#E11D48',
          borderRadius: 6
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: { grid: { display: false } },
        y: { beginAtZero: true, grid: { color: '#F1F1EC' } }
      },
      plugins: {
        legend: { position: 'top', labels: { boxWidth: 12, font: { size: 12 } } }
      }
    }
  });
}

function renderRedFlagsChart(topKeywords, reviews) {
  const ctx = document.getElementById('redFlagsChart');
  if (!ctx || typeof Chart === 'undefined') return;

  if (chartInstances.redFlags) chartInstances.redFlags.destroy();

  // Extract top keywords from fake reviews or fallback to benchmark
  let labels = ['Superlative repetition', 'Syndicated template', 'Polarity deviation', 'Zero product attribute', 'Submission spike'];
  let values = [18, 14, 11, 8, 6];

  if (topKeywords && topKeywords.fake && topKeywords.fake.length > 0) {
    labels = topKeywords.fake.slice(0, 5).map(item => `Word: "${item[0]}"`);
    values = topKeywords.fake.slice(0, 5).map(item => item[1]);
  }

  chartInstances.redFlags = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: 'Flagged Occurrences',
        data: values,
        backgroundColor: '#D97706',
        borderRadius: 6
      }]
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: { beginAtZero: true, grid: { color: '#F1F1EC' } },
        y: { grid: { display: false } }
      },
      plugins: {
        legend: { display: false }
      }
    }
  });
}

function renderTimelineChart(reviews) {
  const ctx = document.getElementById('timelineChart');
  const noticeEl = document.getElementById('timelineDataNotice');
  if (!ctx || typeof Chart === 'undefined') return;

  if (chartInstances.timeline) chartInstances.timeline.destroy();

  // Check if dates are present in reviews
  const reviewsWithDate = (reviews || []).filter(r => r.date && r.date !== 'null' && r.date !== 'None');

  let labels = [];
  let volumeData = [];

  if (reviewsWithDate.length >= 3) {
    if (noticeEl) noticeEl.style.display = 'none';
    // Group counts by date
    const dateCounts = {};
    reviewsWithDate.forEach(r => {
      dateCounts[r.date] = (dateCounts[r.date] || 0) + 1;
    });
    labels = Object.keys(dateCounts).slice(-10);
    volumeData = labels.map(k => dateCounts[k]);
  } else {
    // Transparently note that temporal plotting uses platform benchmark telemetry
    if (noticeEl) {
      noticeEl.style.display = 'block';
      noticeEl.textContent = 'Note: These uploaded reviews lacked timestamp columns. Displaying platform baseline telemetry.';
    }
    labels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
    volumeData = [45, 62, 58, 85, 120, 140, 95];
  }

  chartInstances.timeline = new Chart(ctx, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [{
        label: 'Review Volume',
        data: volumeData,
        borderColor: '#16A34A',
        backgroundColor: 'rgba(22, 163, 74, 0.08)',
        fill: true,
        tension: 0.35,
        pointBackgroundColor: '#16A34A',
        pointRadius: 4,
        pointHoverRadius: 6
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: { grid: { display: false } },
        y: { beginAtZero: true, grid: { color: '#F1F1EC' } }
      },
      plugins: {
        legend: { display: false }
      }
    }
  });
}

// ----------------------------------------------------------------------------
// 8. Searchable, Filterable Reviews Table & Side Drawer
// ----------------------------------------------------------------------------
export function renderReviewsTable() {
  const tbody = document.getElementById('reviewsTableBody');
  const countBadge = document.getElementById('tableReviewsCount');
  if (!tbody) return;

  const data = appState.analysisResult;
  let reviews = (data && data.reviews) ? [...data.reviews] : [];

  // 1. Filter
  if (appState.tableFilter !== 'all') {
    reviews = reviews.filter(r => {
      const cls = (r.forensics && r.forensics.classification) ? r.forensics.classification.toLowerCase() : r.label.toLowerCase();
      if (appState.tableFilter === 'genuine') return cls.includes('genuine');
      if (appState.tableFilter === 'suspicious') return cls.includes('suspicious');
      if (appState.tableFilter === 'fake') return cls.includes('fake');
      return true;
    });
  }

  // 2. Search
  if (appState.tableSearch) {
    const q = appState.tableSearch.toLowerCase();
    reviews = reviews.filter(r => r.text.toLowerCase().includes(q));
  }

  // 3. Sort
  if (appState.tableSort === 'confidence-desc') {
    reviews.sort((a, b) => (b.confidence || 0) - (a.confidence || 0));
  } else if (appState.tableSort === 'rating-desc') {
    reviews.sort((a, b) => (b.rating || 0) - (a.rating || 0));
  } else if (appState.tableSort === 'rating-asc') {
    reviews.sort((a, b) => (a.rating || 0) - (b.rating || 0));
  }

  if (countBadge) countBadge.textContent = `${reviews.length} reviews`;

  if (reviews.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="5" style="text-align:center; padding: 2.5rem; color: var(--tc-text-muted);">
          <i class="bi bi-search" style="font-size: 1.5rem; display:block; margin-bottom: 0.5rem;"></i>
          No reviews matched the current search or filter.
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = reviews.map((r, idx) => {
    const labelCls = (r.forensics && r.forensics.classification) ? r.forensics.classification : r.label;
    let badgeClass = 'tc-badge-genuine';
    if (labelCls === 'Suspicious') badgeClass = 'tc-badge-suspicious';
    else if (r.label === 'Fake' || labelCls === 'Likely Fake') badgeClass = 'tc-badge-fake';

    const stars = r.rating ? `${'★'.repeat(r.rating)}${'☆'.repeat(5 - r.rating)}` : 'No rating';
    const dateStr = r.date || '—';
    const truncatedText = r.text.length > 95 ? r.text.substring(0, 95) + '…' : r.text;

    return `
      <tr data-review-idx="${idx}">
        <td style="max-width: 440px;">
          <div class="fw-medium text-dark">${truncatedText}</div>
          <div class="text-secondary small mt-1" style="font-size: 0.775rem;">Click row for forensic reasoning</div>
        </td>
        <td>
          <span style="color: #F59E0B; font-size: 0.85rem;">${stars}</span>
        </td>
        <td class="text-secondary small">${dateStr}</td>
        <td>
          <span class="tc-badge-label ${badgeClass}">
            ${labelCls}
          </span>
        </td>
        <td class="fw-semibold text-dark">${r.confidence ? Math.round(r.confidence) + '%' : '—'}</td>
      </tr>
    `;
  }).join('');

  // Row click listeners for side drawer
  tbody.querySelectorAll('tr').forEach((tr, i) => {
    tr.addEventListener('click', () => {
      openForensicDrawer(reviews[i]);
    });
  });
}

export function openForensicDrawer(review) {
  const drawer = document.getElementById('forensicDrawer');
  if (!drawer || !review) return;

  appState.selectedReview = review;
  const f = review.forensics || {};

  document.getElementById('drawerReviewText').textContent = `"${review.text}"`;
  document.getElementById('drawerLabelBadge').textContent = f.classification || review.label;
  document.getElementById('drawerLabelBadge').className = `tc-badge-label ${(f.classification || review.label).includes('Fake') ? 'tc-badge-fake' : ((f.classification || review.label).includes('Suspicious') ? 'tc-badge-suspicious' : 'tc-badge-genuine')}`;
  document.getElementById('drawerConfidence').textContent = `${Math.round(review.confidence || 90)}%`;
  document.getElementById('drawerExplanation').textContent = f.explanation || 'Analyzed via TF-IDF linguistic feature extraction and ensemble classification.';

  // Spectrum Bars
  updateDrawerSpectrum('drawerLangBar', 'drawerLangVal', f.language_risk || 30);
  updateDrawerSpectrum('drawerBehaviorBar', 'drawerBehaviorVal', f.behavior_risk || 25);
  updateDrawerSpectrum('drawerSimBar', 'drawerSimVal', f.similarity_risk || 20);
  updateDrawerSpectrum('drawerSentimentBar', 'drawerSentimentVal', f.sentiment_risk || 35);

  drawer.classList.add('open');
}

function updateDrawerSpectrum(barId, valId, riskScore) {
  const bar = document.getElementById(barId);
  const val = document.getElementById(valId);
  if (!bar || !val) return;

  const score = Math.max(0, Math.min(100, Math.round(riskScore)));
  val.textContent = `${score}%`;
  bar.style.width = `${score}%`;

  if (score > 65) {
    bar.style.backgroundColor = 'var(--tc-fake)';
  } else if (score > 40) {
    bar.style.backgroundColor = 'var(--tc-suspicious)';
  } else {
    bar.style.backgroundColor = 'var(--tc-genuine)';
  }
}

export function closeForensicDrawer() {
  const drawer = document.getElementById('forensicDrawer');
  if (drawer) drawer.classList.remove('open');
}

// ----------------------------------------------------------------------------
// 9. Export Report (CSV & Print)
// ----------------------------------------------------------------------------
export function exportAnalysisReport() {
  const data = appState.analysisResult;
  if (!data || !data.reviews) {
    alert('No report data available to export.');
    return;
  }

  const csvRows = [
    ['Review Text', 'Star Rating', 'Date', 'Classification', 'Confidence Score', 'Language Risk', 'Behavior Risk']
  ];

  data.reviews.forEach(r => {
    const f = r.forensics || {};
    csvRows.push([
      `"${r.text.replace(/"/g, '""')}"`,
      r.rating || '',
      r.date || '',
      f.classification || r.label,
      `${r.confidence || ''}%`,
      `${f.language_risk || ''}%`,
      `${f.behavior_risk || ''}%`
    ]);
  });

  const csvString = csvRows.map(row => row.join(',')).join('\n');
  const blob = new Blob([csvString], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.setAttribute('href', url);
  link.setAttribute('download', `TrustCheck_Report_${new Date().toISOString().slice(0, 10)}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

// ----------------------------------------------------------------------------
// 10. Load Default Benchmark Data (for instant demo / #dashboard direct access)
// ----------------------------------------------------------------------------
async function loadDefaultBenchmarkDashboard() {
  try {
    const intel = await apiService.fetchDefaultIntelligence();
    appState.benchmarkIntelligence = intel;

    // Convert benchmark recent reviews into dashboard format
    const sampleReviews = (intel.recent_reviews || []).map(r => ({
      text: r.text,
      rating: r.rating,
      date: r.date,
      label: r.label,
      confidence: r.confidence,
      forensics: {
        classification: r.status || (r.label === 'Fake' ? 'Likely Fake' : 'Likely Genuine'),
        explanation: r.explanation,
        language_risk: r.language_risk,
        behavior_risk: r.behavior_risk,
        similarity_risk: r.similarity_risk,
        sentiment_risk: r.sentiment_risk,
        language_pattern: 'Nuanced Feature Phrasing',
        sentiment: 'Balanced Polarity',
        similarity: 'Low Template Match',
        posting_behavior: 'Organic Velocity'
      }
    }));

    appState.analysisResult = {
      total: intel.total_analyzed || 12847,
      trust_score: Math.round(intel.trust_score || 87),
      platform_avg_rating: 4.4,
      avg_rating_genuine: 4.1,
      pct_genuine: intel.pct_genuine || 81.2,
      pct_fake: intel.pct_fake || 8.8,
      rating_distribution: {
        genuine: [320, 480, 890, 2400, 6341],
        fake: [410, 120, 80, 210, 1280]
      },
      top_keywords: {
        genuine: [['battery', 240], ['quality', 210], ['sound', 180], ['comfortable', 140]],
        fake: [['amazing', 310], ['best', 280], ['perfect', 250], ['love', 190]]
      },
      reviews: sampleReviews
    };

    appState.isSingleReviewMode = false;
    navigateTo('dashboard');
  } catch (err) {
    console.error('Failed to load benchmark telemetry:', err);
    navigateTo('home');
  }
}

// ============================================================================
// 11. Event Listeners & Wire-up
// ============================================================================
document.addEventListener('DOMContentLoaded', () => {
  // If server injected initial analysis data (e.g. from form submission or /dashboard route):
  if (window.INITIAL_DATA) {
    appState.analysisResult = window.INITIAL_DATA;
    appState.isSingleReviewMode = (window.INITIAL_DATA.total === 1);
    navigateTo('dashboard');
  } else {
    // Hash listener
    window.addEventListener('hashchange', handleHashChange);
    handleHashChange();
  }

  // Tab Switching
  const tabs = document.querySelectorAll('.tc-tab-btn');
  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      tabs.forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.tc-tab-pane').forEach(p => p.classList.remove('active'));

      tab.classList.add('active');
      const targetPane = document.getElementById(tab.getAttribute('data-tab-target'));
      if (targetPane) targetPane.classList.add('active');

      appState.inputMode = tab.getAttribute('data-mode');
    });
  });

  // Example Chips
  const exampleChips = {
    bot: "AMAZING! BEST PRODUCT EVER IN HUMAN HISTORY 10/10 MUST BUY RECOMMEND TO EVERYONE DO NOT HESITATE WOW WOW WOW FIVE STARS ALL THE WAY!!",
    genuine: "I've been using this keyboard for 3 weeks now. The tactile switches feel solid for daily typing, though the wrist rest is a bit stiff. Battery life easily lasts 4 days between charges.",
    template: "Outstanding item arrived on time will recommend to everyone super high quality very satisfied five stars purchase."
  };

  document.querySelectorAll('.tc-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      const type = chip.getAttribute('data-example');
      const text = exampleChips[type];
      if (text) {
        // Activate paste tab
        const pasteTab = document.querySelector('[data-tab-target="tabPaste"]');
        if (pasteTab) pasteTab.click();

        const textarea = document.getElementById('pasteTextarea');
        if (textarea) {
          textarea.value = text;
          updatePasteCharCount();
        }
      }
    });
  });

  // Textarea char count
  const pasteTextarea = document.getElementById('pasteTextarea');
  if (pasteTextarea) {
    pasteTextarea.addEventListener('input', updatePasteCharCount);
  }

  function updatePasteCharCount() {
    const el = document.getElementById('pasteTextarea');
    const countEl = document.getElementById('pasteCharCount');
    if (el && countEl) {
      countEl.textContent = `${el.value.length} characters`;
    }
  }

  // Drag & Drop CSV
  const dropzone = document.getElementById('csvDropzone');
  const fileInput = document.getElementById('csvFileInput');
  const statusEl = document.getElementById('csvFileStatus');
  let selectedCsvFile = null;

  if (dropzone && fileInput) {
    dropzone.addEventListener('click', () => fileInput.click());

    ['dragenter', 'dragover'].forEach(name => {
      dropzone.addEventListener(name, (e) => {
        e.preventDefault();
        dropzone.classList.add('dragover');
      });
    });

    ['dragleave', 'drop'].forEach(name => {
      dropzone.addEventListener(name, (e) => {
        e.preventDefault();
        dropzone.classList.remove('dragover');
      });
    });

    dropzone.addEventListener('drop', async (e) => {
      const files = e.dataTransfer.files;
      if (files.length > 0) {
        handleCsvFileSelection(files[0]);
      }
    });

    fileInput.addEventListener('change', () => {
      if (fileInput.files.length > 0) {
        handleCsvFileSelection(fileInput.files[0]);
      }
    });
  }

  async function handleCsvFileSelection(file) {
    try {
      const { rowCount } = await validateAndParseCsv(file);
      selectedCsvFile = file;
      if (statusEl) {
        statusEl.style.display = 'flex';
        statusEl.innerHTML = `
          <div>
            <strong><i class="bi bi-file-earmark-spreadsheet me-1"></i> ${file.name}</strong>
            <span class="text-secondary ms-2 small">(${rowCount} reviews detected)</span>
          </div>
          <button type="button" id="btnRemoveCsv" class="btn btn-sm btn-link text-danger p-0">Remove</button>
        `;
        document.getElementById('btnRemoveCsv').addEventListener('click', (e) => {
          e.stopPropagation();
          selectedCsvFile = null;
          statusEl.style.display = 'none';
          if (fileInput) fileInput.value = '';
        });
      }
    } catch (err) {
      alert(err.message);
      if (fileInput) fileInput.value = '';
    }
  }

  // Sample CSV Download Link
  const sampleCsvBtn = document.getElementById('btnDownloadSampleCsv');
  if (sampleCsvBtn) {
    sampleCsvBtn.addEventListener('click', (e) => {
      e.preventDefault();
      downloadSampleCsv();
    });
  }

  // URL Platform Live Detection
  const urlInput = document.getElementById('productUrlInput');
  const urlBadge = document.getElementById('urlPlatformBadge');
  const urlError = document.getElementById('urlErrorMsg');

  if (urlInput) {
    urlInput.addEventListener('input', () => {
      const val = urlInput.value.trim();
      if (!val) {
        urlBadge.textContent = 'Auto-detect';
        urlBadge.className = 'tc-platform-badge';
        if (urlError) urlError.style.display = 'none';
        return;
      }

      const platform = detectPlatformFromUrl(val);
      if (platform === 'amazon') {
        urlBadge.textContent = 'Amazon';
        urlBadge.className = 'tc-platform-badge amazon';
        if (urlError) urlError.style.display = 'none';
      } else if (platform === 'flipkart') {
        urlBadge.textContent = 'Flipkart';
        urlBadge.className = 'tc-platform-badge flipkart';
        if (urlError) urlError.style.display = 'none';
      } else {
        urlBadge.textContent = 'Unsupported';
        urlBadge.className = 'tc-platform-badge unsupported';
        if (urlError) {
          urlError.style.display = 'block';
          urlError.textContent = 'Only Amazon and Flipkart product URLs are supported for automated scraping.';
        }
      }
    });
  }

  // --------------------------------------------------------------------------
  // Analyze Action Handlers
  // --------------------------------------------------------------------------

  // 1. Paste Analyze
  const btnAnalyzePaste = document.getElementById('btnAnalyzePaste');
  if (btnAnalyzePaste) {
    btnAnalyzePaste.addEventListener('click', async () => {
      const text = pasteTextarea.value.trim();
      if (!text) {
        alert('Please enter review text to analyze.');
        return;
      }

      const lines = text.split(/\r?\n/).filter(l => l.trim().length > 0);

      // Single review vs batch
      if (lines.length === 1) {
        try {
          const forensics = await runWithMultiStepLoading(apiService.analyzeSingle(text));
          appState.isSingleReviewMode = true;
          appState.analysisResult = formatSingleReviewAsDashboard(forensics);
          appState.productInfo = null;
          navigateTo('dashboard');
        } catch (err) {
          alert(`Analysis failed: ${err.message}`);
        }
      } else {
        // Multi-line batch
        try {
          const resp = await runWithMultiStepLoading(apiService.analyzePasted(text));
          appState.isSingleReviewMode = false;
          appState.analysisResult = resp.data;
          appState.productInfo = null;
          navigateTo('dashboard');
        } catch (err) {
          alert(`Analysis failed: ${err.message}`);
        }
      }
    });
  }

  // 2. CSV Analyze
  const btnAnalyzeCsv = document.getElementById('btnAnalyzeCsv');
  if (btnAnalyzeCsv) {
    btnAnalyzeCsv.addEventListener('click', async () => {
      if (!selectedCsvFile) {
        alert('Please choose or drop a valid CSV file first.');
        return;
      }

      try {
        const resp = await runWithMultiStepLoading(apiService.uploadCsv(selectedCsvFile));
        appState.isSingleReviewMode = false;
        appState.analysisResult = resp.data;
        appState.productInfo = null;
        navigateTo('dashboard');
      } catch (err) {
        alert(`CSV Analysis failed: ${err.message}`);
      }
    });
  }

  // 3. URL Scrape & Analyze
  const btnAnalyzeUrl = document.getElementById('btnAnalyzeUrl');
  if (btnAnalyzeUrl) {
    btnAnalyzeUrl.addEventListener('click', async () => {
      const url = urlInput.value.trim();
      if (!url) {
        alert('Please enter a product URL.');
        return;
      }

      const platform = detectPlatformFromUrl(url);
      if (platform === 'unsupported') {
        alert('Unsupported URL. Automated scraping only supports Amazon and Flipkart listings. You can paste reviews directly instead.');
        return;
      }

      try {
        const resp = await runWithMultiStepLoading(apiService.scrapeUrl(url));
        appState.isSingleReviewMode = false;
        appState.analysisResult = resp.data;
        appState.productInfo = {
          platform: platform,
          url: url,
          title: platform === 'amazon' ? 'Amazon Verified Product' : 'Flipkart Catalog Listing'
        };
        navigateTo('dashboard');
      } catch (err) {
        alert(`Scraping failed: ${err.message}`);
      }
    });
  }

  // --------------------------------------------------------------------------
  // Table Controls (Filter, Search, Sort)
  // --------------------------------------------------------------------------
  document.querySelectorAll('.tc-filter-pill').forEach(pill => {
    pill.addEventListener('click', () => {
      document.querySelectorAll('.tc-filter-pill').forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
      appState.tableFilter = pill.getAttribute('data-filter');
      renderReviewsTable();
    });
  });

  const searchInput = document.getElementById('reviewsSearchInput');
  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      appState.tableSearch = e.target.value.trim();
      renderReviewsTable();
    });
  }

  const sortSelect = document.getElementById('reviewsSortSelect');
  if (sortSelect) {
    sortSelect.addEventListener('change', (e) => {
      appState.tableSort = e.target.value;
      renderReviewsTable();
    });
  }

  // Drawer Close
  const btnCloseDrawer = document.getElementById('btnCloseDrawer');
  const drawerBackdrop = document.getElementById('forensicDrawer');
  if (btnCloseDrawer) btnCloseDrawer.addEventListener('click', closeForensicDrawer);
  if (drawerBackdrop) {
    drawerBackdrop.addEventListener('click', (e) => {
      if (e.target === drawerBackdrop) closeForensicDrawer();
    });
  }

  // Export report
  const btnExport = document.getElementById('btnExportReport');
  if (btnExport) {
    btnExport.addEventListener('click', exportAnalysisReport);
  }

  // New Analysis CTA
  const btnNewAnalysis = document.getElementById('btnNewAnalysis');
  if (btnNewAnalysis) {
    btnNewAnalysis.addEventListener('click', () => {
      navigateTo('home');
    });
  }

  // FAQ Accordion
  document.querySelectorAll('.tc-faq-question').forEach(btn => {
    btn.addEventListener('click', () => {
      const item = btn.closest('.tc-faq-item');
      const isOpen = item.classList.contains('open');
      document.querySelectorAll('.tc-faq-item').forEach(i => i.classList.remove('open'));
      if (!isOpen) item.classList.add('open');
    });
  });
});
