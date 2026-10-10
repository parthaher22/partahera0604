/**
 * GramSetu - Frontend API Client
 * Talks only to the FastAPI backend (app/ in egram-backend). The browser
 * never touches Supabase directly; the backend holds the service-role key.
 *
 * Keeps the same `window.gramSetu` interface the dashboard HTML expects while
 * making auth/complaints/announcements/dashboard calls real API requests.
 */

const GRAMSETU_API = (typeof window !== 'undefined' && window.GRAMSETU_API) || 'http://localhost:5000';

// ---- Demo/placeholder data for modules not yet backed by API endpoints ----
// (members, schemes, taxes, finance). Swap these for real GETs once the
// corresponding routers exist in the backend.
const DEMO_MEMBERS = [
  {
    name: 'Balasaheb R. Jadhav', role: 'Sarpanch (Village Head)', ward: 'Gram Panchayat Head',
    phone: '+91 94220 11223', email: 'sarpanch.kumbhari@gov.in', hours: 'Mon, Wed, Fri: 10 AM - 2 PM',
    badge: 'Elected Representative', img: 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=150&auto=format&fit=crop&q=80'
  },
  {
    name: 'Smt. Vandana S. Shinde', role: 'Up-Sarpanch (Deputy Head)', ward: 'Ward No. 4 & 5',
    phone: '+91 94220 33445', email: 'upsarpanch.kumbhari@gov.in', hours: 'Tue, Thu, Sat: 11 AM - 3 PM',
    badge: 'Elected Representative', img: 'https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=150&auto=format&fit=crop&q=80'
  },
  {
    name: 'Sunita M. Jadhav', role: 'Gram Sachiv (Panchayat Secretary)', ward: 'Government Administration',
    phone: '+91 94220 55667', email: 'sachiv.kumbhari@gov.in', hours: 'Mon - Fri: 9:30 AM - 5:30 PM',
    badge: 'State Govt Officer', img: 'https://images.unsplash.com/photo-1580489944761-15a19d654956?w=150&auto=format&fit=crop&q=80'
  },
  {
    name: 'Ganesh T. More', role: 'Gram Rojgar Sahayak (MGNREGA)', ward: 'Employment & Labor Wing',
    phone: '+91 94220 77889', email: 'mgnrega.kumbhari@gov.in', hours: 'Daily: 10 AM - 4 PM',
    badge: 'Public Service Staff', img: 'https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=150&auto=format&fit=crop&q=80'
  }
];

const DEMO_SCHEMES = [
  {
    id: 'SCH-PM-KISAN', title: 'PM-Kisan Samman Nidhi Yojana', category: 'Farmer',
    department: 'Ministry of Agriculture', benefit: '₹6,000 per year in 3 direct bank installments of ₹2,000 each',
    eligibility: 'All small & marginal landholder farmer families with cultivable land holding in village records.',
    documents: ['Aadhaar Card', 'Updated 7/12 Land Record', 'Bank Passbook linked with NPCI / Aadhaar'],
    link: 'https://pmkisan.gov.in'
  },
  {
    id: 'SCH-PMAY-G', title: 'Pradhan Mantri Awas Yojana (Gramin)', category: 'Housing',
    department: 'Rural Development Dept', benefit: 'Financial assistance of ₹1.20 Lakh + 90 days MGNREGA wages for pucca house construction',
    eligibility: 'Homeless families or households living in zero, one or two room kutcha houses with kutcha roof.',
    documents: ['SECC 2011 Confirmation', 'Aadhaar Cards of family', 'Job Card', 'Bank Account details'],
    link: 'https://pmayg.nic.in'
  },
  {
    id: 'SCH-JJM', title: 'Jal Jeevan Mission - Har Ghar Jal', category: 'Housing',
    department: 'Dept of Drinking Water & Sanitation', benefit: 'Assured functional household tap connection delivering 55 liters per capita clean water daily',
    eligibility: 'Every rural household in Kumbhari lacking a functional pipeline tap connection.',
    documents: ['Gram Panchayat House Tax Receipt', 'Aadhaar Card', 'Ration Card'],
    link: 'https://jaljeevanmission.gov.in'
  },
  {
    id: 'SCH-SANJAY-GANDHI', title: 'Sanjay Gandhi Niradhar Anudan Yojana', category: 'Senior Citizens',
    department: 'Social Welfare Department', benefit: 'Monthly pension of ₹1,500 for destitute senior citizens, widows, and differently-abled individuals',
    eligibility: 'Age 65+ (for senior citizen), destitute persons with annual family income below ₹21,000.',
    documents: ['Age proof (TC/Aadhaar/Doctor certificate)', 'Income Certificate from Tahsildar', 'Residence Certificate'],
    link: 'https://sjsa.maharashtra.gov.in'
  },
  {
    id: 'SCH-MGNREGA', title: 'MGNREGA 100-Day Wage Employment Guarantee', category: 'Farmer',
    department: 'Ministry of Rural Development', benefit: 'Guaranteed 100 days of wage employment per financial year at statutory wage rates (₹297/day)',
    eligibility: 'All adult rural villagers willing to do unskilled manual labor.',
    documents: ['Ration Card', 'Aadhaar Card', 'Passport size photographs'],
    link: 'https://nrega.nic.in'
  },
  {
    id: 'SCH-MAJHI-LADKI', title: 'Mukhyamantri Majhi Ladki Bahin Yojana', category: 'Women',
    department: 'Women & Child Development Dept', benefit: 'Direct Benefit Transfer of ₹1,500 monthly to eligible women aged 21 to 65 years',
    eligibility: 'Permanent female residents with annual family income under ₹2.5 Lakhs.',
    documents: ['Aadhaar Card', 'Domicile / Ration Card', 'Aadhaar Seeded Bank Account', 'Income Declaration'],
    link: 'https://ladakibahin.maharashtra.gov.in'
  }
];

