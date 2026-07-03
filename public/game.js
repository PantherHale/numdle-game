'use strict';
/* ═══════════════════════════════════════════════════════════════
   NUMDLE — Wordle-style number-guessing game (MCQ edition)
═══════════════════════════════════════════════════════════════ */

const MAX_Q        = 7;
const MAX_TYPE_USE = 2;

/* ── Question catalogue (mirrors numberl-master/src/questions.js) ─ */
const TYPE_ORDER = ['range','proximity','parity','modular','digit_sum','special','digit_compare','divisible'];

const TYPE_META = {
  range:         { label:'Range',        shortLabel:'Range',   accent:'#6366f1' },
  proximity:     { label:'Proximity',    shortLabel:'Near',    accent:'#7c3aed' },
  parity:        { label:'Parity',       shortLabel:'Parity',  accent:'#0891b2' },
  modular:       { label:'Modular',      shortLabel:'Mod',     accent:'#b59f3b' },
  digit_sum:     { label:'Digit Sum',    shortLabel:'Sum',     accent:'#538d4e' },
  special:       { label:'Special',      shortLabel:'Special', accent:'#e05252' },
  digit_compare: { label:'Digit Compare',shortLabel:'Digits',  accent:'#4f46e5' },
  divisible:     { label:'Divisible',    shortLabel:'Div',     accent:'#0d9488' },
};

const QUESTIONS = (() => {
  let id = 0;
  const qs = [];

  const rangePairs = [
    [1,100],[1,200],[1,300],[1,400],[1,500],[1,600],[1,700],[1,800],[1,900],
    [101,200],[201,300],[301,400],[401,500],[501,600],[601,700],[701,800],[801,900],[901,1000],
    [1,500],[251,750],[1,333],[334,666],[667,1000],[1,250],[251,500],[501,750],[751,1000],
    [201,400],[401,600],[601,800],[801,1000],
    [1,125],[126,250],[251,375],[376,500],[501,625],[626,750],[751,875],[876,1000],
    [300,700],[350,650],[400,600],[1,750],[251,1000],
  ];
  for (const [low,high] of rangePairs)
    qs.push({id:id++,type:'range',low,high,text:`Is the number between ${low} and ${high}?`});

  const proxPairs=[[250,750],[100,900],[200,800],[300,700],[400,600],[150,850],[333,666],[50,950],[450,550],[100,500],[125,875],[375,625]];
  for (const [a,b] of proxPairs)
    qs.push({id:id++,type:'proximity',a,b,text:`Is the number closer to ${a} or ${b}?`});

  qs.push({id:id++,type:'parity',text:'Is the number even or odd?'});

  for (const d of [2,3,4,5,6,7,8,9])
    qs.push({id:id++,type:'modular',divisor:d,text:`What is the number modulo ${d}?`});

  for (const t of [3,5,7,10,12,15,18,20,25])
    qs.push({id:id++,type:'digit_sum',threshold:t,text:`Is the digit sum greater than ${t}?`});

  const specials=[
    ['perfect_square', 'Is the number a perfect square?'],
    ['perfect_cube',   'Is the number a perfect cube? (1,8,27,64…)'],
    ['prime',          'Is the number prime?'],
    ['palindrome',     'Is the number a palindrome?'],
    ['fibonacci',      'Is the number a Fibonacci number?'],
    ['repeated_digit', 'Does the number have a repeated digit?'],
    ['power_of_2',     'Is the number a power of 2?'],
    ['triangular',     'Is the number a triangular number?'],
    ['digit_sum_prime','Is the digit sum itself a prime number?'],
    ['abundant',       'Is the number an abundant number? (sum of divisors > itself)'],
    ['harshad',        'Is the number divisible by its own digit sum? (Harshad number)'],
    ['two_digit',      'Does the number have exactly 2 digits? (10–99)'],
    ['three_digit',    'Does the number have exactly 3 digits? (100–999)'],
    ['product_gt_50',  'Is the product of the digits greater than 50?'],
    ['all_digits_odd',             'Are all digits of the number odd?'],
    ['ends_in_same',               'Do the first and last digits match?'],
    ['all_digits_even',            'Are all digits of the number even? (0,2,4,6,8)'],
    ['contains_zero',              'Does the number contain the digit 0?'],
    ['ascending_digits',           'Are the digits in strictly ascending order? (e.g. 135, 29)'],
    ['descending_digits',          'Are the digits in strictly descending order? (e.g. 531, 84)'],
    ['digit_sum_square',           'Is the digit sum itself a perfect square? (1,4,9,16,25)'],
    ['alternating_parity',         'Do the digits alternate between odd and even? (e.g. 123, 52)'],
    ['square_free',                'Is the number square-free? (not divisible by 4, 9, 25, 49…)'],
    ['digit_product_gt_digit_sum', 'Is the digit product greater than the digit sum?'],
  ];
  for (const [property,text] of specials)
    qs.push({id:id++,type:'special',property,text});

  for (const [p1,p2] of [
    ['hundreds','units'],['tens','hundreds'],['units','tens'],
    ['hundreds','tens'],['units','hundreds'],
  ])
    qs.push({id:id++,type:'digit_compare',pos1:p1,pos2:p2,text:`Is the ${p1} digit greater than the ${p2} digit?`});

  for (const d of [3,4,5,6,7,8,9,10,11,12,15,20,25,50,100])
    qs.push({id:id++,type:'divisible',divisor:d,text:`Is the number divisible by ${d}?`});

  return qs;
})();

/* ── Date helpers ──────────────────────────────────────────────── */
function todayISO() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
}
function getWeekDates(refISO) {
  const ref = new Date(refISO + 'T12:00:00');
  const dow = ref.getDay();
  const mon = new Date(ref);
  mon.setDate(ref.getDate() - (dow === 0 ? 6 : dow - 1));
  return Array.from({length:7},(_,i)=>{
    const d=new Date(mon); d.setDate(mon.getDate()+i);
    return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
  });
}
function weekLabel(isoDate) {
  return new Date(isoDate+'T12:00:00').toLocaleDateString('en-GB',{weekday:'short',day:'numeric',month:'short'});
}

