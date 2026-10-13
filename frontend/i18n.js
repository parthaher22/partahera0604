/* ==========================================================================
   GramSetu i18n engine
   --------------------------------------------------------------------------
   Lightweight, dependency-free translator for the whole UI.

   How it works
   ------------
   A single dictionary maps an English source string to [Hindi, Marathi].
   The engine walks the live DOM and swaps matching text nodes and the
   translatable attributes (placeholder / title / aria-label) in place. A
   MutationObserver re-applies the translation to content that JavaScript
   renders later (tables, modals, toasts, ...), so dynamic screens translate
   too, not just the initial markup.

   The English string is always preserved internally, so switching
   EN -> HI -> MR -> EN is lossless and never corrupts the page.

   Public API (window.GramSetuI18N)
   --------------------------------
     apply(lang)   'en' | 'hi' | 'mr'  -> translate the page
     get()                             -> current language code
     t(english)                        -> translate a single string (JS use)
   ========================================================================== */
(function () {
  'use strict';

  var STORAGE_KEY = 'gramsetu_lang';
  var ATTRS = ['placeholder', 'title', 'aria-label'];

  /* English -> [Hindi, Marathi]. Proper nouns, codes and pure numbers are
     intentionally omitted so they pass through unchanged. */
  var DICT = {
    /* ---- Global / brand ---- */
    "Gram Panchayat Messages": ["ग्राम पंचायत संदेश", "ग्रामपंचायत संदेश"],
    "GramSetu - Kumbhari Gram Panchayat Digital Portal": ["ग्रामसेतू - कुंभारी ग्राम पंचायत डिजिटल पोर्टल", "ग्रामसेतू - कुंभारी ग्रामपंचायत डिजिटल पोर्टल"],
    "GramSetu - Kumbhari Panchayat": ["ग्रामसेतू - कुंभारी पंचायत", "ग्रामसेतू - कुंभारी पंचायत"],
    "GramSetu - Kumbhari Gram Panchayat Operational Desk": ["ग्रामसेतू - कुंभारी ग्राम पंचायत परिचालन डेस्क", "ग्रामसेतू - कुंभारी ग्रामपंचायत कार्यालय डेस्क"],
    "Kumbhari Gram Panchayat": ["कुंभारी ग्राम पंचायत", "कुंभारी ग्रामपंचायत"],
    "Kumbhari Panchayat": ["कुंभारी पंचायत", "कुंभारी पंचायत"],
    "Kumbhari Citizen Helpdesk": ["कुंभारी नागरिक हेल्पडेस्क", "कुंभारी नागरिक हेल्पडेस्क"],
    "Kumbhari Gram Panchayat Operational Desk": ["कुंभारी ग्राम पंचायत परिचालन डेस्क", "कुंभारी ग्रामपंचायत कार्यालय डेस्क"],
    "Kumbhari Gram Panchayat • 15th Finance Commission Sanctioned": ["कुंभारी ग्राम पंचायत • 15वें वित्त आयोग द्वारा स्वीकृत", "कुंभारी ग्रामपंचायत • १५व्या वित्त आयोग मान्यताप्राप्त"],
    "Villager & Panchayat Digital Gateway": ["ग्रामीण एवं पंचायत डिजिटल द्वार", "ग्रामस्थ व ग्रामपंचायत डिजिटल प्रवेशद्वार"],
    "Official Portal": ["आधिकारिक पोर्टल", "अधिकृत पोर्टल"],
    "Panchayat Portal": ["पंचायत पोर्टल", "पंचायत पोर्टल"],
    "Official Citizen Services & Transparency Platform • Kumbhari, Kopargaon, Maharashtra": ["आधिकारिक नागरिक सेवाएं एवं पारदर्शिता मंच • कुंभारी, कोपरगाव, महाराष्ट्र", "अधिकृत नागरिक सेवा व पारदर्शकता मंच • कुंभारी, कोपरगाव, महाराष्ट्र"],
    "© 2026 GramSetu • Kumbhari": ["© 2026 ग्रामसेतू • कुंभारी", "© २०२६ ग्रामसेतू • कुंभारी"],
    "Kumbhari, Taluka Kopargaon, Maharashtra": ["कुंभारी, तालुका कोपरगाव, महाराष्ट्र", "कुंभारी, तालुका कोपरगाव, महाराष्ट्र"],
    "Kopargaon, Maharashtra": ["कोपरगाव, महाराष्ट्र", "कोपरगाव, महाराष्ट्र"],
    "Administrative Layer": ["प्रशासनिक परत", "प्रशासकीय स्तर"],
    "Authorized Administrative Layer": ["अधिकृत प्रशासनिक परत", "अधिकृत प्रशासकीय स्तर"],
    "Secure via backend JWT authentication • Passwords are never stored in the browser.": ["बैकएंड JWT प्रमाणीकरण से सुरक्षित • पासवर्ड कभी ब्राउज़र में संग्रहीत नहीं होते।", "बॅकएंड JWT प्रमाणीकरणाद्वारे सुरक्षित • पासवर्ड कधीही ब्राउझरमध्ये साठवले जात नाहीत."],

    /* ---- Header / roles / language ---- */
    "Citizen View": ["नागरिक दृश्य", "नागरिक दृश्य"],
    "Citizen": ["नागरिक", "नागरिक"],
    "Villager": ["ग्रामीण", "ग्रामस्थ"],
    "Panchayat Desk": ["पंचायत डेस्क", "पंचायत डेस्क"],
    "Panchayat Admin": ["पंचायत प्रशासक", "पंचायत प्रशासक"],
    "Panchayat Staff": ["पंचायत कर्मचारी", "ग्रामपंचायत कर्मचारी"],
    "Staff": ["कर्मचारी", "कर्मचारी"],
    "Admin Accounts": ["प्रशासक खाते", "प्रशासक खाती"],
    "Signed in as:": ["इस रूप में साइन इन:", "या नावाने साइन इन:"],
    "Logged in as:": ["इस रूप में लॉग इन:", "या नावाने लॉग इन:"],
    "Not signed in": ["साइन इन नहीं", "साइन इन केलेले नाही"],
    "Sign In": ["साइन इन", "साइन इन"],
    "Sign out": ["साइन आउट", "साइन आउट"],
    "Sign In to Dashboard": ["डैशबोर्ड में साइन इन करें", "डॅशबोर्डमध्ये साइन इन करा"],
    "Logout": ["लॉगआउट", "लॉगआउट"],
    "Guest": ["अतिथि", "पाहुणे"],
    "Return to Citizen View": ["नागरिक दृश्य पर लौटें", "नागरिक दृश्यावर परत जा"],
    "Change My Password": ["मेरा पासवर्ड बदलें", "माझा पासवर्ड बदला"],
    "Change password": ["पासवर्ड बदलें", "पासवर्ड बदला"],
    "Update Password": ["पासवर्ड अपडेट करें", "पासवर्ड अद्ययावत करा"],
    "Current Password *": ["वर्तमान पासवर्ड *", "सध्याचा पासवर्ड *"],
    "New Password *": ["नया पासवर्ड *", "नवीन पासवर्ड *"],
    "Confirm New Password *": ["नए पासवर्ड की पुष्टि करें *", "नवीन पासवर्डची पुष्टी करा *"],
    "Password *": ["पासवर्ड *", "पासवर्ड *"],
    "Password (min 6 chars) *": ["पासवर्ड (कम से कम 6 अक्षर) *", "पासवर्ड (किमान ६ अक्षरे) *"],
    "Enter your current password and set a new one.": ["अपना वर्तमान पासवर्ड डालें और नया पासवर्ड सेट करें।", "तुमचा सध्याचा पासवर्ड टाका आणि नवीन पासवर्ड सेट करा."],

    /* ---- Navigation ---- */
    "Dashboard": ["डैशबोर्ड", "डॅशबोर्ड"],
    "Grievance Tracking": ["शिकायत ट्रैकिंग", "तक्रार ट्रॅकिंग"],
    "Grievances": ["शिकायतें", "तक्रारी"],
    "Grievance Redressal": ["शिकायत निवारण", "तक्रार निवारण"],
    "Grievance Category *": ["शिकायत श्रेणी *", "तक्रार श्रेणी *"],
    "Grievance Management Desk": ["शिकायत प्रबंधन डेस्क", "तक्रार व्यवस्थापन डेस्क"],
    "Grievance Pipeline (by status)": ["शिकायत पाइपलाइन (स्थिति अनुसार)", "तक्रार पाइपलाइन (स्थितीनुसार)"],
    "Notice Board": ["सूचना पटल", "सूचना फलक"],
    "Digital Notice Board": ["डिजिटल सूचना पटल", "डिजिटल सूचना फलक"],
    "Digital Notice Board - Panchayat Desk": ["डिजिटल सूचना पटल - पंचायत डेस्क", "डिजिटल सूचना फलक - पंचायत डेस्क"],
    "Notices": ["सूचनाएं", "सूचना"],
    "Notice": ["सूचना", "सूचना"],
    "Welfare Schemes": ["कल्याणकारी योजनाएं", "कल्याणकारी योजना"],
    "Financial Transparency": ["वित्तीय पारदर्शिता", "आर्थिक पारदर्शकता"],
    "Financials": ["वित्तीय विवरण", "आर्थिक तपशील"],
    "Services & Tax": ["सेवाएं एवं कर", "सेवा व कर"],
    "Panchayat Leadership & Member Contacts": ["पंचायत नेतृत्व एवं सदस्य संपर्क", "पंचायत नेतृत्व व सदस्य संपर्क"],
    "Manage Panchayat Staff": ["पंचायत कर्मचारी प्रबंधन", "ग्रामपंचायत कर्मचारी व्यवस्थापन"],
    "Audit trail": ["ऑडिट ट्रेल", "ऑडिट ट्रेल"],
    "Audit Events": ["ऑडिट घटनाएं", "ऑडिट घटना"],
    "Site Map": ["साइट मैप", "साइट नकाशा"],
    "Privacy": ["गोपनीयता", "गोपनीयता"],

    /* ---- Dashboard cards ---- */
    "Citizen Dashboard -": ["नागरिक डैशबोर्ड -", "नागरिक डॅशबोर्ड -"],
    "Active Grievances": ["सक्रिय शिकायतें", "सक्रिय तक्रारी"],
    "Pending Taxes": ["बकाया कर", "थकबाकी कर"],
    "Pending / Overdue": ["बकाया / विलंबित", "प्रलंबित / थकीत"],
    "Official Announcements & Alerts": ["आधिकारिक घोषणाएं एवं सूचनाएं", "अधिकृत घोषणा व सूचना"],
    "Official Notices & Alerts - Kumbhari GP": ["आधिकारिक सूचनाएं एवं अलर्ट - कुंभारी ग्रा.पं.", "अधिकृत सूचना व सूचना - कुंभारी ग्रा.पं."],
    "Village Works Budget": ["ग्राम विकास कार्य बजट", "ग्राम विकासकामे अर्थसंकल्प"],
    "Public Village Budget & Work Expenditure": ["सार्वजनिक ग्राम बजट एवं कार्य व्यय", "सार्वजनिक ग्राम अर्थसंकल्प व काम खर्च"],
    "Upcoming Kumbhari Gram Sabha & Events": ["आगामी कुंभारी ग्रामसभा एवं कार्यक्रम", "आगामी कुंभारी ग्रामसभा व कार्यक्रम"],
    "Gram Sabha": ["ग्रामसभा", "ग्रामसभा"],
    "Emergency & Helplines": ["आपातकालीन एवं हेल्पलाइन", "तातडीचे व हेल्पलाईन"],
    "Emergency Alert": ["आपातकालीन अलर्ट", "तातडीची सूचना"],
    "Within Kumbhari GP • Kopargaon, Maharashtra": ["कुंभारी ग्रा.पं. के भीतर • कोपरगाव, महाराष्ट्र", "कुंभारी ग्रा.पं. अंतर्गत • कोपरगाव, महाराष्ट्र"],
    "Village Roads & Potholes": ["ग्राम सड़कें एवं गड्ढे", "गाव रस्ते व खड्डे"],
    "Water Supply & Pipeline": ["जल आपूर्ति एवं पाइपलाइन", "पाणीपुरवठा व पाइपलाइन"],
    "Streetlights & Electricity": ["स्ट्रीटलाइट एवं विद्युत", "पथदीप व वीज"],
    "Sanitation & Drainage": ["स्वच्छता एवं जल निकासी", "स्वच्छता व गटार"],
    "Public Health & Anganwadi": ["जन स्वास्थ्य एवं आंगनवाड़ी", "सार्वजनिक आरोग्य व अंगणवाडी"],
    "Agriculture & Irrigation": ["कृषि एवं सिंचाई", "शेती व पाटबंधारे"],
    "Water Supply": ["जल आपूर्ति", "पाणीपुरवठा"],
    "Tax / Revenue": ["कर / राजस्व", "कर / महसूल"],

    /* ---- Buttons & actions ---- */
    "Lodge New Grievance": ["नई शिकायत दर्ज करें", "नवीन तक्रार नोंदवा"],
    "Lodge Citizen Grievance": ["नागरिक शिकायत दर्ज करें", "नागरिक तक्रार नोंदवा"],
    "Lodge Another Grievance": ["और शिकायत दर्ज करें", "अजून तक्रार नोंदवा"],
    "Submit Grievance": ["शिकायत सबमिट करें", "तक्रार सबमिट करा"],
    "Submit civic issues directly to Kumbhari Gram Panchayat.": ["नागरिक समस्याएं सीधे कुंभारी ग्राम पंचायत को सबमिट करें।", "नागरी समस्या थेट कुंभारी ग्रामपंचायतीकडे सबमिट करा."],
    "Track Status": ["स्थिति ट्रैक करें", "स्थिती तपासा"],
    "Track Full Timeline": ["पूरी समयरेखा देखें", "संपूर्ण कालरेषा पहा"],
    "Complaint Resolution Lifecycle": ["शिकायत निवारण जीवनचक्र", "तक्रार निवारण जीवनचक्र"],
    "Update Complaint Lifecycle": ["शिकायत जीवनचक्र अपडेट करें", "तक्रार जीवनचक्र अद्ययावत करा"],
    "Save & Notify Citizen": ["सहेजें और नागरिक को सूचित करें", "जतन करा व नागरिकाला कळवा"],
    "Browse Schemes": ["योजनाएं देखें", "योजना पहा"],
    "Browse All Schemes": ["सभी योजनाएं देखें", "सर्व योजना पहा"],
    "View All Notices & Agenda": ["सभी सूचनाएं एवं कार्यसूची देखें", "सर्व सूचना व कार्यसूची पहा"],
    "View all": ["सभी देखें", "सर्व पहा"],
    "View": ["देखें", "पहा"],
    "Preview": ["पूर्वावलोकन", "पूर्वदृश्य"],
    "Print": ["प्रिंट करें", "प्रिंट करा"],
    "Print Receipt": ["रसीद प्रिंट करें", "पावती प्रिंट करा"],
    "Download": ["डाउनलोड करें", "डाउनलोड करा"],
    "Download Login Accounts": ["लॉगिन खाते डाउनलोड करें", "लॉगिन खाती डाउनलोड करा"],
    "Export CSV": ["CSV निर्यात करें", "CSV निर्यात करा"],
    "Pay Dues Online": ["ऑनलाइन बकाया भरें", "ऑनलाइन थकबाकी भरा"],
    "Pay & Generate Receipt": ["भुगतान करें एवं रसीद बनाएं", "भरणा करा व पावती तयार करा"],
    "I've Paid - Verify & Generate Receipt": ["मैंने भुगतान किया - सत्यापित करें एवं रसीद बनाएं", "मी भरले - पडताळा व पावती तयार करा"],
    "Add Entry": ["प्रविष्टि जोड़ें", "नोंद जोडा"],
    "Add Financial Entry": ["वित्तीय प्रविष्टि जोड़ें", "आर्थिक नोंद जोडा"],
    "Add Panchayat Staff": ["पंचायत कर्मचारी जोड़ें", "ग्रामपंचायत कर्मचारी जोडा"],
    "Add Staff": ["कर्मचारी जोड़ें", "कर्मचारी जोडा"],
    "Create Staff Account": ["कर्मचारी खाता बनाएं", "कर्मचारी खाते तयार करा"],
    "Create Citizen Account": ["नागरिक खाता बनाएं", "नागरिक खाते तयार करा"],
    "Create the first notice": ["पहली सूचना बनाएं", "पहिली सूचना तयार करा"],
    "Create a staff/admin login for the Panchayat Desk.": ["पंचायत डेस्क के लिए कर्मचारी/प्रशासक लॉगिन बनाएं।", "पंचायत डेस्कसाठी कर्मचारी/प्रशासक लॉगिन तयार करा."],
    "Add a Panchayat staff member so grievances and notices can be shared across the desk.": ["पंचायत कर्मचारी जोड़ें ताकि शिकायतें और सूचनाएं डेस्क पर साझा की जा सकें।", "ग्रामपंचायत कर्मचारी जोडा जेणेकरून तक्रारी व सूचना डेस्कवर सामायिक होतील."],
    "Add the first entry": ["पहली प्रविष्टि जोड़ें", "पहिली नोंद जोडा"],
    "Add the first staff member": ["पहला कर्मचारी जोड़ें", "पहिला कर्मचारी जोडा"],
    "Add village income and expenditure - the ledger feeds the finance KPIs above.": ["ग्राम आय एवं व्यय जोड़ें - बहीखाता ऊपर के वित्तीय KPI को पोषित करता है।", "गाव उत्पन्न व खर्च जोडा - खतावणी वरील आर्थिक KPI ला पोषण देते."],
    "Add, edit, promote, deactivate": ["जोड़ें, संपादित करें, पदोन्नत करें, निष्क्रिय करें", "जोडा, संपादित करा, बढती द्या, निष्क्रिय करा"],
    "Add, edit, verify & export": ["जोड़ें, संपादित करें, सत्यापित करें एवं निर्यात करें", "जोडा, संपादित करा, पडताळा व निर्यात करा"],
    "Add, edit, verify, delete & export": ["जोड़ें, संपादित करें, सत्यापित करें, हटाएं एवं निर्यात करें", "जोडा, संपादित करा, पडताळा, हटवा व निर्यात करा"],
    "Draft, publish, archive or delete official notices. Published items appear instantly to citizens.": ["आधिकारिक सूचनाएं ड्राफ्ट करें, प्रकाशित करें, संग्रहीत या हटाएं। प्रकाशित सूचनाएं नागरिकों को तुरंत दिखाई देती हैं।", "अधिकृत सूचना मसुदा करा, प्रकाशित करा, संग्रहित करा किंवा हटवा. प्रकाशित सूचना नागरिकांना लगेच दिसतात."],
    "Draft, publish, schedule, archive": ["ड्राफ्ट करें, प्रकाशित करें, निर्धारित करें, संग्रहीत करें", "मसुदा करा, प्रकाशित करा, नियोजित करा, संग्रहित करा"],
    "Draft, publish, schedule, archive, delete": ["ड्राफ्ट करें, प्रकाशित करें, निर्धारित करें, संग्रहीत करें, हटाएं", "मसुदा करा, प्रकाशित करा, नियोजित करा, संग्रहित करा, हटवा"],
    "Draft an official notice - citizens see it on the village board the moment you publish.": ["आधिकारिक सूचना का ड्राफ्ट बनाएं - प्रकाशित करते ही नागरिक इसे ग्राम पटल पर देखते हैं।", "अधिकृत सूचनेचा मसुदा तयार करा - प्रकाशित करताच नागरिक ती ग्राम फलकावर पाहतात."],
    "Publish New Notice": ["नई सूचना प्रकाशित करें", "नवीन सूचना प्रकाशित करा"],
    "New Notice": ["नई सूचना", "नवीन सूचना"],
    "Save as Draft": ["ड्राफ्ट के रूप में सहेजें", "मसुदा म्हणून जतन करा"],
    "Notices are saved as Draft and published when you choose.": ["सूचनाएं ड्राफ्ट के रूप में सहेजी जाती हैं और आपके चुनने पर प्रकाशित होती हैं।", "सूचना मसुदा म्हणून जतन होतात आणि तुम्ही निवडल्यावर प्रकाशित होतात."],
    "Retry": ["पुनः प्रयास करें", "पुन्हा प्रयत्न करा"],
    "Refresh": ["ताज़ा करें", "रिफ्रेश करा"],
    "Refresh data": ["डेटा ताज़ा करें", "डेटा रिफ्रेश करा"],
    "Reset": ["रीसेट करें", "रीसेट करा"],
    "Clear": ["साफ़ करें", "साफ करा"],
    "Clear filters": ["फ़िल्टर साफ़ करें", "फिल्टर साफ करा"],
    "Filter": ["फ़िल्टर", "फिल्टर"],
    "Sort": ["क्रमबद्ध करें", "क्रमवारी"],
    "Order": ["क्रम", "क्रम"],
    "Search": ["खोजें", "शोधा"],
    "Next": ["आगे", "पुढे"],
    "Prev": ["पिछला", "मागे"],
    "Close": ["बंद करें", "बंद करा"],
    "Cancel": ["रद्द करें", "रद्द करा"],
    "Save": ["सहेजें", "जतन करा"],
    "Save Entry": ["प्रविष्टि सहेजें", "नोंद जतन करा"],
    "Confirm": ["पुष्टि करें", "पुष्टी करा"],
    "Please confirm": ["कृपया पुष्टि करें", "कृपया पुष्टी करा"],
    "Delete": ["हटाएं", "हटवा"],
    "Edit": ["संपादित करें", "संपादित करा"],
    "Manage": ["प्रबंधित करें", "व्यवस्थापन"],
    "Done": ["हो गया", "झाले"],
    "All": ["सभी", "सर्व"],
    "Loading…": ["लोड हो रहा है…", "लोड होत आहे…"],
    "Loading live budget…": ["लाइव बजट लोड हो रहा है…", "थेट अर्थसंकल्प लोड होत आहे…"],
    "Chart loads with the first refresh…": ["चार्ट पहले रीफ्रेश के साथ लोड होता है…", "चार्ट पहिल्या रिफ्रेशसोबत लोड होतो…"],
    "Check back soon for official Gram Panchayat updates.": ["आधिकारिक ग्राम पंचायत अपडेट के लिए जल्द ही फिर देखें।", "अधिकृत ग्रामपंचायत अद्ययावतांसाठी लवकरच पुन्हा पहा."],
    "Could not reach the GramSetu server.": ["ग्रामसेतू सर्वर से संपर्क नहीं हो सका।", "ग्रामसेतू सर्व्हरशी संपर्क होऊ शकला नाही."],
    "No messages yet.": ["अभी कोई संदेश नहीं।", "अजून कोणतेही संदेश नाहीत."],
    "Mark all read": ["सभी पढ़ा हुआ चिह्नित करें", "सर्व वाचलेले म्हणून खूण करा"],
    "Load": ["लोड करें", "लोड करा"],

    /* ---- Statuses / lifecycle ---- */
    "Submitted": ["दर्ज", "नोंदणीकृत"],
    "Submitted (Registered)": ["दर्ज (पंजीकृत)", "नोंदणीकृत (नोंदवलेले)"],
    "Under Review": ["समीक्षा के अधीन", "छाननी सुरू"],
    "Under Review (Inspecting)": ["समीक्षा के अधीन (निरीक्षण)", "छाननी सुरू (पाहणी)"],
    "In Progress": ["प्रगति पर", "काम सुरू"],
    "In Progress (Field Work Active)": ["प्रगति पर (क्षेत्रीय कार्य सक्रिय)", "काम सुरू (जागेवर काम सुरू)"],
    "Resolved": ["निराकरण पूर्ण", "निराकरण झाले"],
    "Resolved (Work Complete)": ["निराकरण पूर्ण (कार्य पूर्ण)", "निराकरण झाले (काम पूर्ण)"],
    "Resolved & Closed": ["निराकरण एवं बंद", "निराकरण व बंद"],
    "Completed": ["पूर्ण", "पूर्ण"],
    "Closed": ["बंद", "बंद"],
    "Rejected": ["अस्वीकृत", "नामंजूर"],
    "Pending": ["लंबित", "प्रलंबित"],
    "Pending Review": ["समीक्षा लंबित", "छाननी प्रलंबित"],
    "Pending Verification": ["सत्यापन लंबित", "पडताळणी प्रलंबित"],
    "Verified": ["सत्यापित", "पडताळलेले"],
    "Published": ["प्रकाशित", "प्रकाशित"],
    "Drafts": ["ड्राफ्ट", "मसुदे"],
    "Archived": ["संग्रहीत", "संग्रहित"],
    "Expired": ["समाप्त", "कालबाह्य"],
    "Expires": ["समाप्त होता है", "कालबाह्य होते"],
    "Active Expiry": ["सक्रिय समाप्ति", "सक्रिय कालबाह्य"],
    "Paid": ["भुगतान किया", "भरले"],
    "Assessed": ["निर्धारित", "आकारले"],
    "Assigned": ["सौंपा गया", "नेमले"],
    "Overdue (SLA)": ["विलंबित (SLA)", "थकीत (SLA)"],
    "Due soon": ["जल्द देय", "लवकर देय"],
    "High": ["उच्च", "उच्च"],
    "Medium": ["मध्यम", "मध्यम"],
    "Low": ["निम्न", "कमी"],
    "Urgent": ["अत्यावश्यक", "तातडीचे"],
    "High (Urgent)": ["उच्च (अत्यावश्यक)", "उच्च (तातडीचे)"],
    "Priority": ["प्राथमिकता", "प्राधान्य"],
    "Status": ["स्थिति", "स्थिती"],
    "Status:": ["स्थिति:", "स्थिती:"],
    "Status Stage *": ["स्थिति चरण *", "स्थिती टप्पा *"],

    /* ---- Grievance form / list ---- */
    "All your grievances - visible only to you & the Panchayat Desk": ["आपकी सभी शिकायतें - केवल आपको एवं पंचायत डेस्क को दिखाई देती हैं", "तुमच्या सर्व तक्रारी - फक्त तुम्हाला व पंचायत डेस्कला दिसतात"],
    "Lodge & track own only": ["केवल अपनी दर्ज एवं ट्रैक करें", "फक्त स्वतःच्या नोंदवा व ट्रॅक करा"],
    "Issue Subject / Title *": ["समस्या विषय / शीर्षक *", "समस्या विषय / शीर्षक *"],
    "Detailed Description *": ["विस्तृत विवरण *", "सविस्तर वर्णन *"],
    "Description": ["विवरण", "वर्णन"],
    "Description *": ["विवरण *", "वर्णन *"],
    "Subject": ["विषय", "विषय"],
    "Category": ["श्रेणी", "श्रेणी"],
    "Category *": ["श्रेणी *", "श्रेणी *"],
    "Category & Ward": ["श्रेणी एवं वार्ड", "श्रेणी व प्रभाग"],
    "Ward *": ["वार्ड *", "प्रभाग *"],
    "Ward Number *": ["वार्ड क्रमांक *", "प्रभाग क्रमांक *"],
    "House Number": ["मकान नंबर", "घर क्रमांक"],
    "Location Landmark": ["स्थान लैंडमार्क", "ठिकाण खूण"],
    "Specific Landmark / Location *": ["विशिष्ट लैंडमार्क / स्थान *", "विशिष्ट खूण / ठिकाण *"],
    "Address": ["पता", "पत्ता"],
    "After this date the notice auto-hides from citizens.": ["इस तिथि के बाद सूचना नागरिकों से स्वतः छिप जाती है।", "या तारखेनंतर सूचना नागरिकांपासून स्वतः लपते."],
    "Attachment": ["संलग्नक", "जोडपत्र"],
    "Attachment link (optional)": ["संलग्नक लिंक (वैकल्पिक)", "जोडपत्र लिंक (ऐच्छिक)"],
    "Document link (optional)": ["दस्तावेज़ लिंक (वैकल्पिक)", "दस्तऐवज लिंक (ऐच्छिक)"],
    "Email (optional)": ["ईमेल (वैकल्पिक)", "ईमेल (ऐच्छिक)"],
    "Mobile": ["मोबाइल", "मोबाइल"],
    "Mobile Number *": ["मोबाइल नंबर *", "मोबाइल क्रमांक *"],
    "Full Name *": ["पूरा नाम *", "पूर्ण नाम *"],
    "Name": ["नाम", "नाव"],
    "Date": ["तिथि", "तारीख"],
    "Date *": ["तिथि *", "तारीख *"],
    "Date filed": ["दर्ज तिथि", "नोंद तारीख"],
    "Date:": ["तिथि:", "तारीख:"],
    "Details": ["विवरण", "तपशील"],
    "Type": ["प्रकार", "प्रकार"],
    "Reference": ["संदर्भ", "संदर्भ"],
    "Reference (optional)": ["संदर्भ (वैकल्पिक)", "संदर्भ (ऐच्छिक)"],
    "Applicant": ["आवेदक", "अर्जदार"],
    "Assigned To": ["को सौंपा गया", "को नेमले"],
    "Assigned Officer": ["नियुक्त अधिकारी", "नेमलेले अधिकारी"],
    "Assigned": ["सौंपा गया", "नेमले"],
    "Complaint ID": ["शिकायत आईडी", "तक्रार आयडी"],
    "Timestamp": ["समय-चिह्न", "वेळ-नोंद"],
    "Actor": ["कर्ता", "कर्ता"],
    "Action": ["कार्रवाई", "कृती"],
    "Actions": ["कार्रवाइयां", "कृती"],
    "Role": ["भूमिका", "भूमिका"],
    "Role *": ["भूमिका *", "भूमिका *"],
    "Log ID": ["लॉग आईडी", "लॉग आयडी"],
    "Village": ["गांव", "गाव"],
    "Village *": ["गांव *", "गाव *"],
    "All actions": ["सभी कार्रवाइयां", "सर्व कृती"],
    "All categories": ["सभी श्रेणियां", "सर्व श्रेणी"],
    "All statuses": ["सभी स्थितियां", "सर्व स्थिती"],
    "All types": ["सभी प्रकार", "सर्व प्रकार"],
    "Any status": ["कोई भी स्थिति", "कोणतीही स्थिती"],
    "Newest first": ["नवीनतम पहले", "नवीनतम आधी"],
    "Oldest first": ["पुराने पहले", "जुने आधी"],
    "per page": ["प्रति पृष्ठ", "प्रति पृष्ठ"],
    "Export CSV": ["CSV निर्यात करें", "CSV निर्यात करा"],

    /* ---- Notice / scheme content ---- */
    "General Notice": ["सामान्य सूचना", "सामान्य सूचना"],
    "Event / Meeting": ["कार्यक्रम / बैठक", "कार्यक्रम / बैठक"],
    "Notice Title *": ["सूचना शीर्षक *", "सूचना शीर्षक *"],
    "Notice Date *": ["सूचना तिथि *", "सूचना तारीख *"],
    "Notice Text - English *": ["सूचना पाठ - अंग्रेज़ी *", "सूचना मजकूर - इंग्रजी *"],
    "Publish later (optional)": ["बाद में प्रकाशित करें (वैकल्पिक)", "नंतर प्रकाशित करा (ऐच्छिक)"],
    "Expiry Date (optional)": ["समाप्ति तिथि (वैकल्पिक)", "कालबाह्य तारीख (ऐच्छिक)"],
    "Set a date & time to schedule the notice - it stays hidden from citizens until then.": ["सूचना निर्धारित करने के लिए तिथि एवं समय सेट करें - तब तक यह नागरिकों से छिपी रहती है।", "सूचना नियोजित करण्यासाठी तारीख व वेळ सेट करा - तोपर्यंत ती नागरिकांपासून लपलेली असते."],
    "The date shown on the board badge - notices are listed newest first by this date.": ["पटल बैज पर दिखाई गई तिथि - सूचनाएं इस तिथि से नवीनतम पहले सूचीबद्ध होती हैं।", "फलक बॅजवर दर्शविलेली तारीख - सूचना या तारखेनुसार नवीनतम आधी सूचीबद्ध होतात."],
    "Last Updated": ["अंतिम अद्यतन", "शेवटचे अद्ययावत"],
    "Last updated": ["अंतिम अद्यतन", "शेवटचे अद्ययावत"],
    "Central Scheme": ["केंद्रीय योजना", "केंद्रीय योजना"],
    "State Scheme": ["राज्य योजना", "राज्य योजना"],
    "Government Welfare": ["सरकारी कल्याण", "शासकीय कल्याण"],
    "Government welfare schemes": ["सरकारी कल्याणकारी योजनाएं", "शासकीय कल्याणकारी योजना"],
    "Eligibility Criteria:": ["पात्रता मानदंड:", "पात्रता निकष:"],
    "Required Documents:": ["आवश्यक दस्तावेज़:", "आवश्यक कागदपत्रे:"],
    "Key Financial Benefit:": ["मुख्य वित्तीय लाभ:", "मुख्य आर्थिक लाभ:"],
    "Women": ["महिलाएं", "महिला"],
    "Farmer": ["किसान", "शेतकरी"],
    "Education": ["शिक्षा", "शिक्षण"],
    "Health": ["स्वास्थ्य", "आरोग्य"],
    "Housing": ["आवास", "गृहनिर्माण"],
    "Farmer Welfare": ["किसान कल्याण", "शेतकरी कल्याण"],
    "Direct Benefit Transfer & Subsidies": ["प्रत्यक्ष लाभ हस्तांतरण एवं सब्सिडी", "थेट लाभ हस्तांतरण व अनुदान"],
    "₹6,000 Annual Farmer DBT": ["₹6,000 वार्षिक किसान DBT", "₹६,००० वार्षिक शेतकरी DBT"],
    "₹6,000 per year": ["₹6,000 प्रति वर्ष", "₹६,००० प्रति वर्ष"],
    "₹1,500/mo Women Aid": ["₹1,500/माह महिला सहायता", "₹१,५००/महिना महिला सहाय्य"],
    "₹1.20L Pucca House Aid": ["₹1.20 लाख पक्का आवास सहायता", "₹१.२० लाख पक्के घर सहाय्य"],
    "Pradhan Mantri Awas": ["प्रधानमंत्री आवास", "प्रधानमंत्री आवास"],
    "PM-Kisan Samman Nidhi": ["पीएम-किसान सम्मान निधि", "पीएम-किसान सन्मान निधी"],
    "Ladki Bahin Yojana": ["लाड़की बहिन योजना", "लाडकी बहीण योजना"],
    "Ujjwala Yojana": ["उज्ज्वला योजना", "उज्ज्वला योजना"],
    "Free Gas Connection Aid": ["मुफ़्त गैस कनेक्शन सहायता", "मोफत गॅस जोडणी सहाय्य"],

    /* ---- Tax / payment ---- */
    "Citizen Tax & Dues Portal (Ghar Patti & Pani Patti)": ["नागरिक कर एवं देय पोर्टल (घरपट्टी एवं पानीपट्टी)", "नागरिक कर व देय पोर्टल (घरपट्टी व पाणीपट्टी)"],
    "Pay official Kumbhari Gram Panchayat property and utility taxes online with instant downloadable receipts.": ["आधिकारिक कुंभारी ग्राम पंचायत संपत्ति एवं उपयोगिता कर ऑनलाइन भरें, तुरंत डाउनलोड करने योग्य रसीदों के साथ।", "अधिकृत कुंभारी ग्रामपंचायत मालमत्ता व सेवा कर ऑनलाइन भरा, त्वरित डाउनलोड करण्यायोग्य पावत्यांसह."],
    "Online Tax Payment Gateway": ["ऑनलाइन कर भुगतान गेटवे", "ऑनलाइन कर भरणा गेटवे"],
    "House Tax (Ghar Patti)": ["घर कर (घरपट्टी)", "घरपट्टी"],
    "House Tax FY 26-27": ["घर कर वि.व. 26-27", "घरपट्टी आ.व. २६-२७"],
    "Tax Type": ["कर प्रकार", "कर प्रकार"],
    "Taxpayer:": ["करदाता:", "करदाता:"],
    "Total Paid": ["कुल भुगतान", "एकूण भरले"],
    "Total Assessed": ["कुल निर्धारित", "एकूण आकारले"],
    "Amount": ["राशि", "रक्कम"],
    "Amount (₹) *": ["राशि (₹) *", "रक्कम (₹) *"],
    "Balance": ["शेष", "शिल्लक"],
    "Outstanding": ["बकाया", "थकीत"],
    "Due Date": ["देय तिथि", "देय तारीख"],
    "Billing Year": ["बिलिंग वर्ष", "बिलिंग वर्ष"],
    "Select Payment Method": ["भुगतान विधि चुनें", "भरणा पद्धत निवडा"],
    "UPI (Google Pay / PhonePe / BHIM)": ["UPI (गूगल पे / फोनपे / BHIM)", "UPI (गूगल पे / फोनपे / BHIM)"],
    "Net Banking (SBI / BOM / HDFC)": ["नेट बैंकिंग (SBI / BOM / HDFC)", "नेट बँकिंग (SBI / BOM / HDFC)"],
    "Scan with any UPI app": ["किसी भी UPI ऐप से स्कैन करें", "कोणत्याही UPI ॲपने स्कॅन करा"],
    "Open GPay / PhonePe / BHIM and scan to pay. Then tap \"I've Paid\" to verify.": ["GPay / PhonePe / BHIM खोलें और भुगतान के लिए स्कैन करें। फिर सत्यापन के लिए \"मैंने भुगतान किया\" पर टैप करें।", "GPay / PhonePe / BHIM उघडा आणि भरण्यासाठी स्कॅन करा. नंतर पडताळणीसाठी \"मी भरले\" वर टॅप करा."],
    "OFFICIAL e-TAX RECEIPT": ["आधिकारिक ई-कर रसीद", "अधिकृत ई-कर पावती"],
    "Receipt No:": ["रसीद क्रमांक:", "पावती क्रमांक:"],
    "Taxpayer:": ["करदाता:", "करदाता:"],
    "Property:": ["संपत्ति:", "मालमत्ता:"],
    "Property: House No. 142, Ward 3": ["संपत्ति: मकान नंबर 142, वार्ड 3", "मालमत्ता: घर क्रमांक १४२, प्रभाग ३"],
    "Office: 0217-260-0142": ["कार्यालय: 0217-260-0142", "कार्यालय: ०२१७-२६०-०१४२"],

    /* ---- Finance / admin ---- */
    "Financial Ledger - Income & Expenditure": ["वित्तीय बहीखाता - आय एवं व्यय", "आर्थिक खतावणी - उत्पन्न व खर्च"],
    "Record village income and expenditure, verify entries, and export the ledger for audits.": ["ग्राम आय एवं व्यय रिकॉर्ड करें, प्रविष्टियां सत्यापित करें, और ऑडिट के लिए बहीखाता निर्यात करें।", "गाव उत्पन्न व खर्च नोंदवा, नोंदी पडताळा आणि ऑडिटसाठी खतावणी निर्यात करा."],
    "Income and expenditure are recorded in the village ledger.": ["आय एवं व्यय ग्राम बहीखाते में दर्ज किए जाते हैं।", "उत्पन्न व खर्च गाव खतावणीत नोंदवले जातात."],
    "Income": ["आय", "उत्पन्न"],
    "Expenditure": ["व्यय", "खर्च"],
    "Total Income": ["कुल आय", "एकूण उत्पन्न"],
    "Total Expenditure": ["कुल व्यय", "एकूण खर्च"],
    "Net Balance": ["शुद्ध शेष", "निव्वळ शिल्लक"],
    "Fund Source": ["निधि स्रोत", "निधी स्रोत"],
    "Financial Year": ["वित्तीय वर्ष", "आर्थिक वर्ष"],
    "Budget utilisation": ["बजट उपयोग", "अर्थसंकल्प वापर"],
    "Funds Received": ["प्राप्त निधि", "मिळालेला निधी"],
    "In Progress Works": ["प्रगति पर कार्य", "सुरू असलेली कामे"],
    "Avg resolution": ["औसत निवारण", "सरासरी निवारण"],
    "Received": ["प्राप्त", "प्राप्त"],
    "Received this week": ["इस सप्ताह प्राप्त", "या आठवड्यात प्राप्त"],
    "Received vs resolved (daily)": ["प्राप्त बनाम निवारित (दैनिक)", "प्राप्त विरुद्ध निराकरण (दैनिक)"],
    "Operational Trends": ["परिचालन रुझान", "कार्यात्मक कल"],
    "Total Grievances": ["कुल शिकायतें", "एकूण तक्रारी"],
    "Total Staff": ["कुल कर्मचारी", "एकूण कर्मचारी"],
    "Active Staff": ["सक्रिय कर्मचारी", "सक्रिय कर्मचारी"],
    "0 Active Notices Published": ["0 सक्रिय सूचनाएं प्रकाशित", "० सक्रिय सूचना प्रकाशित"],
    "Grievances matching the current filters": ["वर्तमान फ़िल्टर से मेल खाती शिकायतें", "सध्याच्या फिल्टरशी जुळणाऱ्या तक्रारी"],
    "Audit trail events matching the current filters": ["वर्तमान फ़िल्टर से मेल खाती ऑडिट ट्रेल घटनाएं", "सध्याच्या फिल्टरशी जुळणाऱ्या ऑडिट ट्रेल घटना"],
    "Immutable Administrative Audit Trail": ["अपरिवर्तनीय प्रशासनिक ऑडिट ट्रेल", "अपरिवर्तनीय प्रशासकीय ऑडिट ट्रेल"],
    "All status changes and actions recorded permanently with timestamps (FR-13).": ["सभी स्थिति परिवर्तन एवं कार्रवाइयां समय-चिह्नों के साथ स्थायी रूप से दर्ज की जाती हैं (FR-13)।", "सर्व स्थिती बदल व कृती वेळ-नोंदींसह कायमस्वरूपी नोंदवल्या जातात (FR-13)."],
    "Official Action Trail": ["आधिकारिक कार्रवाई ट्रेल", "अधिकृत कृती ट्रेल"],
    "Read notices only": ["केवल सूचनाएं पढ़ें", "फक्त सूचना वाचा"],
    "View only": ["केवल देखें", "फक्त पहा"],
    "Role permissions": ["भूमिका अनुमतियां", "भूमिका परवानग्या"],
    "What each role can do": ["प्रत्येक भूमिका क्या कर सकती है", "प्रत्येक भूमिका काय करू शकते"],
    "Your permissions": ["आपकी अनुमतियां", "तुमच्या परवानग्या"],
    "View, assign, update, close": ["देखें, सौंपें, अपडेट करें, बंद करें", "पहा, नेमा, अद्ययावत करा, बंद करा"],
    "View, filter & export": ["देखें, फ़िल्टर करें एवं निर्यात करें", "पहा, फिल्टर करा व निर्यात करा"],
    "View & export": ["देखें एवं निर्यात करें", "पहा व निर्यात करा"],
    "Manage every grievance in three parts - Submitted, In Progress, Completed.": ["प्रत्येक शिकायत को तीन भागों में प्रबंधित करें - दर्ज, प्रगति पर, पूर्ण।", "प्रत्येक तक्रार तीन भागांत व्यवस्थापित करा - नोंदणीकृत, काम सुरू, पूर्ण."],
    "Add staff, promote to admin, or deactivate accounts. Role/status changes take effect on the staff member's next login.": ["कर्मचारी जोड़ें, प्रशासक में पदोन्नत करें, या खाते निष्क्रिय करें। भूमिका/स्थिति परिवर्तन कर्मचारी के अगले लॉगिन पर प्रभावी होते हैं।", "कर्मचारी जोडा, प्रशासकात बढती द्या, किंवा खाती निष्क्रिय करा. भूमिका/स्थिती बदल कर्मचाऱ्याच्या पुढील लॉगिनला लागू होतात."],
    "Live Excel record of every villager account (name, mobile, village/ward, last login). Updates automatically as citizens register or sign in.": ["प्रत्येक ग्रामीण खाते का लाइव Excel रिकॉर्ड (नाम, मोबाइल, गांव/वार्ड, अंतिम लॉगिन)। नागरिक पंजीकरण या साइन इन करते ही स्वतः अपडेट होता है।", "प्रत्येक ग्रामस्थ खात्याची थेट Excel नोंद (नाव, मोबाइल, गाव/प्रभाग, शेवटचे लॉगिन). नागरिक नोंदणी किंवा साइन इन करताच स्वतः अद्ययावत होते."],
    "Citizen Login Accounts": ["नागरिक लॉगिन खाते", "नागरिक लॉगिन खाती"],
    "Elected representatives and administrative officers serving Kumbhari village.": ["कुंभारी गांव की सेवा करने वाले निर्वाचित प्रतिनिधि एवं प्रशासनिक अधिकारी।", "कुंभारी गावाची सेवा करणारे निर्वाचित प्रतिनिधी व प्रशासकीय अधिकारी."],
    "Assign Officer *": ["अधिकारी नियुक्त करें *", "अधिकारी नेमा *"],
    "Official Resolution Remark *": ["आधिकारिक निवारण टिप्पणी *", "अधिकृत निराकरण शेरा *"],
    "Write update remarks for citizen...": ["नागरिक के लिए अपडेट टिप्पणी लिखें...", "नागरिकासाठी अद्ययावत शेरा लिहा..."],
    "Explain the issue clearly...": ["समस्या स्पष्ट रूप से बताएं...", "समस्या स्पष्टपणे सांगा..."],
    "Audited Under eGramSwaraj": ["ई-ग्राम स्वराज के अंतर्गत ऑडिट", "ई-ग्राम स्वराज अंतर्गत ऑडिट"],
    "Live from backend": ["बैकएंड से लाइव", "बॅकएंडवरून थेट"],
    "Live Portal Active": ["लाइव पोर्टल सक्रिय", "थेट पोर्टल सक्रिय"],

    /* ---- Auth ---- */
    "Register & Open Dashboard": ["पंजीकरण करें एवं डैशबोर्ड खोलें", "नोंदणी करा व डॅशबोर्ड उघडा"],
    "Enter your current password and set a new one.": ["अपना वर्तमान पासवर्ड डालें और नया पासवर्ड सेट करें।", "तुमचा सध्याचा पासवर्ड टाका आणि नवीन पासवर्ड सेट करा."],

    /* ---- Common attribute strings ---- */
    "Account menu": ["खाता मेनू", "खाते मेनू"],
    "Audit from date": ["ऑडिट प्रारंभ तिथि", "ऑडिट प्रारंभ तारीख"],
    "Audit to date": ["ऑडिट अंतिम तिथि", "ऑडिट अंत तारीख"],
    "Browse all schemes": ["सभी योजनाएं देखें", "सर्व योजना पहा"],
    "Change my password": ["मेरा पासवर्ड बदलें", "माझा पासवर्ड बदला"],
    "Clear audit filters": ["ऑडिट फ़िल्टर साफ़ करें", "ऑडिट फिल्टर साफ करा"],
    "Clear all filters": ["सभी फ़िल्टर साफ़ करें", "सर्व फिल्टर साफ करा"],
    "Clear filters": ["फ़िल्टर साफ़ करें", "फिल्टर साफ करा"],
    "Export audit trail as CSV": ["ऑडिट ट्रेल CSV के रूप में निर्यात करें", "ऑडिट ट्रेल CSV म्हणून निर्यात करा"],
    "Filed from date": ["दर्ज प्रारंभ तिथि", "नोंद प्रारंभ तारीख"],
    "Filed to date": ["दर्ज अंतिम तिथि", "नोंद अंत तारीख"],
    "Filter audit trail": ["ऑडिट ट्रेल फ़िल्टर करें", "ऑडिट ट्रेल फिल्टर करा"],
    "Filter by action": ["कार्रवाई अनुसार फ़िल्टर करें", "कृतीनुसार फिल्टर करा"],
    "Filter by actor": ["कर्ता अनुसार फ़िल्टर करें", "कर्त्यानुसार फिल्टर करा"],
    "Filter by category": ["श्रेणी अनुसार फ़िल्टर करें", "श्रेणीनुसार फिल्टर करा"],
    "Filter by status": ["स्थिति अनुसार फ़िल्टर करें", "स्थितीनुसार फिल्टर करा"],
    "Filter grievances": ["शिकायतें फ़िल्टर करें", "तक्रारी फिल्टर करा"],
    "Next page": ["अगला पृष्ठ", "पुढील पृष्ठ"],
    "Notifications from Panchayat Desk": ["पंचायत डेस्क से सूचनाएं", "पंचायत डेस्ककडून सूचना"],
    "Messages from Panchayat Desk": ["पंचायत डेस्क से संदेश", "पंचायत डेस्ककडून संदेश"],
    "Open navigation menu": ["नेविगेशन मेनू खोलें", "नेव्हिगेशन मेनू उघडा"],
    "Previous page": ["पिछला पृष्ठ", "मागील पृष्ठ"],
    "Print audit trail": ["ऑडिट ट्रेल प्रिंट करें", "ऑडिट ट्रेल प्रिंट करा"],
    "Refresh data": ["डेटा ताज़ा करें", "डेटा रिफ्रेश करा"],
    "Refresh all desk data now": ["सभी डेस्क डेटा अभी ताज़ा करें", "सर्व डेस्क डेटा आता रिफ्रेश करा"],
    "Rows per page": ["प्रति पृष्ठ पंक्तियां", "प्रति पृष्ठ ओळी"],
    "Search audit trail": ["ऑडिट ट्रेल खोजें", "ऑडिट ट्रेल शोधा"],
    "Search grievances": ["शिकायतें खोजें", "तक्रारी शोधा"],
    "Sign out": ["साइन आउट", "साइन आउट"],
    "Sort direction": ["क्रम दिशा", "क्रम दिशा"],
    "Sort grievances": ["शिकायतें क्रमबद्ध करें", "तक्रारी क्रमवारी लावा"],
    "Decrease Font": ["फ़ॉन्ट घटाएं", "फॉन्ट कमी करा"],
    "Increase Font": ["फ़ॉन्ट बढ़ाएं", "फॉन्ट वाढवा"],
    "Reset Font": ["फ़ॉन्ट रीसेट करें", "फॉन्ट रीसेट करा"],
    "Live time - Indian Standard Time (GMT+5:30)": ["लाइव समय - भारतीय मानक समय (GMT+5:30)", "थेट वेळ - भारतीय प्रमाणवेळ (GMT+5:30)"],
    "Live weather - Kumbhari, Kopargaon (Open-Meteo)": ["लाइव मौसम - कुंभारी, कोपरगाव (Open-Meteo)", "थेट हवामान - कुंभारी, कोपरगाव (Open-Meteo)"],
    "Manage village income & expenditure": ["ग्राम आय एवं व्यय प्रबंधित करें", "गाव उत्पन्न व खर्च व्यवस्थापित करा"],
    "Outdoor Sunlight Mode": ["बाहरी धूप मोड", "बाहेरील ऊन मोड"],
    "Download visible audit rows as CSV": ["दिखाई देने वाली ऑडिट पंक्तियां CSV में डाउनलोड करें", "दिसणाऱ्या ऑडिट ओळी CSV मध्ये डाउनलोड करा"],
    "10-digit mobile number": ["10 अंकों का मोबाइल नंबर", "१० अंकी मोबाइल क्रमांक"],
    "Action, reference or actor…": ["कार्रवाई, संदर्भ या कर्ता…", "कृती, संदर्भ किंवा कर्ता…"],
    "Create a password": ["पासवर्ड बनाएं", "पासवर्ड तयार करा"],
    "Enter officer name": ["अधिकारी का नाम दर्ज करें", "अधिकाऱ्याचे नाव टाका"],
    "Enter staff full name": ["कर्मचारी का पूरा नाम दर्ज करें", "कर्मचाऱ्याचे पूर्ण नाव टाका"],
    "Full name as per Aadhaar": ["आधार अनुसार पूरा नाम", "आधारनुसार पूर्ण नाव"],
    "Full official notice text...": ["पूर्ण आधिकारिक सूचना पाठ...", "पूर्ण अधिकृत सूचना मजकूर..."],
    "Full or partial user id": ["पूर्ण या आंशिक उपयोगकर्ता आईडी", "पूर्ण किंवा अर्धा वापरकर्ता आयडी"],
    "Minimum 6 characters": ["कम से कम 6 अक्षर", "किमान ६ अक्षरे"],
    "Repeat the new password": ["नया पासवर्ड दोहराएं", "नवीन पासवर्ड पुन्हा टाका"],
    "Search ID, subject, applicant…": ["आईडी, विषय, आवेदक खोजें…", "आयडी, विषय, अर्जदार शोधा…"],
    "Search description / reference / fund…": ["विवरण / संदर्भ / निधि खोजें…", "वर्णन / संदर्भ / निधी शोधा…"],
    "Street / locality": ["गली / इलाका", "गल्ली / परिसर"],
    "What was this income / expenditure for?": ["यह आय / व्यय किस लिए था?", "हे उत्पन्न / खर्च कशासाठी होते?"],
    "Your existing password": ["आपका वर्तमान पासवर्ड", "तुमचा सध्याचा पासवर्ड"],
    "Your password": ["आपका पासवर्ड", "तुमचा पासवर्ड"],
    "e.g. Broken water tap near temple": ["जैसे मंदिर के पास टूटा नल", "उदा. मंदिराजवळ तुटलेला नळ"],
    "e.g. Drainage, Water Supply": ["जैसे जल निकासी, जल आपूर्ति", "उदा. गटार, पाणीपुरवठा"],
    "e.g. In front of Hanuman Mandir, Pole #12": ["जैसे हनुमान मंदिर के सामने, खंभा #12", "उदा. हनुमान मंदिरासमोर, खांब #१२"],
    "e.g. Water Supply Schedule for Ward 3": ["जैसे वार्ड 3 के लिए जल आपूर्ति कार्यक्रम", "उदा. प्रभाग ३ साठी पाणीपुरवठा वेळापत्रक"],
    "auto if blank": ["खाली होने पर स्वतः", "रिकामे असल्यास स्वतः"],
    "Select village…": ["गांव चुनें…", "गाव निवडा…"],
    "Select ward…": ["वार्ड चुनें…", "प्रभाग निवडा…"],
    "e.g. 15th Finance Commission": ["जैसे 15वां वित्त आयोग", "उदा. १५वा वित्त आयोग"]
  };

  /* ---- engine state ---- */
  var lang = 'en';
  var textOriginals = new WeakMap();   // textNode -> english string
  var attrOriginals = new WeakMap();   // element  -> { attr: english }
  var applying = false;
  var observer = null;
  var initialTitle = (typeof document !== 'undefined') ? document.title : '';
  var SKIP = { SCRIPT: 1, STYLE: 1, NOSCRIPT: 1, TEXTAREA: 1 };

  function norm(s) { return String(s).replace(/\s+/g, ' ').trim(); }

  function translate(english) {
    var pair = DICT[english];
    if (!pair) return null;
    if (lang === 'hi') return pair[0];
    if (lang === 'mr') return pair[1];
    return english;
  }

  function handleText(node) {
    var cur = node.nodeValue;
    if (!cur) return;
    var core = norm(cur);
    if (!core) return;

    var english = textOriginals.get(node);
    if (english === undefined) {
      if (!DICT[core]) return;           // not a known phrase; leave untouched
      textOriginals.set(node, cur);
      english = cur;
    }
    var out = (lang === 'en') ? english : (translate(norm(english)) || english);
    if (out !== cur) node.nodeValue = out;
  }

  function handleAttr(el) {
    for (var i = 0; i < ATTRS.length; i++) {
      var name = ATTRS[i];
      var val = el.getAttribute(name);
      if (!val) continue;
      var store = attrOriginals.get(el);
      if (!store) { store = {}; attrOriginals.set(el, store); }
      if (store[name] === undefined) {
        if (!DICT[norm(val)]) continue;  // unknown: leave alone
        store[name] = val;
      }
      var english = store[name];
      var out = (lang === 'en') ? english : (translate(norm(english)) || english);
      if (out !== el.getAttribute(name)) el.setAttribute(name, out);
    }
  }

  function walk(root) {
    if (!root) return;
    if (root.nodeType === 3) { handleText(root); return; }
    if (root.nodeType !== 1 || SKIP[root.nodeName]) return;

    if (root.hasAttribute && (root.hasAttribute('placeholder') || root.hasAttribute('title') || root.hasAttribute('aria-label'))) {
      handleAttr(root);
    }
    var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode: function (n) {
        var p = n.parentNode;
        if (!p || SKIP[p.nodeName]) return NodeFilter.FILTER_REJECT;
        return NodeFilter.FILTER_ACCEPT;
      }
    });
    var n;
    while ((n = walker.nextNode())) handleText(n);

    var els = root.querySelectorAll('[placeholder],[title],[aria-label]');
    for (var i = 0; i < els.length; i++) handleAttr(els[i]);
  }

  var ATTR_FILTER = ['placeholder', 'title', 'aria-label'];

  function startObserver() {
    if (observer || typeof MutationObserver === 'undefined' || !document.body) return;
    observer = new MutationObserver(function (muts) {
      if (applying) return;
      applying = true;
      try {
        for (var i = 0; i < muts.length; i++) {
          var m = muts[i];
          if (m.type === 'childList') {
            for (var j = 0; j < m.addedNodes.length; j++) walk(m.addedNodes[j]);
          } else if (m.type === 'characterData') {
            handleText(m.target);
          } else if (m.type === 'attributes') {
            handleAttr(m.target);
          }
        }
      } finally {
        applying = false;
      }
    });
    observer.observe(document.body, {
      childList: true, subtree: true, characterData: true,
      attributes: true, attributeFilter: ATTR_FILTER
    });
  }

  function apply(next) {
    lang = (next === 'hi' || next === 'mr') ? next : 'en';
    try { localStorage.setItem(STORAGE_KEY, lang); } catch (e) {}
    document.documentElement.setAttribute('lang', lang);
    if (document.body) walk(document.body);
    if (initialTitle) {
      var tkey = norm(initialTitle);
      document.title = (lang === 'en') ? initialTitle : (translate(tkey) || initialTitle);
    }
    var sel = document.getElementById('lang-selector');
    if (sel && sel.value !== lang) sel.value = lang;
  }

  function t(english) {
    if (lang === 'en') return english;
    return translate(norm(english)) || english;
  }

  function init() {
    var saved = 'en';
    try { saved = localStorage.getItem(STORAGE_KEY) || 'en'; } catch (e) {}
    apply(saved);
    startObserver();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  window.GramSetuI18N = { apply: apply, get: function () { return lang; }, t: t, dict: DICT };
})();
