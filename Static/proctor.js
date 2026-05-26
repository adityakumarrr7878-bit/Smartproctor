(function () {
  if (!document.getElementById('exam-container')) return;

  var examData = JSON.parse(document.getElementById('exam-data').textContent);
  var roll     = document.getElementById('roll-data').textContent.trim();
  var examId   = examData.id;

  var video   = document.getElementById('proctor-video');
  var canvas  = document.createElement('canvas');
  canvas.width  = 320;
  canvas.height = 240;
  var ctx     = canvas.getContext('2d');
  var stream  = null;
  var checking = false;

  /* ── Local violation counts (for display) ─────────────── */
  var violationCounts = { no_face: 0, multi_face: 0, object_detected: 0, tab_switch: 0 };

  /* ── Build the popup modal DOM ────────────────────────── */
  var overlay = document.createElement('div');
  overlay.style.cssText =
    'display:none;position:fixed;top:0;left:0;width:100%;height:100%;' +
    'background:rgba(0,0,0,0.82);z-index:99999;' +
    'align-items:center;justify-content:center;';

  var box = document.createElement('div');
  box.style.cssText =
    'background:#16102a;border:2px solid #f75c5c;border-radius:16px;' +
    'padding:36px 44px;text-align:center;max-width:400px;width:90%;' +
    'box-shadow:0 0 48px rgba(247,92,92,0.35);font-family:Sora,Arial,sans-serif;';

  var bIcon  = document.createElement('div');
  bIcon.style.cssText = 'font-size:3rem;margin-bottom:12px;';

  var bTitle = document.createElement('div');
  bTitle.style.cssText = 'font-size:1.25rem;font-weight:700;color:#f75c5c;margin-bottom:10px;';

  var bMsg = document.createElement('div');
  bMsg.style.cssText = 'font-size:.9rem;color:#9ca3c0;line-height:1.65;margin-bottom:24px;';

  var bBtn = document.createElement('button');
  bBtn.style.cssText =
    'background:#f75c5c;color:#fff;border:none;padding:11px 28px;' +
    'border-radius:8px;font-size:.95rem;font-weight:600;cursor:pointer;' +
    'font-family:Sora,Arial,sans-serif;';
  bBtn.textContent = 'I Understand';
  bBtn.onclick = function () { overlay.style.display = 'none'; };

  box.appendChild(bIcon);
  box.appendChild(bTitle);
  box.appendChild(bMsg);
  box.appendChild(bBtn);
  overlay.appendChild(box);
  document.body.appendChild(overlay);

  var INFO = {
    no_face: {
      icon:  '👤',
      title: 'Face Not Detected!',
      msg:   'Your face is not visible to the camera. Please ensure your face is clearly in frame. This violation has been recorded.'
    },
    multi_face: {
      icon:  '👥',
      title: 'Multiple Faces Detected!',
      msg:   'More than one face is visible. Only you should be in front of the camera. This violation has been recorded.'
    },
    object_detected: {
      icon:  '📱',
      title: 'Restricted Object Detected!',
      msg:   'A prohibited item (phone, book, or laptop) was detected in frame. Remove it immediately. This violation has been recorded.'
    },
    tab_switch: {
      icon:  '🚫',
      title: 'Tab Switch Detected!',
      msg:   'You left the exam window. Your exam is being submitted automatically with your current answers.'
    }
  };

  function showPopup(type, onConfirm) {
    var info = INFO[type] || { icon: '⚠️', title: 'Violation Detected!', msg: 'A violation has been recorded.' };
    bIcon.textContent  = info.icon;
    bTitle.textContent = info.title;
    bMsg.textContent   = info.msg;

    if (onConfirm) {
      bBtn.textContent = 'Submit Exam Now';
      bBtn.onclick = function () {
        overlay.style.display = 'none';
        onConfirm();
      };
    } else {
      bBtn.textContent = 'I Understand';
      bBtn.onclick = function () { overlay.style.display = 'none'; };
    }

    /* Show as flex so it centres correctly */
    overlay.style.display = 'flex';
  }

  /* ── Update the small violation counter bar on exam page ─ */
  function updateCounterBar() {
    var bar = document.getElementById('live-violation-counts');
    if (!bar) return;
    var parts = [];
    if (violationCounts.no_face        > 0) parts.push('👤 No Face: '      + violationCounts.no_face);
    if (violationCounts.multi_face     > 0) parts.push('👥 Multi-Face: '   + violationCounts.multi_face);
    if (violationCounts.object_detected > 0) parts.push('📱 Object: '      + violationCounts.object_detected);
    if (violationCounts.tab_switch     > 0) parts.push('🔀 Tab Switch: '   + violationCounts.tab_switch);
    bar.textContent = parts.length > 0 ? ('Violations — ' + parts.join('  |  ')) : '';
    bar.style.display = parts.length > 0 ? 'block' : 'none';
  }

  /* ── Camera start ─────────────────────────────────────── */
  navigator.mediaDevices.getUserMedia({ video: true, audio: false })
    .then(function (s) {
      stream = s;
      video.srcObject = s;
      video.play();
      setInterval(captureAndCheck, 3000);
    })
    .catch(function () {
      console.warn('Camera not accessible — proctoring disabled.');
    });

  /* ── Capture frame → send to backend → handle result ─── */
  function captureAndCheck() {
    if (checking || !stream || window.examSubmitted) return;
    checking = true;

    ctx.drawImage(video, 0, 0, 160, 120);
    var dataUrl = canvas.toDataURL('image/jpeg', 0.85);

    fetch('/proctor/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ image: dataUrl, exam_id: examId, roll_number: roll })
    })
    .then(function (r) { return r.json(); })
    .then(function (res) {
      checking = false;
      if (!res.violation || window.examSubmitted) return;

      var type = res.violation_type;

      /* Increment local counter */
      violationCounts[type] = (violationCounts[type] || 0) + 1;
      updateCounterBar();

      /* Show popup */
      showPopup(type, null);

      /* Also show the small top banner */
      if (window.reportViolation) window.reportViolation(type);
    })
    .catch(function () { checking = false; });
  }

  /* ── Tab switch → log to DB → show popup → auto-submit ── */
  document.addEventListener('visibilitychange', function () {
    if (!document.hidden || window.examSubmitted) return;

    /* Count it locally */
    violationCounts.tab_switch = (violationCounts.tab_switch || 0) + 1;
    updateCounterBar();

    /* Log to DB */
    fetch('/proctor/log_violation', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ exam_id: examId, roll_number: roll, violation_type: 'tab_switch' })
    }).catch(function () {});

    /* Save current answers */
    if (window.getCurrentAnswers) window.getCurrentAnswers();

    /* Show popup — clicking submits */
    showPopup('tab_switch', function () {
      if (window.doSubmit) window.doSubmit();
    });

    /* Auto-submit after 5 s even if they don't click */
    setTimeout(function () {
      if (!window.examSubmitted && window.doSubmit) {
        overlay.style.display = 'none';
        window.doSubmit();
      }
    }, 5000);
  });

})();
