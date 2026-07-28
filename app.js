/**
 * Participant Wise Open Interest (OI) Analysis Dashboard - JavaScript Core Engine
 */

// Global State
let rawCSVData = [];
let availableDates = [];
let currentDateIndex = -1;
let indexFuturesChart = null;
let indexOptionsChart = null;

// Instruments metadata
const INSTRUMENTS = [
    {
        id: 'index-futures',
        title: 'Index Futures',
        longCol: 'Future Index Long',
        shortCol: 'Future Index Short'
    },
    {
        id: 'index-calls',
        title: 'Index Call Longs & Shorts',
        longCol: 'Option Index Call Long',
        shortCol: 'Option Index Call Short'
    },
    {
        id: 'index-puts',
        title: 'Index Put Longs & Shorts',
        longCol: 'Option Index Put Long',
        shortCol: 'Option Index Put Short'
    },
    {
        id: 'stock-futures',
        title: 'Stock Futures',
        longCol: 'Future Stock Long',
        shortCol: 'Future Stock Short'
    },
    {
        id: 'stock-calls',
        title: 'Stock Calls Longs & Shorts',
        longCol: 'Option Stock Call Long',
        shortCol: 'Option Stock Call Short'
    },
    {
        id: 'stock-puts',
        title: 'Stock Puts Longs & Shorts',
        longCol: 'Option Stock Put Long',
        shortCol: 'Option Stock Put Short'
    }
];

const PARTICIPANTS = ['Client', 'DII', 'FII', 'Pro'];

// Helper to format numbers in Indian Number System (e.g. 1,76,498)
function formatIndianNum(num) {
    if (num === null || num === undefined || isNaN(num)) return '-';
    if (num === 0) return '0';

    const absVal = Math.abs(num);
    const formatted = absVal.toLocaleString('en-IN');
    return num < 0 ? `-${formatted}` : formatted;
}

// Fallback CSV Parser if API endpoint is not running
function parseCSV(text) {
    const lines = text.trim().split('\n');
    if (lines.length === 0) return [];

    const headers = lines[0].split(',').map(h => h.trim().replace(/^"|"$/g, ''));
    const records = [];

    for (let i = 1; i < lines.length; i++) {
        if (!lines[i].trim()) continue;
        const row = lines[i].split(',').map(cell => cell.trim().replace(/^"|"$/g, ''));
        const obj = {};
        headers.forEach((h, idx) => {
            let val = row[idx];
            if (h !== 'Client Type' && h !== 'Date' && val !== undefined) {
                val = parseFloat(val) || 0;
            }
            obj[h] = val;
        });
        records.push(obj);
    }
    return records;
}

// Load Data on Startup
async function initDashboard() {
    try {
        // Fetch static CSV directly
        const csvRes = await fetch('FDCP_Data.csv');
        if (!csvRes.ok) throw new Error('Could not fetch FDCP_Data.csv');
        const csvText = await csvRes.text();
        rawCSVData = parseCSV(csvText);

        if (rawCSVData.length === 0) {
            alert('Failed to load FDCP_Data.csv. Please verify the file exists or has data.');
            return;
        }

        // Extract and sort unique trading dates
        const dateSet = new Set(rawCSVData.map(r => r.Date));
        availableDates = Array.from(dateSet);

        // Populate Date Selector
        const selectEl = document.getElementById('date-select');
        selectEl.innerHTML = '';
        availableDates.forEach((d, idx) => {
            const opt = document.createElement('option');
            opt.value = idx;
            opt.textContent = d;
            selectEl.appendChild(opt);
        });

        // Set default to latest available date
        currentDateIndex = availableDates.length - 1;
        selectEl.value = currentDateIndex;

        // Render Dashboard
        renderDashboardForCurrentDate();

        // Setup Event Listeners
        setupEventListeners();

    } catch (err) {
        console.error('Initialization error:', err);
    }
}