/* ── Math helpers ──────────────────────────────────────────────── */
function digitSum(n)     { return String(n).split('').reduce((s,c)=>s+ +c,0); }
function productDigits(n){ return String(n).split('').reduce((p,c)=>p* +c,1); }
function getDigit(n,pos) {
  if (pos==='hundreds') return Math.floor(n/100)%10;
  if (pos==='tens')     return Math.floor(n/10) %10;
  return n%10;
}
const PRIME_SET        = (()=>{ const f=new Array(1001).fill(true); f[0]=f[1]=false; for(let i=2;i<=1000;i++) if(f[i]) for(let j=i*i;j<=1000;j+=i) f[j]=false; return new Set(f.reduce((a,v,i)=>v?[...a,i]:a,[])); })();
const FIBONACCI_SET    = (()=>{ const s=new Set(); let a=1,b=1; while(a<=1000){s.add(a);[a,b]=[b,a+b];} return s; })();
const POWER_OF_2_SET   = new Set([1,2,4,8,16,32,64,128,256,512]);
const PERFECT_CUBE_SET = new Set([1,8,27,64,125,216,343,512,729,1000]);
const TRIANGULAR_SET   = (()=>{ const s=new Set(); for(let k=1;k*(k+1)/2<=1000;k++) s.add(k*(k+1)/2); return s; })();
const ABUNDANT_SET     = (()=>{ const s=new Set(); for(let n=1;n<=1000;n++){let sum=1;for(let d=2;d*d<=n;d++){if(n%d===0){sum+=d;if(d!==n/d)sum+=n/d;}}if(sum>n)s.add(n);} return s; })();
const SMALL_PRIMES     = new Set([2,3,5,7,11,13,17,19,23]);
const SQUARE_FREE_SET  = (()=>{ const s=new Set(); for(let n=1;n<=1000;n++){let free=true;for(let p=2;p*p<=n;p++){if(n%(p*p)===0){free=false;break;}}if(free)s.add(n);} return s; })();

/* ── Answer a question about the secret number ─────────────────── */
function answerQ(q, secret) {
  switch (q.type) {
    case 'range':         return q.low<=secret && secret<=q.high ? 'yes' : 'no';
    case 'proximity': {   const da=Math.abs(secret-q.a),db=Math.abs(secret-q.b);
                          return da<db?`closer to ${q.a}`:db<da?`closer to ${q.b}`:'equidistant'; }
    case 'parity':        return secret%2===0?'even':'odd';
    case 'modular':       return String(secret%q.divisor);
    case 'digit_sum':     return digitSum(secret)>q.threshold?'yes':'no';
    case 'divisible':     return secret%q.divisor===0?'yes':'no';
    case 'digit_compare': return getDigit(secret,q.pos1)>getDigit(secret,q.pos2)?'yes':'no';
    case 'special': {
      const p=q.property;
      if (p==='perfect_square'){ const r=Math.round(Math.sqrt(secret)); return r*r===secret?'yes':'no'; }
      if (p==='perfect_cube')  { const r=Math.round(Math.cbrt(secret)); return r*r*r===secret?'yes':'no'; }
      if (p==='prime')          return PRIME_SET.has(secret)?'yes':'no';
      if (p==='palindrome')     { const s=String(secret); return s===[...s].reverse().join('')?'yes':'no'; }
      if (p==='fibonacci')      return FIBONACCI_SET.has(secret)?'yes':'no';
      if (p==='repeated_digit') { const s=String(secret); return new Set(s).size!==s.length?'yes':'no'; }
      if (p==='power_of_2')     return POWER_OF_2_SET.has(secret)?'yes':'no';
      if (p==='triangular')     return TRIANGULAR_SET.has(secret)?'yes':'no';
      if (p==='digit_sum_prime')return SMALL_PRIMES.has(digitSum(secret))?'yes':'no';
      if (p==='abundant')       return ABUNDANT_SET.has(secret)?'yes':'no';
      if (p==='harshad')        { const ds=digitSum(secret); return ds>0&&secret%ds===0?'yes':'no'; }
      if (p==='two_digit')      return secret>=10&&secret<=99?'yes':'no';
      if (p==='three_digit')    return secret>=100&&secret<=999?'yes':'no';
      if (p==='product_gt_50')  return productDigits(secret)>50?'yes':'no';
      if (p==='all_digits_odd') return String(secret).split('').every(c=>+c%2!==0)?'yes':'no';
      if (p==='ends_in_same')               { const s=String(secret); return s[0]===s[s.length-1]?'yes':'no'; }
      if (p==='all_digits_even')            return String(secret).split('').every(c=>+c%2===0)?'yes':'no';
      if (p==='contains_zero')              return String(secret).includes('0')?'yes':'no';
      if (p==='ascending_digits')           { const ds=String(secret).split('').map(Number); return ds.every((d,i)=>i===0||d>ds[i-1])?'yes':'no'; }
      if (p==='descending_digits')          { const ds=String(secret).split('').map(Number); return ds.every((d,i)=>i===0||d<ds[i-1])?'yes':'no'; }
      if (p==='digit_sum_square')           { const r=Math.round(Math.sqrt(digitSum(secret))); return r*r===digitSum(secret)?'yes':'no'; }
      if (p==='alternating_parity')         { const ds=String(secret).split('').map(Number); return ds.every((d,i)=>i===0||(d%2)!==(ds[i-1]%2))?'yes':'no'; }
      if (p==='square_free')                return SQUARE_FREE_SET.has(secret)?'yes':'no';
      if (p==='digit_product_gt_digit_sum') return productDigits(secret)>digitSum(secret)?'yes':'no';
      return 'unknown';
    }
    default: return '';
  }
}

/* ── Filter remaining candidates after each answer ─────────────── */
function filterCandidates(cands, q, answer) {
  let next = cands;
  if (q.type === 'range') {
    next = answer==='yes'
      ? cands.filter(n=>q.low<=n&&n<=q.high)
      : cands.filter(n=>!(q.low<=n&&n<=q.high));
  } else if (q.type === 'proximity') {
    next = cands.filter(n=>{
      const da=Math.abs(n-q.a),db=Math.abs(n-q.b);
      if (answer==='equidistant') return da===db;
      if (answer===`closer to ${q.a}`) return da<db;
      return db<da;
    });
  } else if (q.type === 'parity') {
    next = cands.filter(n=>answer==='even'?n%2===0:n%2!==0);
  } else if (q.type === 'modular') {
    const rem=Number(answer);
    next = cands.filter(n=>n%q.divisor===rem);
  } else if (q.type === 'digit_sum') {
    next = cands.filter(n=>answer==='yes'?digitSum(n)>q.threshold:digitSum(n)<=q.threshold);
  } else if (q.type === 'special') {
    const matches = n => {
      const p=q.property;
      if (p==='perfect_square') {const r=Math.round(Math.sqrt(n));return r*r===n;}
      if (p==='perfect_cube')   {const r=Math.round(Math.cbrt(n));return r*r*r===n;}
      if (p==='prime')          return PRIME_SET.has(n);
      if (p==='palindrome')     {const s=String(n);return s===[...s].reverse().join('');}
      if (p==='fibonacci')      return FIBONACCI_SET.has(n);
      if (p==='repeated_digit') {const s=String(n);return new Set(s).size!==s.length;}
      if (p==='power_of_2')     return POWER_OF_2_SET.has(n);
      if (p==='triangular')     return TRIANGULAR_SET.has(n);
      if (p==='digit_sum_prime')return SMALL_PRIMES.has(digitSum(n));
      if (p==='abundant')       return ABUNDANT_SET.has(n);
      if (p==='harshad')        {const ds=digitSum(n);return ds>0&&n%ds===0;}
      if (p==='two_digit')      return n>=10&&n<=99;
      if (p==='three_digit')    return n>=100&&n<=999;
      if (p==='product_gt_50')  return productDigits(n)>50;
      if (p==='all_digits_odd') return String(n).split('').every(c=>+c%2!==0);
      if (p==='ends_in_same')               {const s=String(n);return s[0]===s[s.length-1];}
      if (p==='all_digits_even')            return String(n).split('').every(c=>+c%2===0);
      if (p==='contains_zero')              return String(n).includes('0');
      if (p==='ascending_digits')           {const ds=String(n).split('').map(Number);return ds.every((d,i)=>i===0||d>ds[i-1]);}
      if (p==='descending_digits')          {const ds=String(n).split('').map(Number);return ds.every((d,i)=>i===0||d<ds[i-1]);}
      if (p==='digit_sum_square')           {const r=Math.round(Math.sqrt(digitSum(n)));return r*r===digitSum(n);}
      if (p==='alternating_parity')         {const ds=String(n).split('').map(Number);return ds.every((d,i)=>i===0||(d%2)!==(ds[i-1]%2));}
      if (p==='square_free')                return SQUARE_FREE_SET.has(n);
      if (p==='digit_product_gt_digit_sum') return productDigits(n)>digitSum(n);
      return false;
    };
    next = cands.filter(n=>answer==='yes'?matches(n):!matches(n));
  } else if (q.type === 'digit_compare') {
    next = cands.filter(n=>{
      const m=getDigit(n,q.pos1)>getDigit(n,q.pos2);
      return answer==='yes'?m:!m;
    });
  } else if (q.type === 'divisible') {
    next = cands.filter(n=>answer==='yes'?n%q.divisor===0:n%q.divisor!==0);
  }
  return next.length > 0 ? next : cands;
}

