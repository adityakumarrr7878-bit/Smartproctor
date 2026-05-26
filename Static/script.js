/* ── Arrow key navigation in create exam ─────────────────── */
document.addEventListener('keydown', function (e) {
  if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp') return;
  var els = Array.from(document.querySelectorAll('input,textarea,select,button'))
    .filter(function (el) { return !el.disabled && el.offsetParent !== null; });
  var i = els.indexOf(document.activeElement);
  if (i === -1) return;
  e.preventDefault();
  var next = e.key === 'ArrowDown' ? els[i + 1] : els[i - 1];
  if (next) next.focus();
});

/* ── Question builder ─────────────────────────────────────── */
var questionCount = 0;
function addQuestion() {
  questionCount++;
  var container = document.getElementById('questions-container');
  if (!container) return;
  var block = document.createElement('div');
  block.className = 'question-block';
  block.innerHTML =
    '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px;flex-wrap:wrap;gap:10px">' +
      '<h4 style="font-size:.82rem;text-transform:uppercase;letter-spacing:.5px;color:var(--accent);font-weight:600;margin:0">Question ' + questionCount + '</h4>' +
      '<div class="type-toggle">' +
        '<button type="button" class="type-btn active" onclick="setType(this,\'mcq\')">MCQ</button>' +
        '<button type="button" class="type-btn" onclick="setType(this,\'short_answer\')">Short Answer</button>' +
        '<button type="button" class="type-btn" onclick="setType(this,\'long_answer\')">Long Answer</button>' +
      '</div>' +
    '</div>' +
    '<input type="hidden" name="question_type[]" class="q-type-input" value="mcq">' +
    '<div class="form-group"><label>Question Text</label><textarea name="question[]" rows="2" required placeholder="Enter question..."></textarea></div>' +
    '<div class="mcq-fields">' +
      '<div class="options-grid">' +
        '<div class="form-group"><label>Option A</label><input type="text" name="option_a[]" placeholder="Option A"></div>' +
        '<div class="form-group"><label>Option B</label><input type="text" name="option_b[]" placeholder="Option B"></div>' +
        '<div class="form-group"><label>Option C</label><input type="text" name="option_c[]" placeholder="Option C"></div>' +
        '<div class="form-group"><label>Option D</label><input type="text" name="option_d[]" placeholder="Option D"></div>' +
      '</div>' +
      '<div class="form-group"><label>Correct Answer</label><select name="correct[]"><option value="">-- Select --</option><option value="A">A</option><option value="B">B</option><option value="C">C</option><option value="D">D</option></select></div>' +
    '</div>' +
    '<div class="subj-fields" style="display:none">' +
      '<div class="subj-note short-note">✏ <strong>Short Answer</strong> — candidate types a brief answer.</div>' +
      '<div class="subj-note long-note" style="display:none">📝 <strong>Long Answer</strong> — candidate types a detailed answer.</div>' +
    '</div>';
  container.appendChild(block);
  block.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function setType(btn, type) {
  var block = btn.closest('.question-block');
  block.querySelectorAll('.type-btn').forEach(function (b) { b.classList.remove('active'); });
  btn.classList.add('active');
  block.querySelector('.q-type-input').value = type;
  block.querySelector('.mcq-fields').style.display  = type === 'mcq' ? 'block' : 'none';
  block.querySelector('.subj-fields').style.display = type !== 'mcq' ? 'block' : 'none';
  block.querySelector('.short-note').style.display  = type === 'short_answer' ? 'block' : 'none';
  block.querySelector('.long-note').style.display   = type === 'long_answer'  ? 'block' : 'none';
}

/* ══════════════════════════════════════════════════════════
   EXAM PAGE
══════════════════════════════════════════════════════════ */
(function () {
  if (!document.getElementById('exam-container')) return;

  var examData  = JSON.parse(document.getElementById('exam-data').textContent);
  var questions = JSON.parse(document.getElementById('questions-data').textContent);
  var roll      = document.getElementById('roll-data').textContent.trim();
  var duration  = examData.duration * 60;

  var answers  = {};
  var timeLeft = duration;
  window.examSubmitted = false;

  /* Build nav list: MCQ → Short → Long */
  var mcqQs   = questions.filter(function (q) { return q.question_type === 'mcq'; });
  var shortQs = questions.filter(function (q) { return q.question_type === 'short_answer'; });
  var longQs  = questions.filter(function (q) { return q.question_type === 'long_answer'; });
  var navList = [];
  mcqQs.forEach(function (q, i)   { navList.push({ q: q, section: 'mcq',   idx: i, total: mcqQs.length }); });
  shortQs.forEach(function (q, i) { navList.push({ q: q, section: 'short', idx: i, total: shortQs.length }); });
  longQs.forEach(function (q, i)  { navList.push({ q: q, section: 'long',  idx: i, total: longQs.length }); });
  var current = 0;

  /* Timer */
  var timerEl = document.getElementById('timer');
  var timerInterval = setInterval(function () {
    if (window.examSubmitted) return;
    timeLeft--;
    timerEl.textContent = pad(Math.floor(timeLeft / 60)) + ':' + pad(timeLeft % 60);
    if (timeLeft <= 60) timerEl.classList.add('warning');
    if (timeLeft <= 0)  doSubmit();
  }, 1000);
  function pad(n) { return String(n).padStart(2, '0'); }

  /* Render question */
  function render(navIdx) {
    var entry = navList[navIdx];
    var q = entry.q;
    var labels = { mcq: 'Section A — Multiple Choice', short: 'Section B — Short Answer', long: 'Section C — Long Answer' };
    document.getElementById('section-label').textContent   = labels[entry.section];
    document.getElementById('q-counter').textContent       = 'Question ' + (entry.idx + 1) + ' of ' + entry.total;
    document.getElementById('overall-counter').textContent = (navIdx + 1) + ' / ' + navList.length + ' total';
    document.getElementById('q-text').textContent          = q.question_text;

    document.getElementById('mcq-section').style.display   = 'none';
    document.getElementById('short-section').style.display = 'none';
    document.getElementById('long-section').style.display  = 'none';

    var badge = document.getElementById('q-type-badge');
    if (entry.section === 'mcq') {
      document.getElementById('mcq-section').style.display = 'block';
      badge.textContent = '☑ Multiple Choice'; badge.className = 'q-type-badge badge-mcq';
      var keys = ['option_a','option_b','option_c','option_d'];
      ['A','B','C','D'].forEach(function (l, i) {
        var btn = document.getElementById('opt-' + l);
        btn.querySelector('.opt-text').textContent = l + '. ' + (q[keys[i]] || '');
        btn.classList.toggle('selected', answers[q.id] === l);
      });
    } else if (entry.section === 'short') {
      document.getElementById('short-section').style.display = 'block';
      badge.textContent = '✏ Short Answer'; badge.className = 'q-type-badge badge-short';
      document.getElementById('short-answer-input').value = answers[q.id] || '';
    } else {
      document.getElementById('long-section').style.display = 'block';
      badge.textContent = '📝 Long Answer'; badge.className = 'q-type-badge badge-long';
      document.getElementById('long-answer-input').value = answers[q.id] || '';
    }

    document.getElementById('btn-prev').disabled = (navIdx === 0);
    var last = (navIdx === navList.length - 1);
    document.getElementById('btn-next').style.display   = last ? 'none' : 'inline-flex';
    document.getElementById('btn-submit').style.display = last ? 'inline-flex' : 'none';
  }

  function saveCurrent() {
    var entry = navList[current];
    if (!entry) return;
    if (entry.section === 'short') {
      var v = document.getElementById('short-answer-input').value;
      answers[entry.q.id] = v.trim() ? v : '';
    } else if (entry.section === 'long') {
      var v = document.getElementById('long-answer-input').value;
      answers[entry.q.id] = v.trim() ? v : '';
    }
  }

  /* Expose for proctor.js */
  window.getCurrentAnswers = function () { saveCurrent(); return answers; };

  /* MCQ clicks */
  ['A','B','C','D'].forEach(function (l) {
    var btn = document.getElementById('opt-' + l);
    if (btn) btn.addEventListener('click', function () {
      answers[navList[current].q.id] = l;
      render(current);
    });
  });

  /* Nav buttons */
  document.getElementById('btn-next').addEventListener('click', function () { saveCurrent(); if (current < navList.length-1) { current++; render(current); } });
  document.getElementById('btn-prev').addEventListener('click', function () { saveCurrent(); if (current > 0) { current--; render(current); } });
  document.getElementById('btn-submit').addEventListener('click', function () { if (confirm('Submit the exam? This cannot be undone.')) { saveCurrent(); doSubmit(); } });

  /* Single submit function — shared with proctor.js */
  window.doSubmit = function doSubmit() {
    if (window.examSubmitted) return;
    window.examSubmitted = true;
    clearInterval(timerInterval);
    fetch('/exam/' + examData.id + '/submit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ roll_number: roll, answers: answers })
    })
    .then(function (r) { return r.json(); })
    .then(function (d) { window.location.href = '/exam/' + examData.id + '/result?attempted=' + d.attempted; })
    .catch(function () { window.location.href = '/exam/' + examData.id + '/result?attempted=0'; });
  };

  /* Security */
  document.addEventListener('contextmenu', function (e) { e.preventDefault(); });
  document.addEventListener('copy',  function (e) { e.preventDefault(); });
  document.addEventListener('paste', function (e) { e.preventDefault(); });
  document.addEventListener('cut',   function (e) { e.preventDefault(); });

  /* Top banner (called by proctor.js) */
  window.reportViolation = function (type) {
    if (window.examSubmitted) return;
    var msgs = { no_face: '⚠ Face not detected!', multi_face: '⚠ Multiple faces!', object_detected: '⚠ Restricted object detected!', tab_switch: '⚠ Tab switch! Submitting...' };
    var bar = document.getElementById('violation-bar');
    bar.textContent = msgs[type] || '⚠ Violation recorded!';
    bar.style.display = 'block';
    setTimeout(function () { bar.style.display = 'none'; }, 4000);
  };

  if (navList.length > 0) render(0);
  else document.getElementById('q-counter').textContent = 'No questions found.';
})();
