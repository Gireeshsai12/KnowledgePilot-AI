'use strict';
const get = (id) => document.getElementById(id);
let token = sessionStorage.getItem('kp-session');
let spaces = [];
let workspace;

async function api(path, options = {}) {
  const headers = new Headers(options.headers);
  if (token) headers.set('Authorization', 'Bearer ' + token);
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json');
  const response = await fetch('/api/' + path, {...options, headers});
  const data = await response.json();
  if (!response.ok) {
    if (response.status === 401 && token) setSession(null);
    const detail = typeof data.detail === 'string' ? data.detail : 'Check the input and try again.';
    throw new Error(detail);
  }
  return data;
}
function setSession(value) {
  token = value;
  if (value) sessionStorage.setItem('kp-session', value);
  else sessionStorage.removeItem('kp-session');
  get('auth').hidden = Boolean(value);
  get('dashboard').hidden = !value;
  get('logout').hidden = !value;
  if (!value) {
    get('results').replaceChildren();
    get('history-list').replaceChildren();
    get('documents').replaceChildren();
    if (get('preview').open) get('preview').close();
    get('preview-text').textContent = '';
  }
}
function show(message) {
  get('status').textContent = message;
}
function run(action) {
  return async (event) => {
    event?.preventDefault();
    show('');
    const control = event?.submitter || (event?.currentTarget instanceof HTMLButtonElement ? event.currentTarget : null);
    if (control) control.disabled = true;
    try { await action(event); }
    catch (error) { show(error.message); }
    finally { if (control) control.disabled = false; }
  };
}
function route(path) {
  return 'workspaces/' + workspace + '/' + path;
}
function json(body, method = 'POST') {
  return {method, body: JSON.stringify(body)};
}
function add(parent, tag, text) {
  const node = document.createElement(tag);
  node.textContent = text;
  parent.append(node);
  return node;
}
function choices(select, items, placeholder) {
  select.replaceChildren();
  if (placeholder) select.add(new Option(placeholder, ''));
  for (const item of items) select.add(new Option(item.title || item.name, item.id));
}
async function loadSpaces(selected) {
  spaces = await api('workspaces');
  choices(get('workspace'), spaces);
  if (selected) get('workspace').value = selected;
  await selectWorkspace();
}
async function selectWorkspace() {
  workspace = Number(get('workspace').value);
  get('results').replaceChildren();
  get('history-list').replaceChildren();
  await loadDocuments();
}
async function loadDocuments() {
  const active = workspace;
  const docs = await api(route('documents'));
  if (active !== workspace) return;
  const role = spaces.find((item) => item.id === workspace)?.role;
  get('upload').hidden = role === 'viewer';
  get('sharing').hidden = role !== 'owner';
  const list = get('documents');
  list.replaceChildren();
  if (!docs.length) add(list, 'li', 'No indexed documents');
  docs.forEach((item) => {
    const row = add(list, 'li', item.title + ' · ' + item.chunks + ' chunks');
    if (role === 'owner' || role === 'editor') {
      const button = add(row, 'button', 'Delete');
      button.className = 'secondary';
      button.addEventListener('click', run(async () => {
        if (!window.confirm('Delete ' + item.title + '?')) return;
        await api(route('documents/' + item.id), {method: 'DELETE'});
        await loadDocuments();
        show('Document deleted.');
      }));
    }
  });
  choices(get('filter'), docs, 'All documents');
  choices(get('first'), docs, 'Choose a document');
  choices(get('second'), docs, 'Choose a document');
}
function source(parent, item, scope) {
  const button = add(parent, 'button', (item.citation ? '[' + item.citation + '] ' : '') + item.title + ' · ' + item.section);
  button.className = 'secondary';
  button.addEventListener('click', run(async () => {
    const data = await api('workspaces/' + scope + '/chunks/' + item.id);
    get('preview-title').textContent = data.title + ' · ' + data.section;
    get('preview-text').textContent = data.text;
    get('preview').showModal();
  }));
}
function renderAnswer(parent, result, scope, title = 'Extractive answer') {
  const card = add(parent, 'article', '');
  add(card, 'h3', title);
  add(card, 'p', result.answer);
  result.citations.forEach((item) => source(card, item, scope));
}
get('auth-form').addEventListener('submit', run(async (event) => {
  const payload = Object.fromEntries(new FormData(event.target));
  if (event.submitter?.value === 'register') await api('register', json(payload));
  const signedIn = await api('login', json(payload));
  setSession(signedIn.access_token);
  event.target.reset();
  await loadSpaces();
}));
get('logout').addEventListener('click', run(async () => {
  await api('logout', {method: 'POST'});
  setSession(null);
}));
get('new-workspace').addEventListener('submit', run(async (event) => {
  const space = await api('workspaces', json(Object.fromEntries(new FormData(event.target))));
  event.target.reset();
  await loadSpaces(space.id);
}));
get('workspace').addEventListener('change', run(selectWorkspace));
get('demo').addEventListener('click', run(async () => {
  const response = await api(route('demo'), {method:'POST'});
  await loadDocuments();
  show(response.filter((item) => item.status === 'indexed').length + ' sample documents indexed.');
}));
get('upload').addEventListener('submit', run(async (event) => {
  const body = new FormData(event.target);
  const strategy = body.get('strategy');
  body.delete('strategy');
  const result = await api(route('documents?strategy=' + encodeURIComponent(strategy)), {method:'POST', body});
  event.target.reset();
  await loadDocuments();
  show(result.status === 'duplicate' ? 'This document is already indexed.' : 'Indexed ' + result.chunks + ' chunks.');
}));
get('share').addEventListener('submit', run(async (event) => {
  await api(route('members'), json(Object.fromEntries(new FormData(event.target)), 'PUT'));
  show('Workspace access saved.');
}));
get('research').addEventListener('submit', run(async (event) => {
  const {question, document_id, mode} = Object.fromEntries(new FormData(event.target));
  const scope = workspace;
  const output = get('results');
  output.replaceChildren();
  if (event.submitter?.value === 'search') {
    const params = new URLSearchParams({q:question,mode});
    if (document_id) params.set('document_id', document_id);
    const results = await api(route('search?' + params));
    if (scope !== workspace) return;
    if (!results.length) add(output, 'p', 'No matching sources.');
    for (const result of results) {
      const card = add(output, 'article', '');
      add(card, 'p', result.text.slice(0, 360));
      add(card, 'p', 'Relevance score ' + result.score);
      source(card, result, scope);
    }
  } else {
    const result = await api(route('chat'), json({question, document_id: Number(document_id) || null}));
    if (scope === workspace) renderAnswer(output, result, scope);
  }
}));
get('compare').addEventListener('submit', run(async (event) => {
  const {first, second, topic} = Object.fromEntries(new FormData(event.target));
  const scope = workspace;
  const response = await api(route('compare'), json({first:Number(first),second:Number(second),topic}));
  if (scope !== workspace) return;
  get('results').replaceChildren();
  response.documents.forEach((result) => renderAnswer(get('results'), result, scope, result.title));
}));
get('history').addEventListener('click', run(async () => {
  const scope = workspace;
  const records = await api(route('history'));
  if (scope !== workspace) return;
  const parent = get('history-list');
  parent.replaceChildren();
  if (!records.length) add(parent, 'p', 'No questions yet.');
  records.forEach((item) => renderAnswer(parent, item.response, scope, item.question));
}));
setSession(token);
if (token) loadSpaces().catch((error) => show(error.message));