function summarizeCandidates(cands) {
  return { count:cands.length, min:Math.min(...cands), max:Math.max(...cands) };
}

function calculateOptimalGuess() {
  const sorted = [...candidates].sort((a,b)=>a-b);
  const mid = Math.floor((sorted.length - 1) / 2);
  const guess = sorted.length % 2 === 0
    ? Math.round((sorted[mid] + sorted[mid + 1]) / 2)
    : sorted[mid];
  return { guess, distance: Math.abs(guess - secret) };
}

/* ── ALL_VOCAB + findVocabAction (for RL training log) ─────────── */
const ALL_VOCAB=[
  ...[
    [1,100],[1,200],[1,300],[1,400],[1,500],[1,600],[1,700],[1,800],[1,900],
    [101,200],[201,300],[301,400],[401,500],[501,600],[601,700],[701,800],[801,900],[901,1000],
    [1,500],[251,750],[1,333],[334,666],[667,1000],[1,250],[251,500],[501,750],[751,1000],
    [201,400],[401,600],[601,800],[801,1000],
    [1,125],[126,250],[251,375],[376,500],[501,625],[626,750],[751,875],[876,1000],
    [300,700],[350,650],[400,600],[1,750],[251,1000],
  ].map(([low,high])=>({type:'range',low,high})),
  ...[
    [250,750],[100,900],[200,800],[300,700],[400,600],
    [150,850],[333,666],[50,950],[450,550],[100,500],[125,875],[375,625],
  ].map(([a,b])=>({type:'proximity',a,b})),
  {type:'parity'},
  ...[2,3,4,5,6,7,8,9].map(d=>({type:'modular',divisor:d})),
  ...[3,5,7,10,12,15,18,20,25].map(t=>({type:'digit_sum',threshold:t})),
  ...['perfect_square','perfect_cube','prime','palindrome','fibonacci','repeated_digit','power_of_2','triangular','digit_sum_prime','abundant','harshad','two_digit','three_digit','product_gt_50','all_digits_odd','ends_in_same','all_digits_even','contains_zero','ascending_digits','descending_digits','digit_sum_square','alternating_parity','square_free','digit_product_gt_digit_sum'].map(p=>({type:'special',property:p})),
  ...[['hundreds','units'],['tens','hundreds'],['units','tens'],['hundreds','tens'],['units','hundreds']].map(([p1,p2])=>({type:'digit_compare',pos1:p1,pos2:p2})),
  ...[3,4,5,6,7,8,9,10,11,12,15,20,25,50,100].map(d=>({type:'divisible',divisor:d})),
];
function findVocabAction(q) {
  for (let i=0;i<ALL_VOCAB.length;i++){
    const v=ALL_VOCAB[i]; if(v.type!==q.type) continue;
    if(q.type==='range')         { if(v.low===q.low&&v.high===q.high) return i; }
    else if(q.type==='parity')   return i;
    else if(q.type==='modular')  { if(v.divisor===q.divisor) return i; }
    else if(q.type==='special')  { if(v.property===q.property) return i; }
    else if(q.type==='divisible'){ if(v.divisor===q.divisor) return i; }
    else if(q.type==='digit_sum'){ if(v.threshold===q.threshold) return i; }
    else if(q.type==='proximity'){ if(v.a===q.a&&v.b===q.b) return i; }
    else if(q.type==='digit_compare'){ if(v.pos1===q.pos1&&v.pos2===q.pos2) return i; }
  }
  return -1;
}

/* ═══════════════════════════════════════════════════════════════
   STATE
═══════════════════════════════════════════════════════════════ */
const TODAY       = todayISO();
const STORAGE_KEY = `numdle_v2_${TODAY}`;
const ALL_LOG_KEY = 'numdle_v2_all_games';
const AUTH_KEY    = 'numdle_auth_v2';

let secret=null, aiData=null, allDailyData=null, gs=null;
let candidates = [];
let activeType  = 'range';

function defaultState() { return {asked:[],typeCounts:{},gameOver:false,humanGuess:null,humanDist:null,optimalDist:null}; }
function saveState()    { localStorage.setItem(STORAGE_KEY,JSON.stringify(gs)); }

function recomputeCandidates() {
  candidates = gs.asked.reduce((cands, entry) => {
    const q = entry.question || entry.parsed;
    if (!q) return cands;
    return filterCandidates(cands, q, entry.answer);
  }, Array.from({length:1000},(_,i)=>i+1));
}

function loadState() {
  try {
    const r=localStorage.getItem(STORAGE_KEY);
    if (r) {
      gs={...defaultState(),...JSON.parse(r)};
      recomputeCandidates();
      return;
    }
  } catch(_) {}
  gs=defaultState();
  candidates=Array.from({length:1000},(_,i)=>i+1);
}

/* ── Auth state ─────────────────────────────────────────────────── */
function getAuth()             { try{return JSON.parse(localStorage.getItem(AUTH_KEY))||null;}catch(_){return null;} }
function saveAuth(token,user)  { localStorage.setItem(AUTH_KEY,JSON.stringify({token,username:user})); }
function clearAuth()           { localStorage.removeItem(AUTH_KEY); }
function apiHeaders()          { const a=getAuth(); const h={'Content-Type':'application/json'}; if(a?.token) h['X-Auth-Token']=a.token; return h; }

/* ═══════════════════════════════════════════════════════════════
   GAME LOGGING
═══════════════════════════════════════════════════════════════ */
function getLocalLogs() {
  try { return JSON.parse(localStorage.getItem(ALL_LOG_KEY)||'[]'); } catch(_) { return []; }
}

