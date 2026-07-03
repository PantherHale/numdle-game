const STATE = window.GAME_STATE;

// ── Date display ──
document.getElementById('todays-date').textContent =
  new Date().toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });

// ── Group toggles ──
document.querySelectorAll('.group-toggle').forEach(btn => {
  btn.addEventListener('click', () => {
    const idx = btn.dataset.group;
    const panel = document.getElementById('group-' + idx);
    const open = panel.style.display !== 'none';
    panel.style.display = open ? 'none' : 'flex';
    btn.classList.toggle('open', !open);
  });
});

// ── Ask a question ──
document.querySelectorAll('.q-btn').forEach(btn => {
  btn.addEventListener('click', async () => {
    if (STATE.questionsLeft <= 0 || STATE.gameOver) return;

    const id = parseInt(btn.dataset.id);
    btn.disabled = true;

    const res = await fetch('/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id }),
    });

    if (!res.ok) {
      btn.disabled = false;
      const err = await res.json();
      showError(err.error || 'Error asking question');
      return;
    }

    const data = await res.json();
    STATE.questionsLeft = data.questions_left;
    document.getElementById('questions-left').textContent = STATE.questionsLeft;

    btn.classList.add('just-asked');

    addQARow(btn.textContent.trim(), data.answer);

    if (STATE.questionsLeft === 0) {
      document.getElementById('question-picker').style.display = 'none';
      showInfo('All questions used — submit your guess!');
    }
  });
});

function addQARow(question, answer) {
  const list = document.getElementById('qa-list');

  // Remove placeholder hint if present
  const hint = list.querySelector('.hint');
  if (hint) hint.remove();

  const row = document.createElement('div');
  row.className = 'qa-row slide-in';
  row.innerHTML = `<span class="qa-q">${escHtml(question)}</span><span class="qa-a">${escHtml(answer)}</span>`;
  list.appendChild(row);
}

// ── Submit guess ──
document.getElementById('guess-btn')?.addEventListener('click', submitGuess);
document.getElementById('guess-input')?.addEventListener('keydown', e => {
  if (e.key === 'Enter') submitGuess();
});

async function submitGuess() {
  if (STATE.gameOver) return;

  const input = document.getElementById('guess-input');
  const val = parseInt(input.value);

  if (isNaN(val) || val < 1 || val > 1000) {
    showError('Enter a number between 1 and 1000');
    return;
  }

  const asked = document.querySelectorAll('.qa-row').length;
  if (asked === 0) {
    showError('Ask at least one question first');
    return;
  }

  document.getElementById('guess-btn').disabled = true;
  showError('');

  const res = await fetch('/guess', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ guess: val }),
  });

  if (!res.ok) {
    const err = await res.json();
    showError(err.error || 'Error submitting guess');
    document.getElementById('guess-btn').disabled = false;
    return;
  }

  const data = await res.json();
  STATE.gameOver = true;
  showResults(data);
}

function showResults(data) {
  // Hide input section
  document.getElementById('question-picker')?.remove();
  document.getElementById('guess-section')?.remove();

  const resultsEl = document.getElementById('results');
  resultsEl.style.display = 'flex';
  resultsEl.classList.add('pop');

  // Reveal number
  document.getElementById('reveal-number').textContent = data.secret;

  // Human card
  const humanCard = document.getElementById('human-card');
  document.getElementById('human-guess-display').textContent = data.human_guess;
  humanCard.querySelector('.score-distance').innerHTML =
    `Off by <strong>${data.human_distance}</strong>`;

  // AI card
  const aiCard = document.getElementById('ai-card');
  document.getElementById('ai-guess-display').textContent = data.ai_guess;
  aiCard.querySelector('.score-distance').innerHTML =
    `Off by <strong>${data.ai_distance}</strong>`;

  // Apply outcome classes and badges
  const { outcome } = data;
  if (outcome === 'win') {
    humanCard.classList.add('winner');
    aiCard.classList.add('loser');
    setBadge(humanCard, '🏆 Winner');
    setBadge(aiCard, '😔 Lost');
  } else if (outcome === 'lose') {
    humanCard.classList.add('loser');
    aiCard.classList.add('winner');
    setBadge(humanCard, '😔 Lost');
    setBadge(aiCard, '🏆 Winner');
  } else {
    humanCard.classList.add('tie');
    aiCard.classList.add('tie');
    setBadge(humanCard, '🤝 Tie');
    setBadge(aiCard, '🤝 Tie');
  }

  // AI walkthrough
  const walkthroughEl = resultsEl.querySelector('.ai-walkthrough');
  if (walkthroughEl && data.ai_questions) {
    const listEl = walkthroughEl.querySelector('.qa-list-sm');
    listEl.innerHTML = '';
    data.ai_questions.forEach(({ question, answer }) => {
      const row = document.createElement('div');
      row.className = 'qa-row-sm';
      row.innerHTML = `<span class="qa-q-sm">${escHtml(question)}</span><span class="qa-a-sm">${escHtml(answer)}</span>`;
      listEl.appendChild(row);
    });
  }

  // Tomorrow note
  if (!resultsEl.querySelector('.tomorrow-note')) {
    const note = document.createElement('div');
    note.className = 'tomorrow-note';
    note.textContent = 'Come back tomorrow for a new number!';
    resultsEl.appendChild(note);
  }

  resultsEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function setBadge(card, text) {
  let badge = card.querySelector('.score-badge');
  if (!badge) {
    badge = document.createElement('div');
    badge.className = 'score-badge';
    card.appendChild(badge);
  }
  badge.textContent = text;
}

function showError(msg) {
  const el = document.getElementById('error-msg');
  if (el) el.textContent = msg;
}

function showInfo(msg) {
  const el = document.getElementById('error-msg');
  if (el) { el.textContent = msg; el.style.color = 'var(--accent)'; }
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