// Render Dashboard for currently selected date
function renderDashboardForCurrentDate() {
    if (currentDateIndex < 0 || currentDateIndex >= availableDates.length) return;

    const targetDate = availableDates[currentDateIndex];
    const prevDate1 = currentDateIndex >= 1 ? availableDates[currentDateIndex - 1] : null;
    const prevDate2 = currentDateIndex >= 2 ? availableDates[currentDateIndex - 2] : null;

    // Update Header Date Info
    document.getElementById('footer-date-info').textContent = `Active Date: ${targetDate}`;

    // Filter Data by dates
    const dataToday = getParticipantMap(targetDate);
    const dataT1 = prevDate1 ? getParticipantMap(prevDate1) : null;
    const dataT2 = prevDate2 ? getParticipantMap(prevDate2) : null;

    // Clear and build Summary List items
    const summaryItems = [];

    // Process Each Instrument Block
    INSTRUMENTS.forEach(inst => {
        const blockEl = document.getElementById(`block-${inst.id}`);
        if (!blockEl) return;

        // Update Headers for 3-Day Carried Positions (now in unified thead)
        const thEls = blockEl.querySelectorAll('.unified-table thead th');
        // th indices: 0=Participant, 1-2=Longs, 3-4=Shorts, 5-6=Net, 7=Today, 8=1D, 9=2D
        if (thEls[7]) thEls[7].textContent = 'Today';
        if (thEls[8]) thEls[8].textContent = prevDate1 ? '1D Ago' : '-';
        if (thEls[9]) thEls[9].textContent = prevDate2 ? '2D Ago' : '-';

        const tbody = blockEl.querySelector('.unified-table tbody');
        tbody.innerHTML = '';

        let totalLongChange = 0;
        let totalShortChange = 0;
        let totalNetChange = 0;

        PARTICIPANTS.forEach(p => {
            const todayRow = dataToday[p] || {};
            const t1Row = dataT1 ? dataT1[p] || {} : {};
            const t2Row = dataT2 ? dataT2[p] || {} : {};

            const longToday = todayRow[inst.longCol] || 0;
            const longT1 = t1Row[inst.longCol] || 0;
            const shortToday = todayRow[inst.shortCol] || 0;
            const shortT1 = t1Row[inst.shortCol] || 0;

            const longChange = dataT1 ? longToday - longT1 : 0;
            const shortChange = dataT1 ? shortToday - shortT1 : 0;
            const netChange = longChange - shortChange;

            totalLongChange += longChange;
            totalShortChange += shortChange;
            totalNetChange += netChange;

            // Labels
            let longLabel = '-';
            let longClass = '';
            if (longChange > 0) { longLabel = 'Added'; longClass = 'pos-green'; }
            else if (longChange < 0) { longLabel = 'Closed'; longClass = 'pos-red'; }

            let shortLabel = '-';
            let shortClass = '';
            if (shortChange > 0) { shortLabel = 'Added'; shortClass = 'pos-red'; }
            else if (shortChange < 0) { shortLabel = 'Closed'; shortClass = 'pos-green'; }

            let netLabel = '-';
            let netClass = '';
            if (netChange > 0) { netLabel = 'Bought'; netClass = 'pos-green'; }
            else if (netChange < 0) { netLabel = 'Sold'; netClass = 'pos-red'; }

            // Add to Right-Hand Summary
            if (netChange !== 0) {
                summaryItems.push({
                    participant: p,
                    instrument: inst.title.replace(' Longs & Shorts', ''),
                    action: netLabel,
                    value: netChange,
                    netClass: netClass
                });
            }

            // Carried Net Positions
            const carriedToday = longToday - shortToday;
            const carriedT1 = dataT1 ? (t1Row[inst.longCol] || 0) - (t1Row[inst.shortCol] || 0) : null;
            const carriedT2 = dataT2 ? (t2Row[inst.longCol] || 0) - (t2Row[inst.shortCol] || 0) : null;

            // Create unified row (10 columns)
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td class="participant-name">${p}s</td>
                <td class="action-label ${longClass}">${longLabel}</td>
                <td class="action-val ${longClass}">${formatIndianNum(longChange)}</td>
                <td class="action-label ${shortClass}">${shortLabel}</td>
                <td class="action-val ${shortClass}">${formatIndianNum(shortChange)}</td>
                <td class="action-label ${netClass}">${netLabel}</td>
                <td class="action-val ${netClass}">${formatIndianNum(netChange)}</td>
                <td class="action-val ${carriedToday >= 0 ? 'pos-green' : 'pos-red'}">${formatIndianNum(carriedToday)}</td>
                <td class="action-val ${carriedT1 !== null && carriedT1 >= 0 ? 'pos-green' : 'pos-red'}">${formatIndianNum(carriedT1)}</td>
                <td class="action-val ${carriedT2 !== null && carriedT2 >= 0 ? 'pos-green' : 'pos-red'}">${formatIndianNum(carriedT2)}</td>
            `;
            tbody.appendChild(tr);
        });

        // Add Total Row
        const trTotal = document.createElement('tr');
        trTotal.className = 'total-row';
        trTotal.innerHTML = `
            <td class="participant-name">Total</td>
            <td class="action-label" colspan="6">Market Analysis With Gopal Das</td>
            <td class="action-val">-</td>
            <td class="action-val">-</td>
            <td class="action-val">-</td>
        `;
        tbody.appendChild(trTotal);
    });

    // Render Right-Hand Participant Summary
    renderRightHandSummary(summaryItems);

    // Update KPI Bar
    updateKPIs(dataToday, dataT1);
}

// Get Object Map for specific date
function getParticipantMap(dateStr) {
    const rows = rawCSVData.filter(r => r.Date === dateStr);
    const map = {};
    rows.forEach(r => {
        map[r['Client Type']] = r;
    });
    return map;
}

// Render Positions Bought / Sold Summary — separate table per participant
function renderRightHandSummary(summaryItems) {
    const container = document.getElementById('positions-summary-list');
    container.innerHTML = '';

    PARTICIPANTS.forEach(p => {
        const pItems = summaryItems.filter(item => item.participant === p);

        const card = document.createElement('div');
        card.className = 'instrument-block summary-block';

        let rows = '';
        if (pItems.length === 0) {
            rows = `<tr><td colspan="3" class="text-center" style="color:var(--text-muted); padding:12px;">No net activity</td></tr>`;
        } else {
            pItems.forEach(item => {
                rows += `
                    <tr>
                        <td class="action-label">${item.instrument}</td>
                        <td class="action-label ${item.netClass}">${item.action}</td>
                        <td class="action-val ${item.netClass}">${formatIndianNum(item.value)}</td>
                    </tr>`;
            });
        }

        card.innerHTML = `
            <div class="block-header summary-block-header">${p}s</div>
            <div class="table-scroll-wrapper">
                <table class="dashboard-table summary-table">
                    <thead>
                        <tr>
                            <th>Instrument</th>
                            <th>Action</th>
                            <th>Net Value</th>
                        </tr>
                    </thead>
                    <tbody>${rows}</tbody>
                </table>
            </div>`;

        container.appendChild(card);
    });
}

// Update Top KPI Bar
function updateKPIs(todayMap, t1Map) {
    if (!todayMap || !t1Map) return;

    const fiiToday = todayMap['FII'] || {};
    const fiiT1 = t1Map['FII'] || {};

    // FII Index Futures Net
    const fiiFutLongChange = (fiiToday['Future Index Long'] || 0) - (fiiT1['Future Index Long'] || 0);
    const fiiFutShortChange = (fiiToday['Future Index Short'] || 0) - (fiiT1['Future Index Short'] || 0);
    const fiiFutNet = fiiFutLongChange - fiiFutShortChange;

    const fiiFutEl = document.getElementById('kpi-fii-futures');
    const fiiFutSub = document.getElementById('kpi-fii-futures-action');
    fiiFutEl.textContent = formatIndianNum(fiiFutNet);
    fiiFutEl.className = `kpi-value ${fiiFutNet >= 0 ? 'pos-green' : 'pos-red'}`;
    fiiFutSub.textContent = fiiFutNet >= 0 ? 'FII Net Buyers Today' : 'FII Net Sellers Today';

    // Client Index Calls Net Today
    const clientToday = todayMap['Client'] || {};
    const clientT1 = t1Map['Client'] || {};
    const clientCallLongChg = (clientToday['Option Index Call Long'] || 0) - (clientT1['Option Index Call Long'] || 0);
    const clientCallShortChg = (clientToday['Option Index Call Short'] || 0) - (clientT1['Option Index Call Short'] || 0);
    const clientCallNet = clientCallLongChg - clientCallShortChg;

    const clientCallEl = document.getElementById('kpi-client-calls');
    const clientCallSub = document.getElementById('kpi-client-calls-action');
    clientCallEl.textContent = formatIndianNum(clientCallNet);
    clientCallEl.className = `kpi-value ${clientCallNet >= 0 ? 'pos-green' : 'pos-red'}`;
    clientCallSub.textContent = clientCallNet >= 0 ? 'Retail Bought Net Calls' : 'Retail Sold Net Calls';

    // Pro Index Calls Net Today
    const proToday = todayMap['Pro'] || {};
    const proT1 = t1Map['Pro'] || {};
    const proCallLongChg = (proToday['Option Index Call Long'] || 0) - (proT1['Option Index Call Long'] || 0);
    const proCallShortChg = (proToday['Option Index Call Short'] || 0) - (proT1['Option Index Call Short'] || 0);
    const proCallNet = proCallLongChg - proCallShortChg;

    const proCallEl = document.getElementById('kpi-pro-calls');
    const proCallSub = document.getElementById('kpi-pro-calls-action');
    proCallEl.textContent = formatIndianNum(proCallNet);
    proCallEl.className = `kpi-value ${proCallNet >= 0 ? 'pos-green' : 'pos-red'}`;
    proCallSub.textContent = proCallNet >= 0 ? 'Pro Desk Bought Calls' : 'Pro Desk Sold Calls';

    // Institutional Bias
    const smartMoneyNet = fiiFutNet + proCallNet;
    const biasEl = document.getElementById('kpi-bias');
    const biasSub = document.getElementById('kpi-bias-sub');

    if (smartMoneyNet > 20000) {
        biasEl.textContent = 'BULLISH';
        biasEl.className = 'kpi-value pos-green';
        biasSub.textContent = 'Smart Money Buying';
    } else if (smartMoneyNet < -20000) {
        biasEl.textContent = 'BEARISH';
        biasEl.className = 'kpi-value pos-red';
        biasSub.textContent = 'Smart Money Selling';
    } else {
        biasEl.textContent = 'NEUTRAL / MIXED';
        biasEl.className = 'kpi-value';
        biasSub.textContent = 'Ranging Positioning';
    }
}

// Setup Controls and Navigation Listeners
function setupEventListeners() {
    // Select Date
    const selectEl = document.getElementById('date-select');
    selectEl.addEventListener('change', (e) => {
        currentDateIndex = parseInt(e.target.value);
        renderDashboardForCurrentDate();
    });

    // Prev / Next Buttons
    document.getElementById('btn-prev-date').addEventListener('click', () => {
        if (currentDateIndex > 0) {
            currentDateIndex--;
            selectEl.value = currentDateIndex;
            renderDashboardForCurrentDate();
        }
    });

    document.getElementById('btn-next-date').addEventListener('click', () => {
        if (currentDateIndex < availableDates.length - 1) {
            currentDateIndex++;
            selectEl.value = currentDateIndex;
            renderDashboardForCurrentDate();
        }
    });

    document.getElementById('btn-latest-date').addEventListener('click', () => {
        currentDateIndex = availableDates.length - 1;
        selectEl.value = currentDateIndex;
        renderDashboardForCurrentDate();
    });

    // --- Hamburger Menu ---
    const hamburgerBtn = document.getElementById('btn-hamburger');
    const hamburgerDropdown = document.getElementById('hamburger-dropdown');

    hamburgerBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        hamburgerDropdown.classList.toggle('open');
        const icon = hamburgerBtn.querySelector('i');
        icon.className = hamburgerDropdown.classList.contains('open')
            ? 'fa-solid fa-xmark'
            : 'fa-solid fa-bars';
    });

    // Close hamburger on outside click
    document.addEventListener('click', (e) => {
        if (!hamburgerBtn.contains(e.target) && !hamburgerDropdown.contains(e.target)) {
            hamburgerDropdown.classList.remove('open');
            hamburgerBtn.querySelector('i').className = 'fa-solid fa-bars';
        }
    });

    // Hamburger — Trend Charts
    document.getElementById('hamburger-charts').addEventListener('click', () => {
        const section = document.getElementById('charts-section');
        section.classList.toggle('hidden');
        if (!section.classList.contains('hidden')) {
            renderTrendCharts();
        }
        hamburgerDropdown.classList.remove('open');
        hamburgerBtn.querySelector('i').className = 'fa-solid fa-bars';
    });

    // Hamburger — Theme Toggle
    document.getElementById('hamburger-theme').addEventListener('click', () => {
        document.body.classList.toggle('theme-dark');
        const themeIcon = document.querySelector('#hamburger-theme i');
        if (document.body.classList.contains('theme-dark')) {
            themeIcon.className = 'fa-solid fa-sun';
        } else {
            themeIcon.className = 'fa-solid fa-moon';
        }
        hamburgerDropdown.classList.remove('open');
        hamburgerBtn.querySelector('i').className = 'fa-solid fa-bars';
    });


    // --- Tab Switching ---
    document.getElementById('tab-participant-gross').addEventListener('click', () => switchTab('participant-gross'));
    document.getElementById('tab-money-flow').addEventListener('click', () => {
        switchTab('money-flow');
        loadMoneyFlowView();
    });

    // --- Symbol tabs inside Money Flow view ---
    document.querySelectorAll('.symbol-tab').forEach(btn => {
        btn.addEventListener('click', (e) => {
            document.querySelectorAll('.symbol-tab').forEach(b => b.classList.remove('active'));
            e.currentTarget.classList.add('active');
            renderMoneyFlowForSymbol(e.currentTarget.dataset.symbol);
        });
    });
}

// Global state for money flow data
let moneyFlowData = null;

function switchTab(tabName) {
    // Toggle hamburger-tab active
    document.querySelectorAll('.hamburger-tab').forEach(t => t.classList.remove('active'));
    document.getElementById(`tab-${tabName}`).classList.add('active');

    // Toggle tab-content active
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    document.getElementById(`view-${tabName}`).classList.add('active');

    // Close hamburger after switching tabs
    const dropdown = document.getElementById('hamburger-dropdown');
    const btn = document.getElementById('btn-hamburger');
    if (dropdown && btn) {
        dropdown.classList.remove('open');
        btn.querySelector('i').className = 'fa-solid fa-bars';
    }
}

async function loadMoneyFlowView() {
    try {
        // Fetch static JSON file directly (generated by GitHub Actions)
        const fallbackRes = await fetch('docs/money_flow_data.json');
        if (!fallbackRes.ok) {
            showVerdictError('Money Flow verdict data not found. Automatic fetch might be running right now, or failed.');
            return;
        }
        moneyFlowData = await fallbackRes.json();

        // Update Timestamp
        const tsEl = document.querySelector('#oc-last-updated span');
        if (tsEl) tsEl.textContent = moneyFlowData.timestamp ? new Date(moneyFlowData.timestamp).toLocaleString('en-IN') : '--';

        // Render Panel 1: Executive Market Verdict Banner
        renderExecutiveVerdict(moneyFlowData.executive_summary || {});

        // Render Panel 2: FII & Pro Stance
        renderFIIStance(moneyFlowData.participant_summary || {});

        // Render Panel 3: Index Roll Tracker, Magnet Strike & Traps
        renderIndexRolls(moneyFlowData.index_rolls || {});

        // Render Panel 4: Multi-Day Strike Conviction Matrix
        renderMultiDayConviction(moneyFlowData.conviction_trends || {});

        // Render Panel 5: Stock Options Breadth
        renderStockBreadth(moneyFlowData.stock_breadth || {});

    } catch (err) {
        showVerdictError('Error fetching verdict data: ' + err.message);
    }
}

function renderExecutiveVerdict(exec) {
    const badge = document.getElementById('verdict-bias-badge');
    const title = document.getElementById('verdict-title');
    const desc = document.getElementById('verdict-desc');
    const score = document.getElementById('verdict-score');

    const label = exec.bias_label || 'NEUTRAL';
    if (badge) {
        badge.textContent = label;
        badge.className = 'bias-badge';
        if (label.includes('BULLISH')) badge.classList.add('bullish');
        else if (label.includes('BEARISH')) badge.classList.add('bearish');
        else badge.classList.add('neutral');
    }

    if (title) title.textContent = `INSTITUTIONAL MARKET VERDICT: ${label}`;
    if (desc) desc.textContent = exec.action_desc || 'Cross-correlating participant gross data with strike-level OI.';

    if (score) {
        const sc = exec.smart_money_score || 0;
        score.textContent = (sc > 0 ? '+' : '') + sc;
        score.style.color = sc > 0 ? '#22c55e' : sc < 0 ? '#ef4444' : '#f59e0b';
    }
}

function renderFIIStance(ps) {
    const container = document.getElementById('verdict-fii-stance');
    if (!container) return;

    if (!ps || Object.keys(ps).length === 0) {
        container.innerHTML = '<div style="color:var(--text-muted);">No participant data found for latest date.</div>';
        return;
    }

    const fiiCallNetChg = ps.fii_ce_net_short_change || 0;
    const fiiPeNetChg = ps.fii_pe_net_short_change || 0;
    const fiiFutChg = ps.fii_fut_net_change || 0;

    const proCeNetChg = ps.pro_ce_net_short_change || 0;
    const proPeNetChg = ps.pro_pe_net_short_change || 0;
    const clientCeNetBuy = ps.client_ce_net_buy || 0;

    let callAction = fiiCallNetChg > 10000 ? '🔴 Aggressive Call Writing (Upside Capped)' : fiiCallNetChg < -10000 ? '🚀 Call Short Unwinding (Ceiling Released)' : '⚪ Minor Call Shift';
    let putAction = fiiPeNetChg > 10000 ? '🛡 Put Short Addition (Floor Defended)' : fiiPeNetChg < -10000 ? '⚠️ Put Short Unwinding (Floor Dropped)' : '⚪ Minor Put Shift';
    let futAction = fiiFutChg > 5000 ? '🟢 Net Index Futures Bought' : fiiFutChg < -5000 ? '🔴 Net Index Futures Sold' : '⚪ Flat Futures Action';

    let proStance = proPeNetChg > proCeNetChg ? '🛡 Pro Writing Puts (Bullish Support)' : proCeNetChg > proPeNetChg ? '🔴 Pro Writing Calls (Bearish Cap)' : '⚪ Pro Balanced';
    let retailStance = clientCeNetBuy > 15000 ? '⚠️ Retail Heavy Call Longs (Trap Risk)' : clientCeNetBuy < -15000 ? '🟢 Retail Selling Calls' : '⚪ Retail Neutral';

    container.innerHTML = `
        <div style="font-size:11px; font-weight:800; color:#3b82f6; text-transform:uppercase; margin-bottom:2px;">FII (Institutional) Positioning</div>
        <div style="display:flex; justify-content:space-between; padding:6px 10px; background:var(--bg-primary); border-radius:6px;">
            <span><strong>FII Call Options Stance:</strong></span>
            <span class="${fiiCallNetChg < 0 ? 'pos-green' : 'pos-red'} font-mono">${formatIndianNum(fiiCallNetChg)} (${callAction})</span>
        </div>
        <div style="display:flex; justify-content:space-between; padding:6px 10px; background:var(--bg-primary); border-radius:6px;">
            <span><strong>FII Put Options Stance:</strong></span>
            <span class="${fiiPeNetChg > 0 ? 'pos-green' : 'pos-red'} font-mono">${formatIndianNum(fiiPeNetChg)} (${putAction})</span>
        </div>
        <div style="display:flex; justify-content:space-between; padding:6px 10px; background:var(--bg-primary); border-radius:6px;">
            <span><strong>FII Futures Net Shift:</strong></span>
            <span class="${fiiFutChg > 0 ? 'pos-green' : 'pos-red'} font-mono">${formatIndianNum(fiiFutChg)} (${futAction})</span>
        </div>

        <div style="font-size:11px; font-weight:800; color:#a855f7; text-transform:uppercase; margin-top:6px; margin-bottom:2px;">Pro Desk & Retail Positioning</div>
        <div style="display:flex; justify-content:space-between; padding:6px 10px; background:var(--bg-primary); border-radius:6px;">
            <span><strong>Pro Desk Stance:</strong></span>
            <span class="font-mono">${proStance}</span>
        </div>
        <div style="display:flex; justify-content:space-between; padding:6px 10px; background:var(--bg-primary); border-radius:6px;">
            <span><strong>Retail (Client) Net Calls:</strong></span>
            <span class="${clientCeNetBuy > 0 ? 'pos-green' : 'pos-red'} font-mono">${formatIndianNum(clientCeNetBuy)} (${retailStance})</span>
        </div>

        <div style="font-size:11px; color:var(--text-muted); margin-top:6px; background:var(--bg-card); padding:6px 10px; border-radius:6px; border:1px solid var(--border-color);">
            <i class="fa-solid fa-circle-info"></i> Date: <strong>${ps.date || '--'}</strong> | FII Futures Net Carried: <strong class="font-mono ${ps.fii_fut_net_carried >= 0 ? 'pos-green' : 'pos-red'}">${formatIndianNum(ps.fii_fut_net_carried)}</strong>
        </div>
    `;
}

function renderIndexRolls(rolls) {
    const container = document.getElementById('verdict-index-rolls');
    if (!rolls || Object.keys(rolls).length === 0) {
        container.innerHTML = '<div style="color:var(--text-muted);">No index roll data available.</div>';
        return;
    }

    let html = '';
    for (const [sym, item] of Object.entries(rolls)) {
        const resCls = item.resistance_roll_type === 'BULLISH' ? 'pos-green' : item.resistance_roll_type === 'BEARISH' ? 'pos-red' : '';
        const supCls = item.support_roll_type === 'BULLISH' ? 'pos-green' : item.support_roll_type === 'BEARISH' ? 'pos-red' : '';

        // Squeeze & Trap Badges HTML
        let trapHtml = '';
        if (item.traps_and_squeezes && item.traps_and_squeezes.length > 0) {
            const badgesHtml = item.traps_and_squeezes.map(t => `
                <div style="background:#451a03; border:1px solid #f59e0b; color:#fef3c7; padding:4px 8px; border-radius:4px; font-size:10px; font-weight:700; margin-top:4px;">
                    ${t.badge}: ${t.desc}
                </div>
            `).join('');
            trapHtml = `<div style="max-height:140px; overflow-y:auto; margin-top:4px; padding-right:4px;">${badgesHtml}</div>`;
        }

        html += `
            <div style="padding:10px; background:var(--bg-primary); border:1px solid var(--border-color); border-radius:6px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                    <strong style="font-size:13px; color:#2563eb;">${sym} (LTP: ${item.ltp ? item.ltp.toLocaleString('en-IN') : '--'})</strong>
                    <span style="font-size:11px; font-weight:700; color:#8b5cf6;">Max Pain: ${item.max_pain} | PCR: ${item.pcr_oi ? item.pcr_oi.toFixed(2) : '--'}</span>
                </div>
                
                <div style="display:flex; gap:12px; font-size:11px; font-weight:700; color:var(--text-muted); margin-bottom:6px; background:var(--bg-card); padding:4px 8px; border-radius:4px;">
                    <span>🧲 Magnet Strike: <strong style="color:#3b82f6;">${item.magnet_strike ? item.magnet_strike.toLocaleString('en-IN') : '--'}</strong></span>
                    <span>🎯 Expected Expiry: <strong style="color:#10b981;">${item.expiry_range || '--'}</strong></span>
                </div>

                <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px; font-size:11px;">
                    <div style="background:var(--bg-card); padding:6px; border-radius:4px;">
                        <span style="color:var(--text-muted); font-weight:700;">RESISTANCE:</span>
                        <span class="${resCls}" style="font-weight:800; display:block;">${item.resistance_roll}</span>
                        <div style="font-size:10px; color:var(--text-muted); margin-top:2px;">${item.resistance_roll_desc}</div>
                    </div>
                    <div style="background:var(--bg-card); padding:6px; border-radius:4px;">
                        <span style="color:var(--text-muted); font-weight:700;">SUPPORT:</span>
                        <span class="${supCls}" style="font-weight:800; display:block;">${item.support_roll}</span>
                        <div style="font-size:10px; color:var(--text-muted); margin-top:2px;">${item.support_roll_desc}</div>
                    </div>
                </div>
                ${trapHtml}
            </div>
        `;
    }
    container.innerHTML = html;
}

function renderMultiDayConviction(trends) {
    const tbody = document.getElementById('multiday-conviction-body');
    if (!tbody) return;

    const niftyTrend = trends['NIFTY'];
    if (!niftyTrend || !niftyTrend.strikes || niftyTrend.strikes.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="text-center">Insufficient history to render 5-Day Conviction Matrix. Snapshot archives building...</td></tr>';
        return;
    }

    tbody.innerHTML = niftyTrend.strikes.map(s => {
        const ceTag = s.ce_conviction === 'HARD RESISTANCE' ? '<span style="color:#ef4444; font-weight:900;">🔴 HARD RESISTANCE</span>' : s.ce_conviction === 'CE BUILDING' ? '<span style="color:#f97316; font-weight:800;">CE BUILDING</span>' : s.ce_conviction === 'CE UNWINDING' ? '<span style="color:#22c55e; font-weight:800;">🚀 CE UNWINDING</span>' : '<span style="color:#94a3b8;">STABLE</span>';
        const peTag = s.pe_conviction === 'SOLID FLOOR' ? '<span style="color:#22c55e; font-weight:900;">🛡 SOLID FLOOR</span>' : s.pe_conviction === 'PE BUILDING' ? '<span style="color:#3b82f6; font-weight:800;">PE BUILDING</span>' : s.pe_conviction === 'PE UNWINDING' ? '<span style="color:#ef4444; font-weight:800;">⚠️ PE UNWINDING</span>' : '<span style="color:#94a3b8;">STABLE</span>';

        return `
            <tr>
                <td>${ceTag}</td>
                <td class="${s.ce_trend_delta > 0 ? 'pos-red' : s.ce_trend_delta < 0 ? 'pos-green' : ''} font-mono">${s.ce_trend_delta > 0 ? '+' : ''}${formatIndianNum(s.ce_trend_delta)}</td>
                <td style="font-weight:800; color:#38bdf8;">${s.strike.toLocaleString('en-IN')}</td>
                <td class="${s.pe_trend_delta > 0 ? 'pos-green' : s.pe_trend_delta < 0 ? 'pos-red' : ''} font-mono">${s.pe_trend_delta > 0 ? '+' : ''}${formatIndianNum(s.pe_trend_delta)}</td>
                <td>${peTag}</td>
            </tr>
        `;
    }).join('');
}

function renderStockBreadth(breadth) {
    const callBody = document.getElementById('breadth-call-writing-body');
    const putBody = document.getElementById('breadth-put-writing-body');

    const callList = breadth.call_writing_bearish || [];
    const putList = breadth.put_writing_bullish || [];

    if (callList.length === 0) {
        callBody.innerHTML = '<tr><td colspan="4" class="text-center">No significant call writing today.</td></tr>';
    } else {
        callBody.innerHTML = callList.map(s => `
            <tr>
                <td style="font-weight:800;">${s.symbol}</td>
                <td>${(s.ltp ?? 0).toLocaleString('en-IN')}</td>
                <td>${(s.top_ce_write_strike ?? 0).toLocaleString('en-IN')} CE</td>
                <td class="pos-red">+${formatIndianNum(s.top_ce_write_doi || 0)}</td>
            </tr>
        `).join('');
    }

    if (putList.length === 0) {
        putBody.innerHTML = '<tr><td colspan="4" class="text-center">No significant put writing today.</td></tr>';
    } else {
        putBody.innerHTML = putList.map(s => `
            <tr>
                <td style="font-weight:800;">${s.symbol}</td>
                <td>${(s.ltp ?? 0).toLocaleString('en-IN')}</td>
                <td>${(s.top_pe_write_strike ?? 0).toLocaleString('en-IN')} PE</td>
                <td class="pos-green">+${formatIndianNum(s.top_pe_write_doi || 0)}</td>
            </tr>
        `).join('');
    }
}

function showVerdictError(msg) {
    const title = document.getElementById('verdict-title');
    if (title) title.textContent = 'ERROR: ' + msg;
}

// Render Trend Line Charts using Chart.js
function renderTrendCharts() {
    if (availableDates.length < 2) return;

    // Calculate historical net positions across all dates
    const labels = availableDates.slice(1); // date T requires T-1
    const fiiFutTrend = [];
    const clientFutTrend = [];
    const proFutTrend = [];

    const fiiCallTrend = [];
    const clientCallTrend = [];

    for (let i = 1; i < availableDates.length; i++) {
        const dToday = availableDates[i];
        const dT1 = availableDates[i - 1];

        const mapToday = getParticipantMap(dToday);
        const mapT1 = getParticipantMap(dT1);

        // FII Index Futures Net
        const fiiLChg = (mapToday['FII']?.['Future Index Long'] || 0) - (mapT1['FII']?.['Future Index Long'] || 0);
        const fiiSChg = (mapToday['FII']?.['Future Index Short'] || 0) - (mapT1['FII']?.['Future Index Short'] || 0);
        fiiFutTrend.push(fiiLChg - fiiSChg);

        // Client Index Futures Net
        const cliLChg = (mapToday['Client']?.['Future Index Long'] || 0) - (mapT1['Client']?.['Future Index Long'] || 0);
        const cliSChg = (mapToday['Client']?.['Future Index Short'] || 0) - (mapT1['Client']?.['Future Index Short'] || 0);
        clientFutTrend.push(cliLChg - cliSChg);

        // Pro Index Futures Net
        const proLChg = (mapToday['Pro']?.['Future Index Long'] || 0) - (mapT1['Pro']?.['Future Index Long'] || 0);
        const proSChg = (mapToday['Pro']?.['Future Index Short'] || 0) - (mapT1['Pro']?.['Future Index Short'] || 0);
        proFutTrend.push(proLChg - proSChg);

        // FII Calls
        const fiiCLChg = (mapToday['FII']?.['Option Index Call Long'] || 0) - (mapT1['FII']?.['Option Index Call Long'] || 0);
        const fiiCSChg = (mapToday['FII']?.['Option Index Call Short'] || 0) - (mapT1['FII']?.['Option Index Call Short'] || 0);
        fiiCallTrend.push(fiiCLChg - fiiCSChg);

        // Client Calls
        const cliCLChg = (mapToday['Client']?.['Option Index Call Long'] || 0) - (mapT1['Client']?.['Option Index Call Long'] || 0);
        const cliCSChg = (mapToday['Client']?.['Option Index Call Short'] || 0) - (mapT1['Client']?.['Option Index Call Short'] || 0);
        clientCallTrend.push(cliCLChg - cliCSChg);
    }

    // Chart 1: Index Futures
    const ctx1 = document.getElementById('chart-index-futures').getContext('2d');
    if (indexFuturesChart) indexFuturesChart.destroy();
    indexFuturesChart = new Chart(ctx1, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                { label: 'FII Net Index Futures', data: fiiFutTrend, borderColor: '#2563eb', tension: 0.2, fill: false },
                { label: 'Client Net Index Futures', data: clientFutTrend, borderColor: '#16a34a', tension: 0.2, fill: false },
                { label: 'Pro Net Index Futures', data: proFutTrend, borderColor: '#d97706', tension: 0.2, fill: false }
            ]
        },
        options: {
            responsive: true,
            plugins: { legend: { position: 'top' } }
        }
    });

    // Chart 2: Index Call Options
    const ctx2 = document.getElementById('chart-index-options').getContext('2d');
    if (indexOptionsChart) indexOptionsChart.destroy();
    indexOptionsChart = new Chart(ctx2, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [
                { label: 'FII Net Index Calls', data: fiiCallTrend, backgroundColor: '#3b82f6' },
                { label: 'Client Net Index Calls', data: clientCallTrend, backgroundColor: '#ef4444' }
            ]
        },
        options: {
            responsive: true,
            plugins: { legend: { position: 'top' } }
        }
    });
}

// Initialize on DOM Ready
document.addEventListener('DOMContentLoaded', initDashboard);