function saveGameLog(humanGuess, humanDist, aiDist, outcome, optimalDist) {
  const newTypes = gs.asked.filter(a=>a.vocab_action===-1);
  const entry = {
    game_id:              Math.random().toString(36).slice(2),
    date:                 TODAY,
    week:                 getWeekDates(TODAY)[0],
    secret,
    questions_asked:      gs.asked.length,
    questions:            gs.asked.map(a=>({
      text:a.text, answer:a.answer, type:a.type,
      vocab_action:a.vocab_action, is_new_type:a.vocab_action===-1,
    })),
    human_guess:          humanGuess,
    human_distance:       humanDist,
    ai_guess:             aiData.guess,
    ai_distance:          aiDist,
    optimal_distance:     optimalDist,
    outcome,
    has_unique_questions: newTypes.length > 0,
    played_at:            new Date().toISOString(),
  };
  try {
    const logs = getLocalLogs();
    logs.push(entry);
    localStorage.setItem(ALL_LOG_KEY, JSON.stringify(logs));
  } catch(_) {}
  postGameToServer(entry);
  return entry;
}

async function postGameToServer(entry) {
  try { await fetch('/log_game',{method:'POST',headers:apiHeaders(),body:JSON.stringify(entry)}); }
  catch(_) {}
}

/* ═══════════════════════════════════════════════════════════════
   UI HELPERS
═══════════════════════════════════════════════════════════════ */
const $=sel=>document.querySelector(sel);
function escHtml(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}

function showToast(msg, isError=false) {
  const rack=document.getElementById('toast-rack');
  const t=document.createElement('div');
  t.className='toast'+(isError?' error':'');
  t.textContent=msg;
  rack.appendChild(t);
  setTimeout(()=>t.remove(),2400);
}

function openModal(id)  { const el=document.getElementById(id); if(el) el.hidden=false; }
function closeModal(id) { const el=document.getElementById(id); if(el) el.hidden=true;  }

/* ── Candidate grid ─────────────────────────────────────────────── */
const GRID_BEHAVIOR = {
  range:         (ans)=>ans==='yes'?'Range zoomed to the kept interval.':'Range removed that interval, rebalancing candidates.',
  proximity:     (ans)=>ans==='equidistant'?'Proximity kept only the midpoint tie.':'Proximity kept the side closer to the answer.',
  parity:        ()=>'Parity leaves alternating candidate cells.',
  modular:       ()=>'Modulo leaves repeating remainder cells.',
  digit_sum:     ()=>'Digit sum keeps numbers matching the threshold result.',
  special:       ()=>'Special property creates sparse matching cells.',
  digit_compare: ()=>'Digit comparison keeps numbers matching the digit pattern.',
  divisible:     ()=>'Divisibility keeps or removes regular multiple cells.',
};

function renderCandidateGrid(lastEntry) {
  const countEl = document.getElementById('cands-left');
  if (countEl) countEl.textContent = candidates.length;

  const section = document.getElementById('candidate-section');
  const behavEl = document.getElementById('grid-behavior');
  const grid    = document.getElementById('candidate-grid');
  if (!grid) return;
  if (section) section.style.display = '';

  grid.innerHTML = '';

  if (gs.asked.length === 0) {
    // No questions yet — show a prompt instead of 1000 boxes
    const ph = document.createElement('span');
    ph.className = 'cand-placeholder';
    ph.textContent = 'Ask a question to see which numbers are still possible.';
    grid.appendChild(ph);
    if (behavEl) behavEl.textContent = '';
    return;
  }

  // Show only the surviving candidates as individual chips
  for (const n of candidates) {
    const chip = document.createElement('span');
    chip.className = 'candidate-chip';
    chip.textContent = n;
    grid.appendChild(chip);
  }

  if (behavEl) {
    const fn  = lastEntry && GRID_BEHAVIOR[lastEntry.question?.type || lastEntry.type];
    const ctx = lastEntry ? `Answer: ${lastEntry.answer}. ${fn ? fn(lastEntry.answer) : ''}  ` : '';
    behavEl.textContent = `${ctx}${candidates.length} number${candidates.length === 1 ? '' : 's'} remaining.`;
  }
}

/* ── Custom question form (fill-in-the-blank for each type) ─────── */
function buildCustomForm(type, capReached) {
  const wrap = document.createElement('div');
  wrap.className = 'custom-q';

  const errEl = document.createElement('p');
  errEl.className = 'custom-err';

  function addErr(msg) { errEl.textContent = msg; }
  function clearErr()  { errEl.textContent = ''; }

  function inp(placeholder, min, max, width) {
    const el = document.createElement('input');
    el.type = 'number'; el.className = 'custom-in';
    el.placeholder = placeholder;
    if (min !== undefined) el.min = min;
    if (max !== undefined) el.max = max;
    if (width) el.style.width = width;
    return el;
  }

  function askBtn(onclick) {
    const btn = document.createElement('button');
    btn.type = 'button'; btn.className = 'custom-ask-btn';
    btn.textContent = 'Ask'; btn.disabled = capReached;
    btn.addEventListener('click', onclick);
    return btn;
  }

  function row(...nodes) {
    const r = document.createElement('div');
    r.className = 'custom-row';
    nodes.forEach(n => {
      if (typeof n === 'string') { const s=document.createElement('span'); s.className='custom-sep'; s.textContent=n; r.appendChild(s); }
      else r.appendChild(n);
    });
    return r;
  }

  if (type === 'range') {
    const low = inp('1',1,999,'62px'), high = inp('1000',2,1000,'62px');
    wrap.appendChild(row('Between', low, 'and', high,
      askBtn(() => {
        clearErr();
        const lo=parseInt(low.value), hi=parseInt(high.value);
        if (isNaN(lo)||isNaN(hi))        return addErr('Enter both numbers.');
        if (lo<1||hi>1000||lo>=hi)       return addErr('Need 1 ≤ low < high ≤ 1000.');
        if (hi-lo+1 < 10)                return addErr('Range must span at least 10 numbers.');
        ask({id:-1,type:'range',low:lo,high:hi,text:`Is the number between ${lo} and ${hi}?`});
      })
    ));
  } else if (type === 'proximity') {
    const a = inp('100',1,1000,'62px'), b = inp('900',1,1000,'62px');
    wrap.appendChild(row('Closer to', a, 'or', b, '?',
      askBtn(() => {
        clearErr();
        const av=parseInt(a.value), bv=parseInt(b.value);
        if (isNaN(av)||isNaN(bv))  return addErr('Enter both numbers.');
        if (av<1||av>1000||bv<1||bv>1000) return addErr('Both must be 1–1000.');
        if (av===bv)               return addErr('Numbers must differ.');
        ask({id:-1,type:'proximity',a:av,b:bv,text:`Is the number closer to ${av} or ${bv}?`});
      })
    ));
  } else if (type === 'parity') {
    /* Parity has only one question — no custom form needed */
    return null;
  } else if (type === 'modular') {
    const d = inp('3',2,9,'55px');
    wrap.appendChild(row('Number mod', d, '(2–9)',
      askBtn(() => {
        clearErr();
        const dv=parseInt(d.value);
        if (isNaN(dv)||dv<2||dv>9) return addErr('Divisor must be 2–9.');
        ask({id:-1,type:'modular',divisor:dv,text:`What is the number modulo ${dv}?`});
      })
    ));
  } else if (type === 'digit_sum') {
    const t = inp('15',1,27,'55px');
    wrap.appendChild(row('Digit sum >', t, '?',
      askBtn(() => {
        clearErr();
        const tv=parseInt(t.value);
        if (isNaN(tv)||tv<1||tv>27) return addErr('Threshold must be 1–27.');
        ask({id:-1,type:'digit_sum',threshold:tv,text:`Is the digit sum greater than ${tv}?`});
      })
    ));
  } else if (type === 'special') {
    return null;
  } else if (type === 'digit_compare') {
    return null;
  } else if (type === 'divisible') {
    const d = inp('7',2,500,'55px');
    wrap.appendChild(row('Divisible by', d, '?',
      askBtn(() => {
        clearErr();
        const dv=parseInt(d.value);
        if (isNaN(dv)||dv<2||dv>500) return addErr('Divisor must be 2–500.');
        ask({id:-1,type:'divisible',divisor:dv,text:`Is the number divisible by ${dv}?`});
      })
    ));
  } else {
    return null;
  }

  wrap.appendChild(errEl);
  return wrap;
}

