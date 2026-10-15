const content = document.querySelector('#content');
const conceptsEl = document.querySelector('#concepts');
const state = { overview: null, conceptId: null, lesson: null, session: null, answer: '', result: null, review: null, mode: 'recommended', started: Date.now() };
const preferenceKey = 'aesop.foreman.preferences.v1';
let preferences = { minutes: 20, textSize: 'regular', focus: false };
try {
  const saved = JSON.parse(localStorage.getItem(preferenceKey) || '{}');
  if ([5,10,20,30,45].includes(saved.minutes)) preferences.minutes = saved.minutes;
  if (['regular','large'].includes(saved.textSize)) preferences.textSize = saved.textSize;
  if (typeof saved.focus === 'boolean') preferences.focus = saved.focus;
} catch (_) { /* Private browsing may disable storage. */ }
function applyPreferences() {
  document.querySelector('#minutes').value = String(preferences.minutes);
  document.querySelector('#text-size').value = preferences.textSize;
  document.querySelector('#focus').checked = preferences.focus;
  document.body.classList.toggle('large-reading', preferences.textSize === 'large');
  document.body.classList.toggle('quiet', preferences.focus);
  try { localStorage.setItem(preferenceKey, JSON.stringify(preferences)); } catch (_) { /* Settings remain usable for this tab. */ }
}
document.querySelector('#minutes').onchange = async event => { preferences.minutes = Number(event.target.value); applyPreferences(); await refresh().catch(showError); };
document.querySelector('#text-size').onchange = event => { preferences.textSize = event.target.value; applyPreferences(); };
document.querySelector('#focus').onchange = event => { preferences.focus = event.target.checked; applyPreferences(); };
applyPreferences();
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

