from __future__ import annotations

ADMIN_PAGE = r'''<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Telegram Reader — управление чатами</title>
<style>
body{font-family:system-ui,-apple-system,Segoe UI,sans-serif;max-width:980px;margin:32px auto;padding:0 16px;color:#1f2328}
h1{font-size:24px;margin-bottom:6px}.muted{color:#667085}.bar{display:flex;gap:10px;flex-wrap:wrap;margin:18px 0}
input,button{font:inherit;padding:9px 11px;border:1px solid #cfd4dc;border-radius:8px}input[type=search]{flex:1;min-width:240px}
button{cursor:pointer;background:#fff}button.primary{background:#1677ff;color:#fff;border-color:#1677ff}.status{margin:10px 0;font-weight:600}
.list{border:1px solid #e2e5e9;border-radius:10px;overflow:hidden}.row{display:grid;grid-template-columns:34px 1fr auto;gap:8px;align-items:center;padding:10px 12px;border-bottom:1px solid #eef0f2}.row:last-child{border-bottom:0}
.title{font-weight:600}.meta{font-size:12px;color:#667085}.pill{font-size:12px;background:#f2f4f7;padding:3px 7px;border-radius:999px}.hidden{display:none}
</style></head><body>
<h1>Telegram Reader — управление чатами</h1>
<div class="muted">Отметьте чаты, которые Reader должен читать. Снятая галочка отключает дальнейшее чтение.</div>
<div id="auth" class="bar"><input id="key" type="password" placeholder="Ключ управления"><button class="primary" onclick="login()">Открыть список</button></div>
<div id="app" class="hidden"><div class="bar"><input id="q" type="search" placeholder="Поиск по названию" oninput="render()"><button onclick="selectNone()">Снять все</button><button onclick="reload()">Обновить</button><button class="primary" onclick="save()">Сохранить изменения</button></div><div id="status" class="status"></div><div id="list" class="list"></div></div>
<script>
let token=sessionStorage.getItem('tg_admin_token')||'';let dialogs=[];let selected=new Set();
const qp=new URLSearchParams(location.search);if(qp.get('token')){token=qp.get('token');sessionStorage.setItem('tg_admin_token',token);history.replaceState({},'',location.pathname)}
async function api(path,opt={}){const c=new AbortController();const timer=setTimeout(()=>c.abort(),65000);try{opt.signal=c.signal;opt.headers={...(opt.headers||{}),'X-Admin-Token':token,'Content-Type':'application/json'};const r=await fetch(path,opt);if(r.status===401)throw new Error('Неверный ключ управления');if(!r.ok){let text=await r.text();if(r.status===504)throw new Error('Telegram не ответил вовремя. Нажмите «Обновить» ещё раз.');if(r.status===503)throw new Error('Reader временно не может подключиться к Telegram.');throw new Error(text||('HTTP '+r.status))}return r.json()}catch(e){if(e.name==='AbortError')throw new Error('Загрузка заняла слишком много времени. Повторите попытку.');throw e}finally{clearTimeout(timer)}}
async function login(){token=document.getElementById('key').value.trim();sessionStorage.setItem('tg_admin_token',token);await reload()}
async function reload(){try{setStatus('Загружаю список…');const data=await api('/api/admin/dialogs');dialogs=data.dialogs;selected=new Set(data.selected);document.getElementById('auth').classList.add('hidden');document.getElementById('app').classList.remove('hidden');render();setStatus('Активно: '+selected.size+' из '+dialogs.length)}catch(e){document.getElementById('auth').classList.remove('hidden');setStatus(e.message,true)}}
function render(){const q=document.getElementById('q').value.toLowerCase();const box=document.getElementById('list');box.innerHTML='';for(const d of dialogs.filter(x=>(x.title||'').toLowerCase().includes(q))){const row=document.createElement('label');row.className='row';const cb=document.createElement('input');cb.type='checkbox';cb.checked=selected.has(d.chat_id);cb.onchange=()=>{cb.checked?selected.add(d.chat_id):selected.delete(d.chat_id);setStatus('Выбрано: '+selected.size)};const mid=document.createElement('div');mid.innerHTML='<div class="title"></div><div class="meta"></div>';mid.children[0].textContent=d.title||String(d.chat_id);mid.children[1].textContent=(d.username?'@'+d.username+' · ':'')+'ID '+d.chat_id;const pill=document.createElement('span');pill.className='pill';pill.textContent=d.type||'chat';row.append(cb,mid,pill);box.append(row)}}
function selectNone(){selected.clear();render();setStatus('Выбрано: 0')}
async function save(){try{setStatus('Сохраняю…');const r=await api('/api/admin/whitelist',{method:'POST',body:JSON.stringify({chat_ids:[...selected]})});setStatus('Сохранено. Активных чатов: '+r.allowed_chats)}catch(e){setStatus(e.message,true)}}
function setStatus(s,err=false){const e=document.getElementById('status');e.textContent=s;e.style.color=err?'#b42318':'#344054'}
if(token)reload();
</script></body></html>'''