/* ── MCQ Picker (renders inside active board row) ───────────────── */
function buildPicker() {
  const usedIds  = new Set(gs.asked.map(e=>(e.question||{}).id ?? -1));
  const capReached = (gs.typeCounts[activeType]||0) >= MAX_TYPE_USE;
  const picker   = document.createElement('div');
  picker.className = 'picker';

  /* Type tabs */
  const tabs = document.createElement('div');
  tabs.className = 'type-tabs';
  TYPE_ORDER.forEach(type=>{
    const btn=document.createElement('button');
    btn.type='button';
    btn.className='type-tab'+(type===activeType?' selected':'');
    btn.textContent=TYPE_META[type].shortLabel;
    btn.addEventListener('click',()=>{ activeType=type; renderBoard(); });
    tabs.appendChild(btn);
  });
  picker.appendChild(tabs);

  /* Meta line */
  const typeCount = gs.typeCounts[activeType]||0;
  const meta = document.createElement('div');
  meta.className = 'picker-meta';
  meta.innerHTML = `<span>${TYPE_META[activeType].label} &nbsp;<strong>${typeCount}/${MAX_TYPE_USE}</strong></span>${activeType==='modular'?'<span class="no-mod">Max mod 9</span>':''}`;
  picker.appendChild(meta);

  /* Custom fill-in-the-blank form */
  const customForm = buildCustomForm(activeType, capReached);
  if (customForm) {
    picker.appendChild(customForm);
    const divider = document.createElement('div');
    divider.className = 'preset-divider';
    divider.textContent = 'Or choose a preset:';
    picker.appendChild(divider);
  }

  /* Preset question list */
  const list = document.createElement('div');
  list.className = 'question-list';
  QUESTIONS.filter(q=>q.type===activeType).forEach(q=>{
    const btn=document.createElement('button');
    btn.type='button'; btn.className='q-item';
    let disabled=false, tag='';
    if (usedIds.has(q.id))                              { disabled=true; tag='used'; }
    else if ((gs.typeCounts[q.type]||0)>=MAX_TYPE_USE) { disabled=true; tag='cap'; }
    btn.disabled=disabled;
    btn.innerHTML=`<span class="q-item-text">${escHtml(q.text)}</span>${tag?`<em class="q-item-tag">${tag}</em>`:''}`;
    if (!disabled) btn.addEventListener('click',()=>ask(q));
    list.appendChild(btn);
  });
  picker.appendChild(list);
  return picker;
}

/* ── Board (7 rows, active row expands with MCQ picker) ─────────── */
function renderBoard() {
  const board=document.getElementById('board');
  if (!board) return;
  board.innerHTML='';
  for (let i=0;i<MAX_Q;i++) {
    const row=document.createElement('div');
    row.className='q-row';
    row.id=`qrow-${i}`;

    if (i<gs.asked.length) {
      const a=gs.asked[i];
      const al=a.answer.toLowerCase();
      row.classList.add(al==='yes'?'q-row--yes':al==='no'?'q-row--no':'q-row--num');
      row.innerHTML=`<span class="q-text">${escHtml(a.text)}</span><span class="q-ans">${escHtml(a.answer.toUpperCase())}</span>`;

    } else if (i===gs.asked.length && !gs.gameOver) {
      row.classList.add('q-row--active');
      const hdr=document.createElement('div');
      hdr.className='slot-hdr';
      hdr.innerHTML=`<span class="q-text q-placeholder">Choose a question below</span><span class="q-ans">—</span>`;
      row.appendChild(hdr);
      row.appendChild(buildPicker());

    } else {
      row.classList.add('q-row--empty');
    }
    board.appendChild(row);
  }
  document.getElementById('qs-used').textContent=gs.asked.length;
}

/* ── Week strip ─────────────────────────────────────────────────── */
function renderWeekStrip(allData) {
  const strip=document.getElementById('week-strip');
  if (!strip) return;
  const weekDates=getWeekDates(TODAY);
  const localLogs=(()=>{try{return JSON.parse(localStorage.getItem(ALL_LOG_KEY)||'[]');}catch(_){return [];}})();
  strip.innerHTML='';
  weekDates.forEach(iso=>{
    const isToday=iso===TODAY, isPast=iso<TODAY;
    const myGame=localLogs.find(l=>l.date===iso);
    const pill=document.createElement('div');
    pill.className=`day-pill ${isToday?'dp-today':isPast?'dp-past':'dp-future'}`;
    const name=new Date(iso+'T12:00:00').toLocaleDateString('en-GB',{weekday:'short'});
    const day=new Date(iso+'T12:00:00').getDate();
    let score='—';
    if (iso>TODAY) score='🔒';
    else if (myGame){const icon=myGame.outcome==='human_wins'?'🏆':myGame.outcome==='tie'?'🤝':'😔'; score=icon;}
    else if (isToday) score='•';
    pill.innerHTML=`<span class="dp-name">${name} ${day}</span><span class="dp-score">${score}</span>`;
    strip.appendChild(pill);
  });
}