async function api(path, body) {
  const options = body === undefined ? {} : { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body) };
  const response = await fetch(path, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.message || data.error || `Request failed (${response.status})`);
  return data;
}
function showError(error) {
  document.querySelector('.error')?.remove();
  const el = document.createElement('div'); el.className = 'error'; el.role = 'alert'; el.textContent = error.message || String(error);
  content.prepend(el);
}
function concepts() {
  conceptsEl.innerHTML = state.overview.concepts.map((c, i) => `<button class="concept ${c.id === state.conceptId ? 'active' : ''}" data-concept="${esc(c.id)}"><span class="num">${String(i+1).padStart(2,'0')}</span><span><span class="title">${esc(c.title)}</span><small>${c.lessonComplete ? 'Lesson read' : 'Lesson to read'} · ${c.signals.attempts} attempt${c.signals.attempts === 1 ? '' : 's'}</small></span></button>`).join('');
  conceptsEl.querySelectorAll('[data-concept]').forEach(button => button.onclick = () => select(button.dataset.concept));
}
async function select(cid) {
  try {
    state.conceptId = cid; state.answer = ''; state.result = null; state.review = null; state.mode = 'recommended'; state.started = Date.now();
    await refresh();
  } catch (error) { showError(error); }
}
async function refresh() {
  const cid = encodeURIComponent(state.conceptId);
  [state.overview, state.lesson, state.session] = await Promise.all([
    api('/api/v2/overview'), api(`/api/v2/lesson?conceptId=${cid}`),
    api(`/api/v2/session?conceptId=${cid}&mode=${state.mode}&availableMinutes=${preferences.minutes}`)
  ]);
  if (state.session.draft) state.answer = state.session.draft.firstAnswer;
  concepts(); render();
}
function render() {
  const index = state.overview.concepts.findIndex(c => c.id === state.conceptId) + 1;
  const current = state.overview.concepts[index-1], signals = current.signals;
  const intro = `<div class="section-kicker">CONCEPT ${String(index).padStart(2,'0')} / ${String(state.overview.concepts.length).padStart(2,'0')}</div><h2>${esc(current.title)}</h2><p class="lede">The goal is lasting understanding. The setting is yours to adjust; retrieval and delayed checks remain part of the learning path.</p><div class="signals"><div class="signal"><strong>${signals.attempts}</strong>attempts</div><div class="signal"><strong>${signals.unassistedCorrect}</strong>unassisted candidate matches</div><div class="signal"><strong>${signals.hintAssisted}</strong>hint-assisted attempts</div></div><div class="divider"></div>`;
  if (!state.lesson.completed) {
    content.innerHTML = intro + `<span class="pill">Short lesson</span><h2>${esc(state.lesson.title)}</h2><div class="lesson-body">${esc(state.lesson.body)}</div><p class="sources">Sources: ${state.lesson.sources.map(s=>`<a href="${esc(s.url)}" target="_blank" rel="noopener noreferrer">${esc(s.title)}</a>`).join('')}</p><div class="button-row"><button class="button" id="complete">I've read this lesson →</button></div>`;
    document.querySelector('#complete').onclick = async () => { try { await api('/api/v2/lesson-completions',{conceptId:state.conceptId}); await refresh(); } catch(e){showError(e)} };
    return;
  }
  if (state.result) {
    const r = state.result;
    const status = r.scoreStatus === 'ungraded' ? 'Saved for self review' : r.scoreStatus === 'correct' ? 'Candidate key match' : 'Try another approach';
    content.innerHTML = intro + `<div class="feedback"><h3>${status}</h3><p>${esc(r.nextReason)}</p><p class="muted">${r.assisted ? 'Hint assisted · ' : ''}Development preview · No mastery claim</p></div>` +
      (r.rubric && !state.review ? `<div class="activity-card"><span class="label">SELF REVIEW · ORIGINAL ANSWER</span><pre class="code">${esc(state.answer)}</pre><p class="muted">For each criterion, quote the part of your first answer that supports a shown or partial rating.</p>${r.rubric.criteria.map(c=>`<div class="review-row" data-criterion="${esc(c.id)}"><p><strong>${esc(c.description)}</strong></p><select class="answer rating"><option value="unsure">Unsure</option><option value="shown">Shown</option><option value="partial">Partial</option><option value="not_shown">Not shown</option></select><input class="answer evidence" placeholder="Exact quote from your answer, if shown or partial" aria-label="Evidence for ${esc(c.description)}"></div>`).join('')}<div class="button-row"><button class="button" id="review">Save self review →</button></div></div>` : '') +
      (state.review ? `<div class="activity-card"><span class="label">COMPARE AND REVISE</span><p>${esc(state.review.nextStep.replace('_',' '))}</p><pre class="code">${esc(state.review.comparison.annotatedExample)}</pre><p class="muted">Common mistakes: ${esc(state.review.comparison.commonMistakes.join(' · '))}</p><label class="muted" for="revision">A revised answer, if you want to try again</label><textarea id="revision" class="answer long"></textarea><div class="button-row"><button class="button secondary" id="save-revision">Save revision</button></div></div>` : '') +
      `<div class="button-row"><button class="button" id="next">Continue →</button><button class="button secondary" id="more">More practice</button></div>`;
    if (r.rubric && !state.review) document.querySelector('#review').onclick = async () => {
      try {
        const judgments = [...document.querySelectorAll('.review-row')].map(row => ({criterionId:row.dataset.criterion,rating:row.querySelector('.rating').value,evidence:row.querySelector('.evidence').value}));
        state.review = await api('/api/v2/self-reviews',{conceptId:state.conceptId,attemptId:r.attemptId,rubricId:r.rubric.id,rubricVersion:r.rubric.version,judgments,confidence:null});
        render();
      } catch(error){showError(error)}
    };
    if (state.review) document.querySelector('#save-revision').onclick = async () => {
      try { await api('/api/v2/revisions',{conceptId:state.conceptId,reviewId:state.review.reviewId,answer:document.querySelector('#revision').value}); document.querySelector('#save-revision').textContent='Revision saved'; document.querySelector('#save-revision').disabled=true; } catch(error){showError(error)}
    };
    document.querySelector('#next').onclick = async () => { state.result = null; state.review = null; state.answer = ''; await refresh().catch(showError); };
    document.querySelector('#more').onclick = async () => { state.result = null; state.review = null; state.answer = ''; state.mode = 'practice'; await refresh().catch(showError); };
    return;
  }
  const s = state.session, a = s.activity;
  if (!a) {
    content.innerHTML = intro + `<div class="empty"><h3>You're caught up for now.</h3><p>${esc(s.reason || 'The next check will be offered later.')}</p>${s.nextCheckAt ? `<p>Next check: ${esc(new Date(s.nextCheckAt).toLocaleString())}</p>` : ''}</div><div class="button-row"><button class="button secondary" id="more">More practice</button></div>`;
    document.querySelector('#more').onclick = async () => { state.mode = 'practice'; await refresh().catch(showError); };
    return;
  }
  const saved = Boolean(s.draft);
  const previous = signals.recentOutcome === 'incorrect' ? 'Your previous scored answer missed its candidate key. The policy offers continued practice.' : signals.recentOutcome === 'ungraded' ? 'Your previous open answer remains ungraded; self review supplies the comparison.' : signals.recentOutcome === 'correct' ? 'Your previous answer matched a candidate key. A delayed check still requires time and unassisted evidence.' : 'Start with retrieval after reading the lesson.';
  const reason = saved ? 'Resume the first answer you already saved.' : s.recommendation?.reason || 'Continue with an available activity.';
  content.innerHTML = intro + `<span class="pill">${a.heldOut ? 'Delayed check' : 'Practice activity'}</span><div class="why"><strong>Why this activity?</strong>${esc(reason)} ${esc(previous)}</div><div class="activity-card"><span class="label">${esc(a.type.replace('_',' '))} · ${esc(a.evidenceKind)}</span><h3>${esc(a.prompt)}</h3>${a.body ? `<pre class="code">${esc(a.body)}</pre>` : ''}<div id="answer-area"></div><div class="button-row"><button id="save" class="button" ${saved?'disabled':''}>${saved?'First answer saved':'Save first answer →'}</button></div><div id="after-save"></div></div>`;
  drawAnswer(a, saved);
  document.querySelector('#save').onclick = async () => {
    try {
      if (!state.answer.trim()) throw new Error('Enter an answer first.');
      await api('/api/v2/first-answers', { conceptId:state.conceptId, activityId:a.id, draftId:crypto.randomUUID(), answer:state.answer, mode:state.mode, availableMinutes:preferences.minutes });
      await refresh();
    } catch(error){showError(error)}
  };
  if (saved) drawAfterSave(a, s.draft);
}
function drawAnswer(a, saved) {
  const area = document.querySelector('#answer-area');
  if (a.type === 'choice') {
    area.innerHTML = a.choices.map((choice,i)=>`<button class="choice ${state.answer===choice?'selected':''}" data-choice="${i}" ${saved?'disabled':''}><span></span>${esc(choice)}</button>`).join('');
    area.querySelectorAll('[data-choice]').forEach(button=>button.onclick=()=>{ state.answer=a.choices[Number(button.dataset.choice)]; drawAnswer(a,false); });
  } else if (a.type === 'trace') {
    area.innerHTML = `<label class="muted" for="answer-input">YOUR ANSWER</label><input id="answer-input" class="answer" value="${esc(state.answer)}" ${saved?'readonly':''} autocomplete="off">`;
    area.querySelector('input').oninput = event => { state.answer=event.target.value; };
  } else {
    area.innerHTML = `<label class="muted" for="answer-input">YOUR EXPLANATION OR CODE</label><textarea id="answer-input" class="answer long" ${saved?'readonly':''}>${esc(state.answer)}</textarea>`;
    area.querySelector('textarea').oninput = event => { state.answer=event.target.value; };
  }
}
function drawAfterSave(a, draft) {
  const area = document.querySelector('#after-save');
  const viewed = new Set(draft.hintLevels);
  area.innerHTML = `<div class="hint-panel"><h4>A little help, if you need it</h4><p>Hints open in order. The answer you saved stays the same.</p>${a.hints.filter(h=>viewed.has(h.level)).map(h=>`<div class="hint"><strong>${esc(h.level.replace('_',' '))}</strong><br>${esc(h.text)}</div>`).join('')}<div class="button-row">${viewed.size<a.hints.length?'<button id="hint" class="button secondary">Open next hint</button>':''}<button id="submit" class="button">Check saved answer →</button></div></div>`;
  const hint = document.querySelector('#hint');
  if (hint) hint.onclick = async () => { try { await api('/api/v2/hints',{draftId:draft.id}); await refresh(); } catch(error){showError(error)} };
  document.querySelector('#submit').onclick = async () => { try { state.result = await api('/api/v2/attempts',{draftId:draft.id,activeSeconds:Math.max(0,Math.floor((Date.now()-state.started)/1000))}); state.overview=await api('/api/v2/overview'); concepts(); render(); } catch(error){showError(error)} };
}
document.querySelector('#export').onclick = async () => {
  try { const data=await api('/api/v2/export'); data.displayPreferences = {...preferences}; const blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json'}); const url=URL.createObjectURL(blob); const link=document.createElement('a'); link.href=url; link.download='aesop-foreman-data.json'; link.click(); setTimeout(()=>URL.revokeObjectURL(url),1000); } catch(error){showError(error)}
};
document.querySelector('#delete').onclick = async () => {
  if (!confirm('Delete all local learner data for this preview? This cannot be undone.')) return;
  try { await api('/api/v2/delete',{}); try { localStorage.removeItem(preferenceKey); } catch (_) {} preferences = {minutes:20,textSize:'regular',focus:false}; applyPreferences(); state.result=null;state.answer='';await refresh(); } catch(error){showError(error)}
};
(async()=>{try{state.overview=await api('/api/v2/overview');state.conceptId=state.overview.concepts[0].id;await refresh()}catch(error){showError(error)}})();
