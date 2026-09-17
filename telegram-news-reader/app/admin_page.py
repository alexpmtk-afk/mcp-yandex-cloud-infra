from __future__ import annotations

ADMIN_PAGE = r'''<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Telegram Reader — управление чатами</title>
<style>
body{font-family:system-ui,-apple-system,Segoe UI,sans-serif;max-width:980px;margin:32px auto;padding:0 16px;color:#1f2328}
h1{font-size:24px;margin-bottom:6px}.muted{color:#667085;line-height:1.45}.bar{display:flex;gap:10px;flex-wrap:wrap;margin:18px 0}
input,button{font:inherit;padding:9px 11px;border:1px solid #cfd4dc;border-radius:8px}input[type=search]{flex:1;min-width:240px}
button{cursor:pointer;background:#fff}button.primary{background:#1677ff;color:#fff;border-color:#1677ff}button.danger{color:#b42318}.status{margin:10px 0;font-weight:600}
.list{border:1px solid #e2e5e9;border-radius:10px;overflow:hidden}.row{display:grid;grid-template-columns:34px 1fr auto;gap:8px;align-items:center;padding:10px 12px;border-bottom:1px solid #eef0f2}.row:last-child{border-bottom:0}
.title{font-weight:600}.meta{font-size:12px;color:#667085}.pill{font-size:12px;background:#f2f4f7;padding:3px 7px;border-radius:999px}.hidden{display:none}
.notice{background:#f8fafc;border:1px solid #e2e8f0;border-radius:9px;padding:10px 12px;margin:14px 0;font-size:14px;line-height:1.45}
</style></head><body>
<h1>Telegram Reader — управление чатами</h1>
<div class="muted">Галочка означает: ChatGPT разрешено читать этот Telegram-чат через Reader. Снятая галочка запрещает дальнейшее чтение. Изменения начинают действовать после нажатия «Сохранить изменения».</div>
<div class="notice">Список сохраняется постоянно в защищённом хранилище Yandex Cloud и применяется ко всем новым запросам Reader, в том числе после его перезапуска.</div>
<div id="auth" class="bar"><input id="key" type="password" autocomplete="current-password" placeholder="Ключ управления"><button class="primary" onclick="login()">Открыть список</button></div>
<div id="app" class="hidden">
  <div class="bar"><input id="q" type="search" placeholder="Поиск по названию" oninput="render()"><button onclick="selectAll()">Выбрать все</button><button onclick="selectNone()">Снять все</button><button onclick="reload()">Обновить</button><button class="primary" onclick="save()">Сохранить изменения</button><button class="danger" onclick="forgetKey()">Забыть ключ на этом компьютере</button></div>
  <div id="status" class="status"></div><div id="list" class="list"></div>
</div>
<script>
let token=localStorage.getItem('tg_admin_token')||'';let dialogs=[];let selected=new Set();
const qp=new URLSearchParams(location.search);if(qp.get('token')){token=qp.get('token').trim();if(token){localStorage.setItem('tg_admin_token',token)}history.replaceState({},'',location.pathname)}
async function api(path,opt={}){const c=new AbortController();const timer=setTimeout(()=>c.abort(),65000);try{opt.signal=c.signal;opt.headers={...(opt.headers||{}),'X-Admin-Token':token,'Content-Type':'application/json'};const r=await fetch(path,opt);if(r.status===401)throw new Error('Ключ управления не принят. Откройте персональную ссылку заново или введите действующий ключ.');if(!r.ok){let text=await r.text();if(r.status===400&&text.includes('AT_LEAST_ONE_CHAT_REQUIRED'))throw new Error('Нужно оставить разрешённым хотя бы один чат.');if(r.status===504)throw new Error('Telegram не ответил вовремя. Нажмите «Обновить» ещё раз.');if(r.status===503)throw new Error('Reader временно не может подключиться к Telegram или защищённому хранилищу.');throw new Error(text||('HTTP '+r.status))}return r.json()}catch(e){if(e.name==='AbortError')throw new Error('Загрузка заняла слишком много времени. Повторите попытку.');throw e}finally{clearTimeout(timer)}}
async function login(){token=document.getElementById('key').value.trim();if(!token){setStatus('Введите ключ управления.',true);return}localStorage.setItem('tg_admin_token',token);await reload()}
async function reload(){try{setStatus('Загружаю список Telegram-чатов…');const data=await api('/api/admin/dialogs');dialogs=data.dialogs;selected=new Set(data.selected);document.getElementById('auth').classList.add('hidden');document.getElementById('app').classList.remove('hidden');render();setStatus('Разрешено: '+selected.size+' из '+dialogs.length)}catch(e){document.getElementById('auth').classList.remove('hidden');document.getElementById('app').classList.add('hidden');setStatus(e.message,true)}}
function render(){const q=document.getElementById('q').value.toLowerCase();const box=document.getElementById('list');box.innerHTML='';for(const d of dialogs.filter(x=>(x.title||'').toLowerCase().includes(q))){const row=document.createElement('label');row.className='row';const cb=document.createElement('input');cb.type='checkbox';cb.checked=selected.has(d.chat_id);cb.onchange=()=>{cb.checked?selected.add(d.chat_id):selected.delete(d.chat_id);setStatus('Выбрано: '+selected.size+' из '+dialogs.length)};const mid=document.createElement('div');mid.innerHTML='<div class="title"></div><div class="meta"></div>';mid.children[0].textContent=d.title||String(d.chat_id);mid.children[1].textContent=(d.username?'@'+d.username+' · ':'')+'ID '+d.chat_id;const pill=document.createElement('span');pill.className='pill';pill.textContent=d.type||'chat';row.append(cb,mid,pill);box.append(row)}}
function selectAll(){selected=new Set(dialogs.map(d=>d.chat_id));render();setStatus('Выбрано: '+selected.size+' из '+dialogs.length)}
function selectNone(){selected.clear();render();setStatus('Выбрано: 0 из '+dialogs.length+'. Для сохранения нужно выбрать хотя бы один чат.',true)}
async function save(){if(selected.size<1){setStatus('Нельзя сохранить пустой список. Выберите хотя бы один Telegram-чат.',true);return}try{setStatus('Сохраняю…');const r=await api('/api/admin/whitelist',{method:'POST',body:JSON.stringify({chat_ids:[...selected]})});setStatus('Сохранено. ChatGPT разрешено читать '+r.allowed_chats+' чат(ов). Изменение уже действует.')}catch(e){setStatus(e.message,true)}}
function forgetKey(){localStorage.removeItem('tg_admin_token');token='';document.getElementById('key').value='';document.getElementById('app').classList.add('hidden');document.getElementById('auth').classList.remove('hidden');setStatus('Ключ удалён только из этого браузера. Чтобы войти снова, откройте персональную ссылку или введите ключ.')}
function setStatus(s,err=false){const e=document.getElementById('status');e.textContent=s;e.style.color=err?'#b42318':'#344054'}
if(token)reload();
</script></body></html>'''