/* ═══════════════════════════════════════════════════════════════
   WEEK VIEW (post-game)
═══════════════════════════════════════════════════════════════ */
function renderWeekView() {
  const localLogs = getLocalLogs();
  const ref       = new Date(TODAY + 'T12:00:00');
  const year      = ref.getFullYear();
  const month     = ref.getMonth();           // 0-based
  const totalDays = new Date(year, month + 1, 0).getDate();
  const firstDow  = new Date(year, month, 1).getDay();   // 0=Sun…6=Sat
  /* Monday-first offset: Sun->6, Mon->0, Tue->1, … */
  const offset    = (firstDow + 6) % 7;

  const daysEl = document.getElementById('wv-days');
  if (!daysEl) return;
  daysEl.innerHTML = '';

  /* Day-of-week header row */
  ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'].forEach(d => {
    const h = document.createElement('div');
    h.className = 'wv-dow-hdr';
    h.textContent = d;
    daysEl.appendChild(h);
  });

  /* Leading empty cells */
  for (let i = 0; i < offset; i++) {
    const e = document.createElement('div');
    e.className = 'wv-empty';
    daysEl.appendChild(e);
  }

  /* One cell per day */
  for (let d = 1; d <= totalDays; d++) {
    const iso     = `${year}-${String(month+1).padStart(2,'0')}-${String(d).padStart(2,'0')}`;
    const isToday = iso === TODAY;
    const isFuture= iso > TODAY;
    const myGame  = localLogs.find(l => l.date === iso);
    const won     = myGame?.outcome === 'human_wins';
    const tied    = myGame?.outcome === 'tie';

    const cell = document.createElement('div');
    cell.className = 'wv-day'
      + (isToday  ? ' wv-today'  : '')
      + (isFuture ? ' wv-future' : '')
      + (won      ? ' wv-win'    : '')
      + (myGame?.outcome === 'ai_wins' ? ' wv-loss' : '')
      + (tied     ? ' wv-tie'    : '');

    const icon = isFuture ? ''
               : !myGame && isToday ? '•'
               : won  ? '🏆'
               : tied ? '🤝'
               : myGame ? '😔' : '';

    const dayEntry   = allDailyData ? allDailyData[iso] : null;
    const secretNum  = dayEntry ? (dayEntry.s ?? dayEntry.secret) : null;
    const isPastMiss = !isFuture && iso < TODAY && !myGame;

    cell.innerHTML =
      `<div class="wv-day-num">${d}</div>` +
      `<div class="wv-day-icon">${icon}</div>` +
      (myGame && secretNum ? `<div class="wv-day-secret">${secretNum}</div>` : '') +
      (myGame ? `<div class="wv-day-dist">±${myGame.human_distance}</div>` : '') +
      (isPastMiss ? `<div class="wv-day-secret wv-day-secret--hidden">?</div>` : '');
    daysEl.appendChild(cell);
  }

  /* Stats for this month */
  const pad2 = n => String(n).padStart(2,'0');
  const monthPrefix = `${year}-${pad2(month+1)}`;
  const monthGames  = localLogs.filter(l => l.date.startsWith(monthPrefix));
  const wins   = monthGames.filter(g => g.outcome === 'human_wins').length;
  const losses = monthGames.filter(g => g.outcome === 'ai_wins').length;
  const rate   = monthGames.length ? Math.round(100 * wins / monthGames.length) : 0;

  /* Streak (backwards from today) */
  let streak = 0;
  let cur = new Date(ref);
  while (true) {
    const iso2 = `${cur.getFullYear()}-${pad2(cur.getMonth()+1)}-${pad2(cur.getDate())}`;
    if (iso2 > TODAY) { cur.setDate(cur.getDate()-1); continue; }
    const g = localLogs.find(l => l.date === iso2);
    if (g && (g.outcome === 'human_wins' || g.outcome === 'tie')) { streak++; cur.setDate(cur.getDate()-1); }
    else break;
  }

  document.getElementById('wv-wins').textContent   = wins;
  document.getElementById('wv-losses').textContent = losses;
  document.getElementById('wv-rate').textContent   = rate + '%';
  document.getElementById('wv-streak').textContent = streak;

  const wvTitle  = document.querySelector('.wv-title');
  const rangeEl  = document.getElementById('wv-date-range');
  if (wvTitle) wvTitle.textContent = ref.toLocaleDateString('en-GB', {month:'long', year:'numeric'});
  if (rangeEl) rangeEl.textContent = `${monthGames.length} games played`;

  const signupBtn = document.getElementById('wv-signup-btn');
  if (signupBtn) signupBtn.style.display = getAuth() ? 'none' : 'flex';
}

/* ═══════════════════════════════════════════════════════════════
   LEADERBOARD PAGE
═══════════════════════════════════════════════════════════════ */
function renderLbWeekGrid() {
  const grid = document.getElementById('lb-week-grid');
  if (!grid) return;
  const weekDates = getWeekDates(TODAY);
  const localLogs = getLocalLogs();
  const days = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];

  grid.innerHTML = '';
  weekDates.forEach((iso, idx) => {
    const isToday  = iso === TODAY;
    const isFuture = iso > TODAY;
    const myGame   = localLogs.find(l => l.date === iso);
    const entry    = allDailyData ? allDailyData[iso] : null;
    const won = myGame?.outcome === 'human_wins';
    const missed = !myGame && !isFuture && iso < TODAY;

    const card = document.createElement('div');
    card.className = 'lb-day-card'
      + (isToday ? ' lbd-today' : '')
      + (isFuture ? ' lbd-future' : '')
      + (won ? ' lbd-win' : '')
      + (missed ? ' lbd-loss' : '');

    const dayNum = new Date(iso + 'T12:00:00').getDate();
    const icon = isFuture ? '🔒'
               : !myGame && isToday ? '•'
               : won ? '🏆'
               : myGame?.outcome === 'tie' ? '🤝'
               : myGame ? '😔' : '—';
    const secretNum  = entry ? (entry.s ?? entry.secret) : null;
    const isPastMiss = !isFuture && iso < TODAY && !myGame;

    card.innerHTML =
      `<div class="lb-day-name">${days[idx]}</div>` +
      `<div class="lb-day-num">${dayNum}</div>` +
      `<div class="lb-day-icon">${icon}</div>` +
      (myGame && secretNum ? `<div class="lb-day-secret">${secretNum}</div>` : '') +
      (myGame ? `<div class="lb-day-dist">Off ${myGame.human_distance}</div>` : '') +
      (isPastMiss ? `<div class="lb-day-secret lb-day-secret--hidden">?</div>` : '');
    grid.appendChild(card);
  });
}