const DEMO_TAXES = [
  {
    id: 'TAX-2026-HP-304', type: 'House Tax (Ghar Patti)', year: 'FY 2026-27',
    villager_id: 'Ramesh Patil', property_no: 'House No. 142, Ward 3', amount: 850,
    due_date: '31 Oct 2026', status: 'Pending', payment_ref: null, paid_at: null
  },
  {
    id: 'TAX-2026-WP-304', type: 'Water Supply Cess (Pani Patti)', year: 'FY 2026-27',
    villager_id: 'Ramesh Patil', property_no: 'House No. 142, Ward 3', amount: 450,
    due_date: '15 Nov 2026', status: 'Pending', payment_ref: null, paid_at: null
  },
  {
    id: 'TAX-2025-HP-304', type: 'House Tax (Ghar Patti)', year: 'FY 2025-26',
    villager_id: 'Ramesh Patil', property_no: 'House No. 142, Ward 3', amount: 800,
    due_date: '31 Oct 2025', status: 'Paid', payment_ref: 'PAY-GS-982143', paid_at: '2025-10-14 11:20 AM'
  }
];

const DEMO_FINANCIALS = {
  totalGrant: 4250000,
  allocatedWorks: 3590000,
  spentToDate: 2840000,
  unspentBalance: 660000,
  source: '15th Central Finance Commission & State Untied Grants (Public eGramSwaraj Audit)',
  updated_at: 'September 2026',
  projects: [
    { id: 'PRJ-2026-01', title: 'Concrete Cement Road Paving (Bazaar to School Link)', ward: 'Ward 2 & 3', budget: 850000, spent: 850000, percent: 100, status: 'Completed', contractor: 'Shree Ganesh Infra Works', completion_date: 'August 2026' },
    { id: 'PRJ-2026-02', title: 'Solar High-Mast Streetlighting Installation (35 Poles)', ward: 'Ward 1, 3 & 6', budget: 520000, spent: 416000, percent: 80, status: 'In Progress', contractor: 'Urja Green Energy Systems', completion_date: 'Target: Oct 2026' },
    { id: 'PRJ-2026-03', title: 'Overhead Water Tank & Feeder Pipeline Upgradation', ward: 'Ward 4 & 5', budget: 1400000, spent: 1050000, percent: 75, status: 'In Progress', contractor: 'Sahyadri Jal Contractors', completion_date: 'Target: Nov 2026' },
    { id: 'PRJ-2026-04', title: 'Anganwadi Center Smart Modernization & Child Playscape', ward: 'Ward 1', budget: 480000, spent: 240000, percent: 50, status: 'In Progress', contractor: 'Panchayat Works Committee', completion_date: 'Target: Dec 2026' },
    { id: 'PRJ-2026-05', title: 'Solid Waste Segregation Shed & Biocompost Pits', ward: 'Ward 7 (Village Outskirts)', budget: 340000, spent: 284000, percent: 85, status: 'In Progress', contractor: 'Swachh Gram Yojna Taskforce', completion_date: 'Target: Oct 2026' }
  ]
};

