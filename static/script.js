const monthNames = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
let monthlySales = [55, 72, 90, 98, 124, 142, 142, 158, 173, 191, 212, 240];
let currentMode = 'text';
let toastTimer;

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

function showToast(message) {
  const toast = $('#toast');
  toast.textContent = message;
  toast.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove('show'), 2300);
}

function renderChart() {
  const bars = $('#bars');
  const labels = $('#xLabels');
  const max = Math.max(250, ...monthlySales);
  bars.innerHTML = monthlySales.map((value, i) =>
    `<div class="bar" style="height:${Math.max(2, value / max * 100)}%" title="${monthNames[i]}: ${value}K" aria-label="${monthNames[i]} sales ${value} thousand"></div>`
  ).join('');
  labels.innerHTML = monthNames.map((month) => `<span>${month}</span>`).join('');
  $('#salesTable').innerHTML = monthlySales.map((value, i) => `<tr><td>${monthNames[i]} 2026</td><td>${formatSales(value * 1000)}</td></tr>`).join('');
}

function formatSales(value) {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(value);
}

function summarizeQuery(query) {
  const q = query.toLowerCase();
  if (q.includes('month') && (q.includes('sale') || q.includes('revenue'))) {
    return {
      reply: 'Here is the monthly trend from the demo dataset. The chart and table have been refreshed for this example.',
      title: 'Total sales by month (2026)',
      insights: [
        `Sales are highest in ${monthNames[monthlySales.indexOf(Math.max(...monthlySales))]} at around ${Math.max(...monthlySales)}K.`,
        'The demo data shows an overall upward trend across the year.',
        'Use a connected database for real business figures.'
      ]
    };
  }
  if (q.includes('highest') || q.includes('top')) {
    const index = monthlySales.indexOf(Math.max(...monthlySales));
    return { reply: `In this demo data, ${monthNames[index]} has the highest monthly sales at about ${monthlySales[index]}K.`, title: 'Highest monthly sales (demo)', insights: [`${monthNames[index]} is the highest month in the sample.`, 'The values are illustrative and not connected to a live database.', 'Connect your data source to calculate actual rankings.'] };
  }
  if (q.includes('average') || q.includes('avg')) {
    const avg = monthlySales.reduce((a, b) => a + b, 0) / monthlySales.length;
    return { reply: `The average monthly sales in the demo dataset are around ${Math.round(avg)}K.`, title: 'Average monthly sales (demo)', insights: [`Average monthly sales: approximately ${Math.round(avg)}K.`, 'The result is calculated from the illustrative chart values.', 'Connect a database to analyze your actual figures.'] };
  }
  return { reply: 'I have recorded your question in this UI prototype. To return accurate results, connect a database and add a text-to-SQL backend for this type of query.', title: 'Demo results', insights: ['This interface currently uses sample data only.', 'No live SQL query has been executed.', 'A backend connection is needed for accurate answers.'] };
}

function addMessage(query, result) {
  const conversation = $('#conversation');
  const user = document.createElement('div');
  user.className = 'message user-message';
  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  bubble.textContent = query;
  const chip = document.createElement('span');
  chip.className = 'user-chip';
  chip.textContent = 'U';
  user.append(bubble, chip);
  const assistant = document.createElement('div');
  assistant.className = 'message assistant-message';
  const bot = document.createElement('span');
  bot.className = 'bot-chip';
  bot.textContent = '✦';
  const answer = document.createElement('div');
  answer.className = 'bubble assistant-bubble';
  answer.textContent = result.reply;
  assistant.append(bot, answer);
  conversation.append(user, assistant);
  conversation.scrollTop = conversation.scrollHeight;
  $('#chartTitle').textContent = result.title;
  $('#insightsList').innerHTML = result.insights.map(item => `<li>${item}</li>`).join('');
  $('#sqlCode').textContent = '-- Demo mode: SQL is not executed.\n-- Connect a database and secure query backend to enable this.\nSELECT month, SUM(total_amount) AS total_sales\nFROM sales\nGROUP BY month\nORDER BY month;';
}

$('#queryForm').addEventListener('submit', (event) => {
  event.preventDefault();
  const input = $('#queryInput');
  const query = input.value.trim();
  if (!query) { showToast('Enter a question about your data first.'); input.focus(); return; }
  const result = summarizeQuery(query);
  addMessage(query, result);
  input.value = '';
  showToast('Demo response generated. No live query was run.');
});

