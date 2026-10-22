const articles = [...document.querySelectorAll('article')];
const selection = document.querySelector('#selection');
document.querySelector('#viewport').addEventListener('change', event => document.body.classList.toggle('phone', event.target.value === 'phone'));
document.querySelectorAll('.choose').forEach(button => button.addEventListener('click', () => {
  articles.forEach(article => article.classList.toggle('selected', article === button.closest('article')));
  selection.value = `选择「${button.dataset.name}」。按这个方向完成页面，保留已确认的内容与交互。`;
  document.querySelector('#status').textContent = '已选择，可复制结果。';
}));
document.querySelector('#copy').addEventListener('click', async () => {
  if (!selection.value) { document.querySelector('#status').textContent = '先选择一个方向。'; return; }
  try { await navigator.clipboard.writeText(selection.value); document.querySelector('#status').textContent = '已复制。'; }
  catch { selection.focus(); selection.select(); document.querySelector('#status').textContent = '浏览器未授权剪贴板，请手动复制所选文字。'; }
});
document.addEventListener('keydown', event => {
  if (!['ArrowLeft', 'ArrowRight'].includes(event.key) || /INPUT|TEXTAREA|SELECT/.test(event.target.tagName)) return;
  const current = articles.indexOf(document.activeElement.closest('article'));
  const next = articles[Math.max(0, Math.min(articles.length - 1, current + (event.key === 'ArrowRight' ? 1 : -1)))];
  if (next) { event.preventDefault(); next.querySelector('button').focus(); next.scrollIntoView({block:'nearest', inline:'center'}); }
});