// Multilingual Dictionary (kept for the dashboard language switcher)
const I18N = {
  en: {
    portalName: 'GramSetu', tagline: 'Digital Bridge Between Villagers & Gram Panchayat',
    panchayatName: 'Kumbhari Gram Panchayat', district: 'Taluka South Solapur, Dist. Solapur',
    villagerRole: 'Villager (Citizen)', adminRole: 'Panchayat Staff / Admin', switchRole: 'Switch Role',
    navHome: 'Dashboard', navComplaints: 'Grievance Redressal', navAnnouncements: 'Notice Board',
    navMembers: 'Panchayat Members', navSchemes: 'Welfare Schemes', navTax: 'Tax & Payments',
    navFinance: 'Financial Transparency', lodgeGrievance: 'Lodge New Grievance', trackStatus: 'Track Status',
    payTaxNow: 'Pay Dues Online', viewSchemes: 'Browse Schemes', gramSabhaSchedule: 'Gram Sabha Schedule',
    emergencyHelpline: 'Emergency & Helplines', activeGrievances: 'Active Grievances', pendingTaxes: 'Pending Taxes',
    availableSchemes: 'Welfare Schemes', fundTransp: 'Village Works Budget', recentAnnouncements: 'Official Announcements & Alerts',
    searchPlaceholder: 'Search complaints, schemes, notices, or staff...',
    statusSubmitted: 'Submitted', statusUnderReview: 'Under Review', statusInProgress: 'In Progress', statusResolved: 'Resolved',
    permissionsTitle: 'Your permissions', logout: 'Logout', refresh: 'Refresh data'
  },
  hi: {
    portalName: 'ग्रामसेतू', tagline: 'ग्रामीणों और ग्राम पंचायत के बीच डिजिटल सेतु',
    panchayatName: 'कुंभारी ग्राम पंचायत', district: 'तालुका दक्षिण सोलापूर, जिला सोलापूर',
    villagerRole: 'ग्रामीण (नागरिक)', adminRole: 'पंचायत कर्मचारी / प्रशासन', switchRole: 'भूमिका बदलें',
    navHome: 'डैशबोर्ड', navComplaints: 'शिकायत निवारण', navAnnouncements: 'सूचना पटल',
    navMembers: 'पंचायत पदाधिकारी', navSchemes: 'कल्याणकारी योजनाएं', navTax: 'कर एवं भुगतान',
    navFinance: 'वित्तीय पारदर्शिता', lodgeGrievance: 'नई शिकायत दर्ज करें', trackStatus: 'स्थिति ट्रैक करें',
    payTaxNow: 'ऑनलाइन कर भरें', viewSchemes: 'योजनाएं देखें', gramSabhaSchedule: 'ग्राम सभा कार्यक्रम',
    emergencyHelpline: 'आपातकालीन हेल्पलाइन', activeGrievances: 'सक्रिय शिकायतें', pendingTaxes: 'बकाया कर',
    availableSchemes: 'सरकारी योजनाएं', fundTransp: 'ग्राम विकास कार्य एवं बजट', recentAnnouncements: 'आधिकारिक घोषणाएं एवं सूचनाएं',
    searchPlaceholder: 'शिकायत, योजना, सूचना या कर्मचारी खोजें...',
    statusSubmitted: 'दर्ज (Submitted)', statusUnderReview: 'जांच में (Under Review)', statusInProgress: 'कार्य प्रगति पर (In Progress)', statusResolved: 'निराकरण पूर्ण (Resolved)',
    permissionsTitle: 'आपकी अनुमतियाँ', logout: 'लॉगआउट', refresh: 'डेटा ताज़ा करें'
  },
  mr: {
    portalName: 'ग्रामसेतू', tagline: 'ग्रामस्थ आणि ग्रामपंचायत यांच्यातील डिजिटल सेतू',
    panchayatName: 'कुंभारी ग्रामपंचायत', district: 'तालुका दक्षिण सोलापूर, जि. सोलापूर',
    villagerRole: 'ग्रामस्थ (नागरिक)', adminRole: 'ग्रामपंचायत कर्मचारी / प्रशासन', switchRole: 'भूमिका बदला',
    navHome: 'डॅशबोर्ड', navComplaints: 'तक्रार निवारण', navAnnouncements: 'सूचना फलक',
    navMembers: 'पंचायत पदाधिकारी', navSchemes: 'शासकीय योजना', navTax: 'कर व देयके',
    navFinance: 'आर्थिक पारदर्शकता', lodgeGrievance: 'नवीन तक्रार नोंदवा', trackStatus: 'स्थिती तपासा',
    payTaxNow: 'घरपट्टी/पाणीपट्टी भरा', viewSchemes: 'योजनांची माहिती', gramSabhaSchedule: 'ग्रामसभा वेळापत्रक',
    emergencyHelpline: 'तातडीच्या हेल्पलाईन', activeGrievances: 'सक्रिय तक्रारी', pendingTaxes: 'थकबाकी कर',
    availableSchemes: 'उपलब्ध योजना', fundTransp: 'विकासकामे व निधी पारदर्शकता', recentAnnouncements: 'अधिकृत जाहीर सूचना',
    searchPlaceholder: 'तक्रारी, योजना, नोटीस किंवा अधिकारी शोधा...',
    statusSubmitted: 'नोंदणीकृत (Submitted)', statusUnderReview: 'छाननी सुरू (Under Review)', statusInProgress: 'काम सुरू (In Progress)', statusResolved: 'निराकरण झाले (Resolved)',
    permissionsTitle: 'तुमची परवानग्या', logout: 'बाहेर पडा', refresh: 'डेटा ताजे करा'
  }
};

// ---- Helpers ---------------------------------------------------------------

function initialsFor(name) {
  const parts = (name || 'Guest').trim().split(/\s+/).slice(0, 2);
  return parts.map(p => p[0] ? p[0].toUpperCase() : '').join('') || 'G';
}

function pick(arr, keys) {
  return keys.map(k => arr[k]).filter(v => v !== undefined && v !== null && v !== '');
}

// ---- API client ------------------------------------------------------------