function renderLeaderboardPage(data) {
  const me   = data.me;
  const list = data.leaderboard || [];

  const myCard    = document.getElementById('lb-my-card');
  const signCard  = document.getElementById('lb-signup-card');

  if (me) {
    document.getElementById('my-rank').textContent        = me.rank ?? '—';
    document.getElementById('my-display-name').textContent= me.username;
    document.getElementById('my-win-rate').textContent    = (me.win_rate ?? 0) + '%';
    document.getElementById('my-optimal').textContent     = me.optimal_rate != null ? me.optimal_rate + '%' : '—';
    document.getElementById('my-streak').textContent      = me.streak ?? 0;
    document.getElementById('my-games').textContent       = me.total_games ?? 0;
    const sn = me.streak || 0;
    document.getElementById('my-streak-label').textContent = sn > 0 ? `${sn}-day streak 🔥` : 'No current streak';
    if (myCard) myCard.style.display = 'block';
    if (signCard) signCard.style.display = 'none';
  } else {
    if (myCard) myCard.style.display = 'none';
    if (signCard) signCard.style.display = 'flex';
  }

  const rankingsEl = document.getElementById('lb-rankings');
  if (!list.length) {
    rankingsEl.innerHTML = '<p class="muted" style="text-align:center;padding:16px">No players yet. Play and sign up!</p>';
    return;
  }

  const rows = list.filter(r => !r.suspicious).map(r => {
    const rCls = r.rank===1?'lb-rank-1':r.rank===2?'lb-rank-2':r.rank===3?'lb-rank-3':'';
    const nameStr = escHtml(r.username) + (r.is_ai ? ' 🤖' : r.is_me ? ' ← you' : '');
    return `<div class="lb-row${r.is_me?' lb-row-me':''}${r.is_ai?' lb-row-ai':''}">
      <span class="lb-row-rank ${rCls}">${r.rank ?? '—'}</span>
      <span class="lb-row-name">${nameStr}</span>
      <span class="lb-row-rate">${r.win_rate ?? 0}%</span>
      <span class="lb-row-opt">${r.optimal_rate != null ? r.optimal_rate + '%' : '—'}</span>
      <span class="lb-row-games">${r.total_games ?? 0}</span>
    </div>`;
  }).join('');
  rankingsEl.innerHTML = rows;
}

async function showLeaderboardPage() {
  renderLbWeekGrid();
  document.getElementById('lb-page').style.display = 'flex';
  document.getElementById('lb-rankings').innerHTML = '<p class="muted" style="text-align:center;padding:16px">Loading…</p>';
  try {
    const res  = await fetch('/api/leaderboard', {headers: apiHeaders()});
    const data = await res.json();
    renderLeaderboardPage(data);
  } catch(_) {
    document.getElementById('lb-rankings').innerHTML = '<p class="muted" style="text-align:center;padding:16px">Could not load rankings.</p>';
  }
}

/* ═══════════════════════════════════════════════════════════════
   AUTH UI
═══════════════════════════════════════════════════════════════ */
let authMode='signup';

function updateAuthUI() {
  const auth=getAuth();
  const formEl=document.querySelector('.auth-form');
  const doneEl=document.getElementById('auth-loggedin');
  if (auth) {
    if(formEl) formEl.style.display='none';
    if(doneEl){ doneEl.style.display='block'; document.getElementById('auth-username-display').textContent=auth.username; }
  } else {
    if(formEl) formEl.style.display='flex';
    if(doneEl) doneEl.style.display='none';
  }
}

async function handleAuth() {
  const username=(document.getElementById('auth-username').value||'').trim();
  const password=(document.getElementById('auth-password').value||'').trim();
  const errEl=document.getElementById('auth-error');
  if (!username||!password){errEl.textContent='Fill in both fields.';return;}
  errEl.textContent='Saving...';
  try {
    const res=await fetch(authMode==='signup'?'/api/signup':'/api/login',
      {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username,password})});
    const d=await res.json();
    if (!res.ok){errEl.textContent=d.error||'Something went wrong.';return;}
    errEl.textContent='';
    saveAuth(d.token,d.username);
    updateAuthUI();
    document.getElementById('auth-password').value='';
    showToast(`Welcome, ${d.username}!`);
  } catch(_){errEl.textContent='Network error.';}
}

async function handleLogout() {
  try{await fetch('/api/logout',{method:'POST',headers:apiHeaders()});}catch(_){}
  clearAuth(); updateAuthUI(); showToast('Logged out.');
}

function setAuthMode(mode) {
  authMode=mode;
  const isSignup=mode==='signup';
  document.getElementById('auth-title').textContent   =isSignup?'Create Account':'Log In';
  document.getElementById('auth-subtitle').textContent=isSignup?'Sign up to track your score on the leaderboard. Login stays active for one week.':'Welcome back!';
  document.getElementById('auth-submit').textContent  =isSignup?'Create Account':'Log In';
  document.getElementById('auth-toggle').textContent  =isSignup?'Already have an account? Log in':'New here? Create an account';
  document.getElementById('auth-error').textContent   ='';
}

/* ═══════════════════════════════════════════════════════════════
   GAME FLOW
═══════════════════════════════════════════════════════════════ */
function ask(question) {
  if (gs.gameOver||gs.asked.length>=MAX_Q) return;

  const answer=answerQ(question, secret);
  if (!answer) return;

  candidates=filterCandidates(candidates, question, answer);

  const vocabAction=findVocabAction(question);
  const entry={
    question,
    text:     question.text,
    answer,
    vocab_action: vocabAction,
    type:     question.type,
    is_new_type: vocabAction===-1,
    parsed:   question,
  };
  gs.asked.push(entry);
  gs.typeCounts[question.type]=(gs.typeCounts[question.type]||0)+1;
  saveState();

  renderBoard();
  renderCandidateGrid(entry);

  if (gs.asked.length>=MAX_Q) {
    showToast('All 6 questions used — now submit your guess!');
  }
}

function handleGuess() {
  if (gs.gameOver) { showToast('You already played today!'); return; }
  const input=$('#guess-input');
  const val=parseInt(input.value);
  if (isNaN(val)||val<1||val>1000){$('#form-error').textContent='Enter a whole number between 1 and 1000.';return;}
  if (gs.asked.length < 1){$('#form-error').textContent='Ask at least one question before guessing.';return;}
  $('#form-error').textContent='';

  const humanDist=Math.abs(val-secret);
  const aiDist=aiData.distance;
  const outcome=humanDist<aiDist?'human_wins':humanDist>aiDist?'ai_wins':'tie';

  const optimalData = calculateOptimalGuess();
  gs.gameOver=true; gs.humanGuess=val; gs.humanDist=humanDist; gs.optimalDist=optimalData.distance;
  saveState();
  saveGameLog(val,humanDist,aiDist,outcome,optimalData.distance);
  showResults(val,humanDist,aiDist,outcome);
}

function showGameOverBanner() {
  const activeArea = document.getElementById('active-game-area');
  const weekStrip  = document.getElementById('week-strip');
  const weekView   = document.getElementById('week-view');
  if (activeArea) activeArea.style.display = 'none';
  if (weekStrip)  weekStrip.style.display  = 'none';
  if (weekView)   { weekView.style.display = 'flex'; renderWeekView(); }
}