$$('.mode').forEach(button => button.addEventListener('click', () => {
  currentMode = button.dataset.mode;
  $$('.mode').forEach(item => {
    const active = item === button;
    item.classList.toggle('active', active);
    item.setAttribute('aria-selected', String(active));
  });
  if (currentMode === 'voice') {
    $('#queryInput').placeholder = 'Tap the microphone to speak...';
    $('#micButton').focus();
    showToast('Voice mode selected. Tap the microphone to start.');
  } else {
    $('#queryInput').placeholder = 'Type your question here...';
    $('#queryInput').focus();
  }
}));

$('#micButton').addEventListener('click', () => {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    showToast('Voice input is not supported in this browser. Try Chrome.');
    return;
  }
  const recognition = new SpeechRecognition();
  recognition.lang = 'en-IN';
  recognition.interimResults = false;
  recognition.maxAlternatives = 1;
  $('#micButton').textContent = '…';
  recognition.onresult = (event) => {
    $('#queryInput').value = event.results[0][0].transcript;
    $('#queryInput').focus();
    showToast('Voice captured. Press send to continue.');
  };
  recognition.onerror = () => showToast('Could not recognize speech. Please try again.');
  recognition.onend = () => { $('#micButton').textContent = '🎙'; };
  try { recognition.start(); } catch { $('#micButton').textContent = '🎙'; showToast('Microphone could not start. Check browser permission.'); }
});

$$('.view-button').forEach(button => button.addEventListener('click', () => {
  const view = button.dataset.resultView;
  $$('.view-button').forEach(item => {
    const active = item === button;
    item.classList.toggle('active', active);
    item.setAttribute('aria-selected', String(active));
  });
  $('#chartView').classList.toggle('hidden', view !== 'chart');
  $('#tableView').classList.toggle('hidden', view !== 'table');
}));

$('#copySql').addEventListener('click', async () => {
  const sql = $('#sqlCode').textContent;
  try {
    await navigator.clipboard.writeText(sql);
    showToast('SQL copied.');
  } catch {
    const temp = document.createElement('textarea');
    temp.value = sql; document.body.appendChild(temp); temp.select();
    const copied = document.execCommand('copy'); temp.remove();
    showToast(copied ? 'SQL copied.' : 'Could not copy SQL.');
  }
});

$('#speakButton').addEventListener('click', () => {
  if (!('speechSynthesis' in window)) { showToast('Audio playback is not supported in this browser.'); return; }
  window.speechSynthesis.cancel();
  const insightText = [...$('#insightsList').querySelectorAll('li')].map(li => li.textContent).join('. ');
  const utterance = new SpeechSynthesisUtterance(`Here are your key insights. ${insightText}`);
  utterance.lang = 'en-IN';
  utterance.onstart = () => { $('#audioStatus').textContent = 'Speaking…'; $('#speakButton').textContent = 'Ⅱ'; };
  utterance.onend = () => { $('#audioStatus').textContent = 'Read aloud'; $('#speakButton').textContent = '▶'; };
  utterance.onerror = () => { $('#audioStatus').textContent = 'Read aloud'; $('#speakButton').textContent = '▶'; };
  window.speechSynthesis.speak(utterance);
});
$('#stopSpeak').addEventListener('click', () => {
  if ('speechSynthesis' in window) window.speechSynthesis.cancel();
  $('#audioStatus').textContent = 'Read aloud'; $('#speakButton').textContent = '▶';
});

$('#themeToggle').addEventListener('click', () => {
  document.body.classList.toggle('dark');
  const dark = document.body.classList.contains('dark');
  $('#themeToggle').textContent = dark ? '☀' : '☾';
  $('#themeToggle').title = dark ? 'Switch to light mode' : 'Switch to dark mode';
});

$$('.nav-item').forEach(button => button.addEventListener('click', () => {
  $$('.nav-item').forEach(item => item.classList.toggle('active', item === button));
  const view = button.dataset.view;
  if (view === 'Chat') return;
  const messages = {
    'History': 'Chat history will appear here once conversation storage is connected.',
    'Data Sources': 'Database connections can be configured here when a backend is added.',
    'Settings': 'Basic preferences are available in this prototype. Use the moon icon to switch themes.'
  };
  showToast(messages[view] || `${view} selected.`);
}));

renderChart();