class GramSetuClient {
  constructor() {
    this.apiBase = GRAMSETU_API;
    this.token = localStorage.getItem('gramsetu_token') || null;
    this.user = null;
    try { this.user = JSON.parse(localStorage.getItem('gramsetu_user') || 'null'); } catch (e) { this.user = null; }

    this.reference = { villages: [], wards: [], categories: [] };
    this.state = {
      activeRole: 'villager',
      currentLang: 'en',
      currentUser: { name: 'Guest', mobile: '', ward: '', village: '', district: '' },
      complaints: [],
      complaintsTotal: 0,
      announcements: [],
      members: DEMO_MEMBERS,
      schemes: DEMO_SCHEMES,
      taxes: DEMO_TAXES,
      financials: DEMO_FINANCIALS,
      finance: {
        records: [], total: 0, summary: null, page: 1, pageSize: 25,
        filters: {
          q: '', transaction_type: '', verification_status: '', category: '',
          financial_year: '', date_from: '', date_to: ''
        }
      },
      auditLogs: [],
      auditTotal: 0,
      staff: [],
      dashboard: null,
      dashboardStageCounts: null,
      trends: null,
      trendDays: 30,
      notifications: [],
      // Panchayat Desk triage filters (server-side on /api/complaints)
      stageFilter: '',
      grievanceFilters: {
        q: '', status: '', category_id: '', date_from: '', date_to: '',
        sort: 'submitted_at', order: 'desc', page: 1, page_size: 25
      },
      // Audit trail filters (server-side on /api/audit-logs)
      auditFilters: { q: '', action: '', actor_id: '', reference: '', date_from: '', date_to: '', limit: 200 },
      lastRefreshAt: 0,
      loadError: null
    };
  }

  get loggedIn() {
    return !!this.token;
  }

  get role() {
    return (this.user && this.user.role) || 'villager';
  }

  get isStaff() {
    return ['panchayat_staff', 'panchayat_admin', 'system_admin'].includes(this.role);
  }

  get canManageStaff() {
    return ['panchayat_admin', 'system_admin'].includes(this.role);
  }

  get canManageAnnouncements() {
    return ['panchayat_staff', 'panchayat_admin', 'system_admin'].includes(this.role);
  }

  // Central fetch helper: attaches the JWT, parses JSON, normalizes errors.
  async api(path, opts = {}) {
    const { method = 'GET', body, auth = Boolean(this.token) } = opts;
    const headers = { 'Content-Type': 'application/json' };
    if (auth && this.token) headers['Authorization'] = `Bearer ${this.token}`;

    let res;
    try {
      res = await fetch(`${this.apiBase}${path}`, {
        method,
        headers,
        body: body === undefined ? undefined : JSON.stringify(body)
      });
    } catch (e) {
      throw new Error(`Cannot reach backend at ${this.apiBase}. Is uvicorn running?`);
    }

    let data = null;
    try { data = await res.json(); } catch (e) { /* non-JSON body */ }

    if (res.status === 401) {
      this.logoutLocal();
      throw new Error(data && data.detail ? data.detail : 'Session expired — please log in again.');
    }
    if (!res.ok) {
      const msg = data ? (data.detail || data.message || JSON.stringify(data)) : `Request failed (${res.status})`;
      throw new Error(msg);
    }
    if (auth && this.token) this.state.lastRefreshAt = Date.now(); // data freshness stamp
    return data;
  }

  logoutLocal() {
    this.token = null;
    this.user = null;
    localStorage.removeItem('gramsetu_token');
    localStorage.removeItem('gramsetu_user');
  }

  async changePassword(currentPassword, newPassword) {
    return this.api('/api/auth/change-password', {
      method: 'POST',
      body: { current_password: currentPassword, new_password: newPassword }
    });
  }

  // Reference lookups
  async loadReference() {
    const tryGet = async (path) => {
      try { return await this.api(path, { auth: false }); }
      catch (e) { return null; }
    };
    const [villages, wards, categories] = await Promise.all([
      tryGet('/api/villages'),
      tryGet('/api/wards'),
      tryGet('/api/complaint-categories')
    ]);
    this.reference.villages = Array.isArray(villages) ? villages : [];
    this.reference.wards = Array.isArray(wards) ? wards : [];
    this.reference.categories = Array.isArray(categories) ? categories : [];
    return this.reference;
  }

  _villageName(id) {
    const v = this.reference.villages.find(x => String(x.village_id) === String(id));
    return v ? (v.name || v.village_name) : (id || '');
  }

  _wardName(id) {
    const w = this.reference.wards.find(x => String(x.ward_id) === String(id));
    return w ? (w.ward_name || w.name || w.ward_number) : (id || '');
  }

  _categoryName(id) {
    const c = this.reference.categories.find(x => String(x.category_id) === String(id));
    return c ? (c.name || c.category_name) : (id || '');
  }

  // ---- Auth ----------------------------------------------------------------

  async login(mobile, password) {
    const data = await this.api('/api/auth/login', {
      method: 'POST', auth: false,
      body: { mobile_number: mobile, password }
    });
    this.token = data.access_token;
    this.user = { user_id: data.user_id, role: data.role, mobile_number: mobile };
    localStorage.setItem('gramsetu_token', this.token);
    localStorage.setItem('gramsetu_user', JSON.stringify(this.user));
    await this.loadMe();
    await this.refresh();
    return data;
  }