function showResults(humanGuess, humanDist, aiDist, outcome) {
  document.getElementById('reveal-num').textContent   = secret;
  document.getElementById('human-guess').textContent  = humanGuess;
  document.getElementById('human-dist').innerHTML     = `Off by <strong>${humanDist}</strong>`;
  document.getElementById('ai-guess').textContent     = aiData.guess;
  document.getElementById('ai-dist').innerHTML        = `Off by <strong>${aiDist}</strong>`;

  const hCard=document.getElementById('human-card');
  const aCard=document.getElementById('ai-card');
  hCard.className='score-card'; aCard.className='score-card';

  if (outcome==='human_wins'){
    hCard.classList.add('winner'); aCard.classList.add('loser');
    document.getElementById('human-badge').textContent='You win!';
    document.getElementById('ai-badge').textContent='Lost';
    document.getElementById('results-msg').innerHTML='<span class="win-txt">You beat the AI today!</span>';
  } else if (outcome==='ai_wins'){
    hCard.classList.add('loser'); aCard.classList.add('winner');
    document.getElementById('human-badge').textContent='Lost';
    document.getElementById('ai-badge').textContent='AI wins';
    document.getElementById('results-msg').textContent='The AI was closer this time. Come back tomorrow!';
  } else {
    hCard.classList.add('tie'); aCard.classList.add('tie');
    document.getElementById('human-badge').textContent='Tie!';
    document.getElementById('ai-badge').textContent='Tie!';
    document.getElementById('results-msg').textContent="It's a tie — you perfectly matched the AI!";
  }

  /* Optimal note */
  const optNote  = document.getElementById('optimal-note');
  const optText  = document.getElementById('optimal-note-text');
  const optDist  = gs.optimalDist;
  if (optNote && optDist != null) {
    const aiDist2 = aiData.distance;
    const msg = optDist < aiDist2
      ? `Optimal guess (median) was off by ${optDist} — even better than the AI!`
      : optDist === aiDist2
        ? `Optimal guess was also off by ${optDist} — same as the AI.`
        : `Optimal guess would have been off by ${optDist}.`;
    if (optText) optText.textContent = msg;
    optNote.style.display = 'block';
  } else if (optNote) {
    optNote.style.display = 'none';
  }

  /* Show sign-up CTA only if not logged in */
  const signupEl = document.getElementById('results-signup');
  if (signupEl) signupEl.style.display = getAuth() ? 'none' : 'flex';

  const log=document.getElementById('ai-qa-log'); log.innerHTML='';
  (aiData.questions||[]).forEach(({question,answer})=>{
    const row=document.createElement('div');
    row.className='ai-qa-row';
    row.innerHTML=`<span class="ai-qa-q">${escHtml(question)}</span><span class="ai-qa-a">${escHtml(answer)}</span>`;
    log.appendChild(row);
  });

  showGameOverBanner();
  renderWeekStrip(allDailyData);
  openModal('results-modal');
}

function restoreGame() {
  renderBoard();
  renderCandidateGrid(gs.asked.length ? gs.asked[gs.asked.length-1] : null);
  if (gs.gameOver) {
    showGameOverBanner();
    if (gs.humanGuess !== null) {
      const outcome = gs.humanDist < aiData.distance ? 'human_wins'
                    : gs.humanDist > aiData.distance ? 'ai_wins' : 'tie';
      showResults(gs.humanGuess, gs.humanDist, aiData.distance, outcome);
    }
  }
}

/* ═══════════════════════════════════════════════════════════════
   INIT
═══════════════════════════════════════════════════════════════ */
async function init() {
  try {
    const res=await fetch('daily_data.json');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    allDailyData=await res.json();
  } catch(e) {
    document.getElementById('loading').style.display='none';
    document.getElementById('error-screen').style.display='flex';
    document.getElementById('error-text').textContent=`Could not load daily data: ${e.message}`;
    return;
  }

  const entry=allDailyData[TODAY];
  if (!entry){
    document.getElementById('loading').style.display='none';
    document.getElementById('error-screen').style.display='flex';
    document.getElementById('error-text').textContent=`No data for today (${TODAY}). Run precompute.py --week.`;
    return;
  }

  secret  = entry.s??entry.secret;
  aiData  = {guess:entry.ag??entry.ai_guess, distance:entry.ad??entry.ai_distance, questions:entry.aq??entry.ai_questions};

  loadState();
  document.getElementById('loading').style.display='none';
  document.getElementById('game').style.display='block';

  renderBoard();
  renderCandidateGrid(gs.asked.length?gs.asked[gs.asked.length-1]:null);
  renderWeekStrip(allDailyData);
  updateAuthUI();

  /* Modal close — always wired */
  document.querySelectorAll('[data-close]').forEach(btn=>{
    btn.addEventListener('click',()=>closeModal(btn.dataset.close));
  });
  document.querySelectorAll('.modal-back').forEach(b=>{
    b.addEventListener('click',e=>{if(e.target===b)b.hidden=true;});
  });
  document.addEventListener('keydown',e=>{
    if(e.key==='Escape') document.querySelectorAll('.modal-back').forEach(m=>{m.hidden=true;});
  });

  /* Header buttons */
  document.getElementById('help-btn').addEventListener('click',()=>openModal('help-modal'));
  document.getElementById('leaderboard-btn').addEventListener('click',()=>showLeaderboardPage());
  document.getElementById('account-btn').addEventListener('click',()=>{
    updateAuthUI(); openModal('auth-modal');
  });

  /* Leaderboard page */
  document.getElementById('lb-back-btn')?.addEventListener('click',()=>{
    document.getElementById('lb-page').style.display = 'none';
  });
  document.getElementById('lb-page-signup-btn')?.addEventListener('click',()=>{
    document.getElementById('lb-page').style.display = 'none';
    setAuthMode('signup'); openModal('auth-modal');
  });

  /* Auth form */
  document.getElementById('auth-submit').addEventListener('click',handleAuth);
  document.getElementById('auth-toggle').addEventListener('click',()=>setAuthMode(authMode==='signup'?'login':'signup'));
  document.getElementById('auth-logout').addEventListener('click',handleLogout);
  document.getElementById('auth-username')?.addEventListener('keydown',e=>{if(e.key==='Enter')document.getElementById('auth-password').focus();});
  document.getElementById('auth-password')?.addEventListener('keydown',e=>{if(e.key==='Enter')handleAuth();});

  /* Results modal sign-up button */
  document.getElementById('results-signup-btn')?.addEventListener('click',()=>{
    closeModal('results-modal'); setAuthMode('signup'); openModal('auth-modal');
  });

  /* Post-game week view CTA buttons */
  document.getElementById('wv-results-btn')?.addEventListener('click',()=>{
    if (gs.gameOver && gs.humanGuess !== null) {
      const outcome = gs.humanDist < aiData.distance ? 'human_wins'
                    : gs.humanDist > aiData.distance ? 'ai_wins' : 'tie';
      showResults(gs.humanGuess, gs.humanDist, aiData.distance, outcome);
    }
  });
  document.getElementById('wv-lb-btn')?.addEventListener('click',()=>showLeaderboardPage());
  document.getElementById('wv-signup-btn')?.addEventListener('click',()=>{
    setAuthMode('signup'); openModal('auth-modal');
  });

  /* Guess input */
  $('#guess-btn').addEventListener('click',handleGuess);
  $('#guess-input').addEventListener('keydown',e=>{if(e.key==='Enter')handleGuess();});

  if (gs.gameOver) { restoreGame(); }
}

document.addEventListener('DOMContentLoaded', init);