  async register(payload) {
    const data = await this.api('/api/auth/register', {
      method: 'POST', auth: false, body: payload
    });
    this.token = data.access_token;
    this.user = { user_id: data.user_id, role: data.role, mobile_number: payload.mobile_number };
    localStorage.setItem('gramsetu_token', this.token);
    localStorage.setItem('gramsetu_user', JSON.stringify(this.user));
    await this.loadMe();
    await this.refresh();
    return data;
  }

  logout() {
    this.logoutLocal();
  }

  async loadMe() {
    if (!this.loggedIn) return;
    try {
      const me = await this.api('/api/auth/me');
      const p = me.profile || {};
      this.user = {
        user_id: me.user_id,
        role: me.role,
        full_name: me.full_name || p.full_name || this.user.full_name || 'Villager',
        mobile_number: me.mobile_number || '',
        village_id: p.village_id,
        ward_id: p.ward_id,
        house_number: p.house_number || '',
        address: p.address || ''
      };
      localStorage.setItem('gramsetu_user', JSON.stringify(this.user));
      this.state.currentUser = {
        name: this.user.full_name,
        mobile: this.user.mobile_number,
        village: this._villageName(p.village_id),
        ward: this._wardName(p.ward_id),
        district: 'Solapur, Maharashtra'
      };
    } catch (e) {
      // keep whatever is already stored
    }
  }

  // ---- Data loaders --------------------------------------------------------

  async refresh() {
    try { await this.loadReference(); } catch (e) { /* optional */ }
    try { await this.loadMe(); } catch (e) { /* optional */ }
    await Promise.all([
      this.loadComplaints(),
      this.loadAnnouncements(),
      this.loadAuditLogs().catch(() => {}),
      this.loadStaff().catch(() => {}),
      this.loadPanchayatDashboard().catch(() => {}),
      this.loadTrends().catch(() => {}),
      this.loadFinance().catch(() => {}),
      this.loadFinanceSummary().catch(() => {}),
      this.loadMyTaxes().catch(() => {}),
      this.loadNotifications().catch(() => {})
    ]);
    this.state.lastRefreshAt = Date.now();
  }

  async init() {
    await this.loadReference();
    if (this.loggedIn) {
      await this.loadMe();
      await Promise.all([
        this.loadComplaints(),
        this.loadAnnouncements(),
        this.loadAuditLogs().catch(() => {}),
        this.loadStaff().catch(() => {}),
        this.loadPanchayatDashboard().catch(() => {}),
        this.loadTrends().catch(() => {}),
        this.loadFinance().catch(() => {}),
        this.loadFinanceSummary().catch(() => {}),
        this.loadMyTaxes().catch(() => {}),
        this.loadNotifications().catch(() => {})
      ]);
      this.state.lastRefreshAt = Date.now();
    }
    return this;
  }

  // Three-part grievance stage used by citizens and the Panchayat Desk.
  stageOf(status) {
    const s = String(status || '').toLowerCase();
    if (['resolved', 'closed', 'rejected'].includes(s)) return 'completed';
    if (['in progress', 'in_progress'].includes(s)) return 'in_progress';
    return 'submitted';
  }

  stageLabel(stage) {
    return ({ submitted: 'Submitted', in_progress: 'In Progress', completed: 'Completed' })[stage] || stage;
  }

  async loadComplaints(stage) {
    if (stage !== undefined && stage !== null) this.state.grievanceStage = stage || '';
    try {
      let q;
      if (this.isStaff) {
        const f = this.state.grievanceFilters;
        const p = new URLSearchParams();
        const activeStage = this.state.grievanceStage || f.stage || '';
        if (activeStage) p.set('stage', activeStage);
        if (f.q) p.set('q', f.q);
        if (f.status) p.set('status', f.status);
        if (f.category_id) p.set('category_id', f.category_id);
        if (f.date_from) p.set('date_from', f.date_from);
        if (f.date_to) p.set('date_to', f.date_to);
        p.set('sort', f.sort || 'submitted_at');
        p.set('order', f.order || 'desc');
        p.set('page', String(f.page || 1));
        p.set('page_size', String(f.page_size || 25));
        q = `?${p.toString()}`;
      } else {
        q = '?page_size=100';
      }
      const data = await this.api(`/api/complaints${q}`);
      this.state.complaints = (data && data.results ? data.results : []).map(c => this.mapComplaint(c));
      this.state.complaintsTotal =
        data && typeof data.total === 'number' ? data.total : this.state.complaints.length;
      this.state.loadError = null;
    } catch (e) {
      this.state.complaints = [];
      this.state.loadError = e.message;
      if (this.loggedIn) console.warn('Complaints load failed:', e.message);
    }
    return this.state.complaints;
  }

  mapComplaint(c) {
    return {
      id: c.complaint_number || (c.complaint_id || '').slice(0, 8),
      uuid: c.complaint_id,
      title: c.title || '(untitled)',
      description: c.description || '',
      location: c.location || '',
      category: this._categoryName(c.category_id),
      category_id: c.category_id,
      ward: this._wardName(c.ward_id),
      status: c.status || 'Submitted',
      priority: c.priority || 'Medium',
      applicant: (c.villager_name) || 'Villager',
      mobile: c.mobile_number || '',
      created_at: c.submitted_at || '',
      submitted_at: c.submitted_at || '',
      updated_at: c.updated_at || c.submitted_at || '',
      resolved_at: c.resolved_at || '',
      closed_at: c.closed_at || '',
      expected_resolution_date: c.expected_resolution_date || '',
      assigned_to: c.assigned_to || 'Panchayat Verification Desk',
      updates: []
    };
  }

  async loadComplaintDetail(idOrUuid) {
    const c = this.state.complaints.find(x => x.id === idOrUuid || x.uuid === idOrUuid);
    if (!c) return null;
    if (!c.uuid) return c;
    const detail = await this.api(`/api/complaints/${c.uuid}`);
    c.updates = (detail.history || []).map(u => ({
      status: u.new_status || '-',
      time: u.changed_at || '',
      remark: u.remark || '',
      changed_by: u.changed_by || ''
    }));
    if (detail.complaint) {
      c.status = detail.complaint.status || c.status;
      c.assigned_to = detail.complaint.assigned_to || c.assigned_to;
      c.location = detail.complaint.location || c.location;
    }
    return c;
  }

  async loadAnnouncements() {
    try {
      const rows = await this.api('/api/announcements');
      const mapped = (Array.isArray(rows) ? rows : []).map(a => this.mapAnnouncement(a));
      mapped.sort((x, y) => {
        if (!x.date && !y.date) return 0;
        if (!x.date) return 1;
        if (!y.date) return -1;
        return x.date < y.date ? 1 : (x.date > y.date ? -1 : 0);
      });
      this.state.announcements = mapped;
    } catch (e) {
      this.state.announcements = [];
      if (this.loggedIn) console.warn('Announcements load failed:', e.message);
    }
    return this.state.announcements;
  }

  async createAnnouncement(payload) {
    const body = {
      title: payload.title,
      description: payload.description,
      category: payload.category || 'General Notice',
      priority: payload.priority || 'Medium',
      event_date: payload.event_date || null,
      expiry_date: payload.expiry_date || null,
      attachment_url: payload.attachment_url || null
    };
    const created = await this.api('/api/announcements', { method: 'POST', body });
    await this.loadAnnouncements();
    return created;
  }

  async updateAnnouncement(announcementId, patch) {
    const updated = await this.api(`/api/announcements/${announcementId}`, { method: 'PATCH', body: patch });
    await this.loadAnnouncements();
    return updated;
  }

  async deleteAnnouncement(announcementId) {
    const result = await this.api(`/api/announcements/${announcementId}`, { method: 'DELETE' });
    await this.loadAnnouncements();
    return result;
  }

  mapAnnouncement(a) {
    return {
      id: a.announcement_id,
      title: a.title || '(notice)',
      description: a.description || a.title || '',
      category: a.category || 'Notice',
      priority: a.priority || 'Medium',
      date: a.event_date || a.created_at || '',
      venue: a.venue || '',
      content: a.description || a.title || '',
      status: a.status || 'Published',
      is_urgent: a.is_urgent === true || ['high', 'urgent'].includes(String(a.priority || '').toLowerCase()),
      author: a.created_by || '',
      expiry: a.expiry_date || '',
      published_on: a.published_at || '',
      created_on: a.created_at || '',
      village_id: a.village_id || '',
      village_name: this._villageName(a.village_id),
      attachment_url: a.attachment_url || ''
    };
  }

  async loadAuditLogs() {
    if (!this.isStaff) {
      this.state.auditLogs = [];
      this.state.auditTotal = 0;
      return this.state.auditLogs;
    }
    try {
      const f = this.state.auditFilters;
      const p = new URLSearchParams();
      p.set('limit', String(f.limit || 200));
      if (f.q) p.set('q', f.q);
      if (f.actor_id) p.set('actor_id', f.actor_id);
      if (f.action) p.set('action', f.action);
      if (f.reference) p.set('reference', f.reference);
      if (f.date_from) p.set('date_from', f.date_from);
      if (f.date_to) p.set('date_to', f.date_to);
      const d = await this.api(`/api/audit-logs?${p.toString()}`);
      const rows = Array.isArray(d) ? d : (d.results || []);
      this.state.auditTotal = Array.isArray(d) ? rows.length : (d.total || rows.length);
      this.state.auditLogs = rows.map(l => ({
        id: l.log_id || l.audit_id || `LOG-${l.id || ''}`,
        timestamp: l.created_at || l.timestamp || '',
        actor: l.actor_id || l.actor_name || '-',
        action: l.action || '-',
        entity_type: l.entity_type || '',
        entity_id: l.entity_id || '-',
        ip: l.ip_address || '',
        device: l.user_agent || '',
        details: l.remarks || l.details || (l.new_values && JSON.stringify(l.new_values)) || '-'
      }));
    } catch (e) {
      this.state.auditLogs = [];
      this.state.auditTotal = 0;
    }
    return this.state.auditLogs;
  }

  // ---- Citizen tax dues (real tax_records + payments) ------------------------
  async loadMyTaxes() {
    if (!this.loggedIn) return this.state.taxes;
    try {
      const d = await this.api('/api/tax/my-taxes');
      const rows = (d && d.records) || [];
      this.state.taxSummary = (d && d.summary) || null;
      this.state.taxProfile = (d && d.profile) || null;
      if (rows.length) {
        this.state.taxes = rows.map(t => ({
          id: t.tax_id,
          type: t.type,
          year: t.financial_year,
          property_no: t.assessment_number,
          frequency: t.frequency,
          amount: t.remaining_amount > 0 ? t.amount_due : t.amount_paid || t.amount_due,
          amount_due: t.amount_due,
          amount_paid: t.amount_paid,
          balance: t.remaining_amount,
          due_date: t.due_date,
          status: t.status === 'Paid' ? 'Paid' : 'Pending',
          is_overdue: !!t.is_overdue,
          payment_ref: t.last_payment ? t.last_payment.receipt_number : null,
          paid_at: t.last_payment ? t.last_payment.payment_date : null,
          payment_method: t.last_payment ? t.last_payment.payment_method : null,
          gateway: t.last_payment ? t.last_payment.gateway_name : null,
          txn_ref: t.last_payment ? t.last_payment.transaction_reference : null,
          payments: t.payments || []
        }));
      } else if (!this.isStaff) {
        this.state.taxes = [];
      }
    } catch (e) {
      if (this.loggedIn) console.warn('Taxes load failed:', e.message);
    }
    return this.state.taxes;
  }

  // ---- Citizen inbox (notices sent by the Panchayat Desk) -------------------
  async loadNotifications() {
    if (!this.loggedIn) { this.state.notifications = []; this.state.unread = 0; return; }
    try {
      const d = await this.api('/api/notifications?limit=20');
      this.state.notifications = (d && d.results) || [];
      this.state.unread = (d && d.unread) || 0;
    } catch (e) {
      this.state.notifications = [];
      this.state.unread = 0;
    }
    return this.state.notifications;
  }

  async markAllNotificationsRead() {
    try { await this.api('/api/notifications/read-all', { method: 'POST', body: {} }); } catch (e) { /* ignore */ }
    await this.loadNotifications();
  }

  // Real-time refresh used by the LIVE ticker on the operational desk.
  async liveUpdate() {
    if (!this.loggedIn) return false;
    try {
      if (this.isStaff) {
        await this.refresh();
      } else {
        await Promise.all([
          this.loadComplaints(''),
          this.loadAnnouncements(),
          this.loadNotifications().catch(() => {}),
          this.loadMyTaxes().catch(() => {})
        ]);
      }
      if (typeof window.renderAll === 'function') window.renderAll();
      if (typeof window.updateLiveIndicator === 'function') window.updateLiveIndicator();
      return true;
    } catch (e) {
      return false;
    }
  }

  // ---- Panchayat staff & dashboard ------------------------------------------

  async loadStaff() {
    if (!this.isStaff) { this.state.staff = []; return []; }
    try {
      const d = await this.api('/api/staff');
      this.state.staff = (d && d.staff) || [];
      return this.state.staff;
    } catch (e) {
      this.state.staff = [];
      return [];
    }
  }

  async addStaff(payload) {
    const created = await this.api('/api/staff', { method: 'POST', body: payload });
    await this.loadStaff();
    return created;
  }

  async setStaffAccount(userId, patch) {
    const updated = await this.api(`/api/staff/${userId}`, { method: 'PATCH', body: patch });
    await this.loadStaff();
    return updated;
  }

  async loadPanchayatDashboard() {
    if (!this.isStaff) return null;
    const vid = (this.user && this.user.village_id) ||
      (this.state.reference.villages[0] && this.state.reference.villages[0].village_id) || '';
    try {
      const q = vid ? `?village_id=${encodeURIComponent(vid)}` : '';
      const d = await this.api(`/api/dashboard/panchayat${q}`);
      this.state.dashboard = d;
      this.state.loadError = null;
      // Authoritative stage counts (from vw_complaints_by_status) so the
      // desk tabs/KPIs are correct even though the table shows one page.
      const counts = { submitted: 0, in_progress: 0, completed: 0 };
      (d.complaints_by_status || []).forEach(r => {
        const s = String(r.status || '').toLowerCase();
        const n = Number(r.total || 0);
        if (['submitted', 'under review', 'assigned'].includes(s)) counts.submitted += n;
        else if (['in progress', 'in_progress'].includes(s)) counts.in_progress += n;
        else if (['resolved', 'closed', 'rejected'].includes(s)) counts.completed += n;
      });
      this.state.dashboardStageCounts = counts;
      return d;
    } catch (e) {
      this.state.dashboard = null;
      this.state.loadError = e.message;
      return null;
    }
  }

  // ---- Operational trends (received / avg resolution / SLA / 7-30 day chart)
  async loadTrends() {
    if (!this.isStaff) return null;
    try {
      const d = await this.api(`/api/dashboard/trends?days=${Number(this.state.trendDays) || 30}`);
      this.state.trends = d;
      return d;
    } catch (e) {
      return this.state.trends; // keep last good data on failure
    }
  }

  // ---- Financial ledger management (Panchayat Desk) ------------------------
  _financeQuery() {
    const f = this.state.finance.filters;
    const q = new URLSearchParams();
    ['q', 'transaction_type', 'verification_status', 'category', 'financial_year', 'date_from', 'date_to']
      .forEach(k => { if (f[k]) q.set(k, f[k]); });
    return q;
  }

  async loadFinance() {
    if (!this.isStaff) { this.state.finance.records = []; this.state.finance.total = 0; return []; }
    const q = this._financeQuery();
    q.set('limit', String(this.state.finance.pageSize));
    q.set('offset', String((this.state.finance.page - 1) * this.state.finance.pageSize));
    try {
      const d = await this.api(`/api/finance/records?${q.toString()}`);
      this.state.finance.records = (d && d.results) || [];
      this.state.finance.total = d && typeof d.total === 'number' ? d.total : this.state.finance.records.length;
      return this.state.finance.records;
    } catch (e) {
      this.state.finance.records = [];
      this.state.finance.total = 0;
      throw e;
    }
  }

  async loadFinanceSummary() {
    if (!this.isStaff) { this.state.finance.summary = null; return null; }
    const q = this._financeQuery();
    try {
      const d = await this.api(`/api/finance/records/summary?${q.toString()}`);
      this.state.finance.summary = d;
      return d;
    } catch (e) {
      return this.state.finance.summary; // keep last good summary
    }
  }

  async createFinance(payload) {
    return this.api('/api/finance/records', { method: 'POST', body: payload });
  }

  async updateFinance(financialId, patch) {
    return this.api(`/api/finance/records/${encodeURIComponent(financialId)}`, { method: 'PATCH', body: patch });
  }

  async deleteFinance(financialId) {
    return this.api(`/api/finance/records/${encodeURIComponent(financialId)}`, { method: 'DELETE' });
  }

  async setFinanceVerification(financialId, status) {
    return this.api(`/api/finance/records/${encodeURIComponent(financialId)}/verification`, {
      method: 'POST', body: { status }
    });
  }

  upiQrUrl(amount, note) {
    const q = new URLSearchParams({ amount: String(amount || 0), name: 'Kumbhari Gram Panchayat' });
    if (note) q.set('note', String(note).slice(0, 50));
    return `${this.apiBase}/api/pay/upi-qr?${q.toString()}`;
  }

  // ---- Mutations -----------------------------------------------------------

  async addComplaint(data) {
    // data: { category_id, title, description, location, priority, ward(label) }
    const created = await this.api('/api/complaints', {
      method: 'POST',
      body: {
        category_id: data.category_id || data.category,
        title: data.title,
        description: data.description,
        location: data.location || null,
        priority: data.priority || 'Medium'
      }
    });
    const mapped = this.mapComplaint(created);
    this.state.complaints.unshift(mapped);
    return mapped;
  }

  async updateComplaintStatus(idOrUuid, newStatus, remark, assignedTo) {
    const c = this.state.complaints.find(x => x.id === idOrUuid || x.uuid === idOrUuid);
    if (!c) return null;
    const body = { new_status: newStatus, remark: remark || null };
    if (assignedTo) body.assigned_to = assignedTo;
    const result = await this.api(`/api/complaints/${c.uuid}/status`, {
      method: 'PATCH',
      body
    });
    c.status = newStatus;
    if (assignedTo) c.assigned_to = assignedTo;
    try { await this.loadComplaints(); } catch (e) { /* keep local */ }
    return { ...result, complaint: c };
  }

  async payTax(taxId, paymentMethod) {
    const tax = this.state.taxes.find(t => t.id === taxId);
    if (!tax) return null;
    const result = await this.api(`/api/tax/${encodeURIComponent(taxId)}/pay`, {
      method: 'POST',
      body: { payment_method: paymentMethod || 'UPI', gateway_name: (paymentMethod || 'UPI') === 'UPI' ? 'UPI QR' : paymentMethod }
    });
    await this.loadMyTaxes();
    const updated = this.state.taxes.find(t => t.id === taxId) || tax;
    const p = (result && result.payment) || {};
    return {
      tax: updated,
      ref: p.receipt_number || '',
      txn: p.transaction_reference || '',
      paid_at: p.payment_date || new Date().toISOString(),
      upi: (paymentMethod || 'UPI') === 'UPI',
      qr_url: this.upiQrUrl(updated.balance || updated.amount, `${updated.type} ${updated.year}`)
    };
  }

  // Kept for the admin costume change; local only.
  setRole(role) {
    this.state.activeRole = role;
    localStorage.setItem('gramsetu_role', role);
  }

  setLanguage(lang) {
    if (I18N[lang]) {
      this.state.currentLang = lang;
      localStorage.setItem('gramsetu_lang', lang);
    }
  }
}

// ---- Global App Instance ---------------------------------------------------

if (typeof window !== 'undefined') {
  window.gramSetu = new GramSetuClient();
}