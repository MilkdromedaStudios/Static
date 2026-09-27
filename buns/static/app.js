'use strict';
const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
const icons = {
  chat:'M4 4h16v12H9l-5 4V4Z', folder:'M3 6h7l2 2h9v12H3V6Z',
  grid:'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z',
  sliders:'M4 6h16 M4 12h16 M4 18h16 M8 3v6 M16 9v6 M10 15v6',
  home:'m3 10 9-7 9 7 M5 9v12h14V9 M9 21v-8h6v8',
  leaf:'M20 3C8 3 3 8 5 15s13 6 15-12Z M4 21 15 10',
  globe:'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0 M3 12h18 M12 3c-5 6-5 12 0 18 M12 3c5 6 5 12 0 18',
  file:'M5 3h9l5 5v13H5V3Z M14 3v6h5 M8 13h8 M8 17h5',
  bag:'M5 7h14l1 14H4L5 7Z M9 8V6a3 3 0 0 1 6 0v2',
  cube:'m12 3 9 5v9l-9 5-9-5V8l9-5Z M3 8l9 5 9-5 M12 13v9',
  pen:'m4 16 12-12 4 4L8 20H4v-4Z M13 7l4 4',
  clip:'m8 12 7-7a4 4 0 0 1 6 6L10 22a6 6 0 0 1-8-8L13 3 M7 15l9-9',
  shield:'m12 3 9 4c0 7-3 11-9 14C6 18 3 14 3 7l9-4Z m-4 9 3 3 5-6',
  activity:'M3 12h4l3-8 4 16 3-8h4'
};
function fillIcons(root=document){root.querySelectorAll('[data-icon]').forEach(el=>{
  const path=icons[el.dataset.icon]; if(!path)return;
  const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');
  svg.setAttribute('viewBox','0 0 24 24'); svg.setAttribute('fill','none'); svg.setAttribute('stroke','currentColor');svg.setAttribute('aria-hidden','true');
  const p=document.createElementNS(svg.namespaceURI,'path');p.setAttribute('d',path);p.setAttribute('stroke-linecap','round');p.setAttribute('stroke-linejoin','round');svg.append(p);el.replaceChildren(svg);
});}
function el(tag, cls, text){const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n;}
const state={conversation:null,run:null,after:0,poll:null,settings:null,keys:{},attachments:[],view:'chat',conversations:[],generation:0,token:sessionStorage.getItem('buns-token')||'',busy:false};
let toastTimer;
function toast(message){$('#toast').textContent=message;$('#toast').classList.remove('hidden');clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('#toast').classList.add('hidden'),6000);}
async function api(path, options={}){
  const headers={'X-Buns-Client':'web',...(state.token?{Authorization:'Bearer '+state.token}:{}),...options.headers};
  if(options.body && !(options.body instanceof FormData))headers['Content-Type']='application/json';
  const r=await fetch('/api'+path,{...options,headers});
  if(r.status===401){if(!$('#auth-dialog').open)$('#auth-dialog').showModal();throw new Error('Workspace is locked. Enter its access token.');}
  if(!r.ok){let body;try{body=await r.json();}catch{body={detail:'Request failed ('+r.status+')'};}
    throw new Error(typeof body.detail==='string'?body.detail:JSON.stringify(body.detail));}
  return r.json();
}
function action(fn){return async (...args)=>{try{await fn(...args);}catch(e){toast(e.message);}};}
function money(x){return '$'+Number(x||0).toFixed(Number(x)>0&&Number(x)<.01?4:2);}
function safeURL(url){return /^https?:\/\//i.test(url)||/^\/api\/artifacts\/[a-f0-9]{32}\/download$/.test(url);}
async function download(id,name){
  const r=await fetch('/api/artifacts/'+id+'/download',{headers:state.token?{Authorization:'Bearer '+state.token}:{}});
  if(!r.ok)throw new Error('Could not download the file. Unlock the workspace and retry.');
  const url=URL.createObjectURL(await r.blob());const a=el('a');a.href=url;a.download=name||'buns-file';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
// Minimal DOM-only Markdown. Model text is never interpreted as HTML.
function inline(parent,text){
  const rx=/\[([^\]]+)\]\(([^\s)]+)\)|\*\*([^*]+)\*\*|`([^`]+)`/g;let last=0,m;
  while((m=rx.exec(text))){parent.append(document.createTextNode(text.slice(last,m.index)));
    if(m[1]&&safeURL(m[2])){const a=el('a','',m[1]);a.href=m[2];
      if(m[2].startsWith('/api/artifacts/')){const id=m[2].split('/')[3],name=m[1];a.onclick=action(async e=>{e.preventDefault();await download(id,name);});}
      else {a.target='_blank';a.rel='noopener noreferrer';}parent.append(a);
    }else if(m[3])parent.append(el('strong','',m[3]));else if(m[4])parent.append(el('code','',m[4]));else parent.append(document.createTextNode(m[0]));last=rx.lastIndex;
  }parent.append(document.createTextNode(text.slice(last)));
}
function markdown(parent,text){let code=false,lines=[];for(const line of text.split('\n')){
  if(line.startsWith('```')){if(code){parent.append(el('pre','',lines.join('\n')));lines=[];}code=!code;continue;}
  if(code){lines.push(line);continue;}if(!line.trim())continue;
  const h=line.match(/^(#{1,3})\s+(.*)/);const n=el(h?(h[1].length===1?'h2':'h3'):'p');inline(n,h?h[2]:line);parent.append(n);
}if(lines.length)parent.append(el('pre','',lines.join('\n')));}
function showMessages(messages){const root=$('#messages');root.replaceChildren();$('#welcome').classList.toggle('hidden',messages.length>0);
  for(const msg of messages){const wrap=el('article','message '+msg.role);const av=el('div','message-avatar');
    if(msg.role==='assistant'){const img=el('img');img.src='/static/bun.svg';img.alt='';av.append(img);}else av.textContent='Y';
    const body=el('div','message-body');body.append(el('div','message-title',msg.role==='assistant'?'Buns':'You'));markdown(body,msg.content);wrap.append(av,body);root.append(wrap);
  }
}
function scrollBottom(){$('#conversation-scroll').scrollTop=$('#conversation-scroll').scrollHeight;}
function setBusy(busy){state.busy=busy;$('#send').disabled=busy;$('#stop').classList.toggle('hidden',!busy);$('#agent-state').textContent=busy?'Working':'Ready';}
function resetRun(){clearTimeout(state.poll);state.generation++;state.run=null;state.after=0;setBusy(false);$('#events').replaceChildren(el('div','idle-event','Ready when you are.'));$('#plan').replaceChildren(el('p','empty-small','Big tasks become small steps. Your plan will appear here.'));$('#plan-count').textContent='—';$('#run-cost').textContent='$0.00';$('#run-banner').classList.add('hidden');$('#approval-panel').replaceChildren();}
async function refreshNav(){state.conversations=await api('/conversations');const recent=$('#recent');recent.replaceChildren();
  if(!state.conversations.length)recent.append(el('p','empty-small','A fresh start. Your conversations will live here.'));
  for(const c of state.conversations){const b=el('button',c.id===state.conversation?'selected':'',c.title);b.title=c.title;b.onclick=action(()=>loadConversation(c.id));recent.append(b);}
  const all=await api('/artifacts');$('#file-count').textContent=all.length;
}
async function ensureConversation(){if(!state.conversation){const c=await api('/conversations',{method:'POST',body:JSON.stringify({title:'New conversation'})});state.conversation=c.id;}return state.conversation;}
async function newConversation(){resetRun();state.conversation=null;state.attachments=[];renderAttachments();showMessages([]);$('#page-title').textContent='New conversation';$('#prompt').value='';switchView('chat');await refreshNav();$('#prompt').focus();}
async function loadConversation(id){resetRun();state.conversation=id;state.attachments=[];renderAttachments();const data=await api('/conversations/'+id);showMessages(data.messages);$('#page-title').textContent=state.conversations.find(c=>c.id===id)?.title||'Conversation';switchView('chat');await refreshNav();if(data.runs[0]){state.run=data.runs[0].id;await pollRun(state.generation);}scrollBottom();}
function switchView(view){state.view=view;$('#sidebar').classList.remove('open');$$('.nav-item').forEach(b=>b.classList.toggle('active',b.dataset.view===view));$('#workspace').classList.toggle('hidden',view!=='chat');$$('.page-view').forEach(n=>n.classList.add('hidden'));if(view!=='chat')$('#'+view+'-view').classList.remove('hidden');if(view==='files')action(loadFiles)();if(view==='skills')action(loadSkills)();if(view==='settings')action(loadSettings)();}
async function send(event){event?.preventDefault();const message=$('#prompt').value.trim();if(!message||state.busy)return;await ensureConversation();
  const run=await api('/conversations/'+state.conversation+'/chat',{method:'POST',body:JSON.stringify({message,mode:$('#mode').value,attachments:state.attachments.map(a=>a.id)})});
  resetRun();state.run=run.id;state.attachments=[];renderAttachments();$('#prompt').value='';setBusy(true);const c=await api('/conversations/'+state.conversation);showMessages(c.messages);await refreshNav();$('#page-title').textContent=message.slice(0,45);scrollBottom();await pollRun(state.generation);
}
function renderEvent(event){const data=event.data;
  if(event.kind==='plan'){const plan=$('#plan');plan.replaceChildren();for(const s of data.steps){const row=el('div','plan-step '+s.status);row.append(el('span','step-dot',s.status==='done'?'✓':s.status==='active'?'•':''),el('span','',s.title));plan.append(row);}$('#plan-count').textContent=data.steps.filter(s=>s.status==='done').length+'/'+data.steps.length;}
  let label='';if(event.kind==='model')label=data.role+' · '+data.name;
  if(event.kind==='tool_start')label='Using '+data.name.replaceAll('_',' ');
  if(event.kind==='tool_done')label='Finished '+data.name.replaceAll('_',' ');
  if(event.kind==='tool_error')label=data.name+': '+data.error;
  if(event.kind==='artifact')label='Created '+data.name;
  if(event.kind==='media')label='Media job submitted';
  if(event.kind==='answer')label='Task finished';
  if(label){const row=el('div','event'+(event.kind==='tool_error'?' error':''));row.append(el('span','','•'),el('span','',label));$('#events').append(row);$('#events').scrollTop=$('#events').scrollHeight;}
}
function renderApprovals(approvals){const root=$('#approval-panel');root.replaceChildren();for(const a of approvals){const card=el('div','approval');card.append(el('h3','','Ready to generate?'),el('p','',a.args.arguments.kind+' · '+a.args.profile.model+' · '+money(a.cost)+' reserved'),el('pre','',a.args.arguments.prompt),el('p','','This calls a paid media provider. The reservation is an estimate; your provider’s price determines the actual charge.'));
  for(const [label,allow] of [['Approve generation',true],['Decline',false]]){const b=el('button',allow?'primary':'secondary',label);b.onclick=action(async()=>{b.disabled=true;try{await api('/approvals/'+a.id,{method:'POST',body:JSON.stringify({allow})});root.replaceChildren();await pollRun(state.generation);}catch(e){b.disabled=false;throw e;}});card.append(b);}root.append(card);}}
async function pollRun(generation){if(!state.run||generation!==state.generation)return;clearTimeout(state.poll);const runId=state.run;
  try{const data=await api('/runs/'+runId+'?after='+state.after);if(generation!==state.generation||runId!==state.run)return;
    for(const event of data.events){renderEvent(event);state.after=event.id;}
    $('#run-cost').textContent=money(data.spent);const busy=['queued','running','awaiting_approval'].includes(data.status);setBusy(busy);$('#agent-state').textContent=data.status==='awaiting_approval'?'Your turn':busy?'Working':'Ready';renderApprovals(data.approvals);
    const banner=$('#run-banner');banner.classList.toggle('hidden',!busy&&!data.error);banner.classList.toggle('error',!!data.error);banner.textContent=data.error||(data.status==='awaiting_approval'?'Buns is waiting for your approval.':'Buns is working… follow the activity on the right.');
    if(!busy){const c=await api('/conversations/'+state.conversation);if(generation!==state.generation)return;showMessages(c.messages);await refreshBudget();await refreshNav();scrollBottom();}
    if(busy||data.events.length===100)state.poll=setTimeout(()=>pollRun(generation),900);
  }catch(e){if(generation===state.generation){toast(e.message);state.poll=setTimeout(()=>pollRun(generation),4000);}}
}
function renderAttachments(){const root=$('#attachments');root.replaceChildren();for(const a of state.attachments){const b=el('button','attachment',a.name+' ×');b.onclick=()=>{state.attachments=state.attachments.filter(x=>x.id!==a.id);renderAttachments();};root.append(b);}}
async function upload(file){if(!file)return;if(file.size>5000000)throw new Error('Files must be under 5 MB');if(state.attachments.length>=5)throw new Error('Attach up to five files');await ensureConversation();const form=new FormData();form.append('file',file);const a=await api('/conversations/'+state.conversation+'/upload',{method:'POST',body:form});state.attachments.push(a);renderAttachments();toast('File attached. Send a message to ask Buns about it.');}
async function refreshBudget(){const data=await api('/settings');state.settings=data.settings;state.keys=data.keys;$('#daily-spend').textContent=money(data.spent_today);$('#daily-budget').textContent='of '+money(data.settings.daily_budget_usd)+' today';$('#budget-bar').max=data.settings.daily_budget_usd||1;$('#budget-bar').value=data.spent_today;}
async function loadFiles(){const [files,jobs]=await Promise.all([api('/artifacts'),api('/media')]);const root=$('#file-grid');root.replaceChildren();$('#file-count').textContent=files.length;
  if(!files.length)root.append(el('div','empty-page','Your next idea could be a file. Ask Buns to create a document, model, image, or video.'));
  for(const file of files){const card=el('article','file-card');const ic=el('span','tile-icon sage');ic.dataset.icon='file';card.append(ic,el('h3','',file.name),el('small','',(file.size/1024).toFixed(1)+' KB · '+new Date(file.created).toLocaleDateString()));const b=el('button','','Download ↓');b.onclick=action(()=>download(file.id,file.name));card.append(b);root.append(card);}
  const jr=$('#media-jobs');jr.replaceChildren();for(const job of jobs){const div=el('div','job');const text=el('div','',job.kind.toUpperCase()+' generation · '+job.status);text.append(el('small','',(job.error||'Job '+job.id.slice(0,8))+(job.prediction_id?' · Provider ID: '+job.prediction_id:'')));div.append(text);if(['starting','processing'].includes(job.status)){const b=el('button','secondary','Cancel');b.onclick=action(async()=>{await api('/media/'+job.id+'/cancel',{method:'POST'});await loadFiles();});div.append(b);}jr.append(div);}fillIcons(root);
}
async function loadSkills(){const skills=await api('/skills');const root=$('#skill-grid');root.replaceChildren();for(const s of skills){const card=el('article','skill-card');const header=el('header');header.append(el('span','skill-category',s.category));const toggle=el('input','switch');toggle.type='checkbox';toggle.checked=s.enabled;toggle.setAttribute('aria-label','Enable '+s.name);toggle.onchange=action(async()=>{try{await refreshBudget();const disabled=new Set(state.settings.disabled_skills);if(toggle.checked)disabled.delete(s.name);else disabled.add(s.name);state.settings.disabled_skills=[...disabled];await api('/settings',{method:'PUT',body:JSON.stringify(state.settings)});toast('Skill updated');}catch(e){toggle.checked=!toggle.checked;throw e;}});header.append(toggle);card.append(header,el('h3','',s.name.replaceAll('_',' ')),el('p','',s.description));if(s.approval)card.append(el('span','skill-category','ASKS BEFORE SPENDING'));root.append(card);}}
function field(label,value,type='text'){const l=el('label','',label),i=el('input');i.type=type;i.value=value??'';l.append(i);return [l,i];}
function modelCard(model){const card=el('details','model-card');card.dataset.modelId=model.id;const summary=el('summary','',model.name);summary.append(el('span','pill',model.local?'LOCAL':'API'));card.append(summary);
  const grid=el('div','form-grid');const fields={};for(const [key,label,type] of [['name','Display name'],['model','Model ID'],['base_url','API base URL'],['key_env','API key environment variable'],['input_per_million','Input · USD / million tokens','number'],['output_per_million','Output · USD / million tokens','number'],['max_output_tokens','Maximum output tokens','number']]){const [l,i]=field(label,model[key],type);fields[key]=i;if(type==='number'){i.min='0';i.step=key==='max_output_tokens'?'1':'0.01';}grid.append(l);}card.append(grid);
  const roles=el('div','roles');for(const role of ['coordinator','researcher','writer','coder','planner']){const l=el('label'),i=el('input');i.type='checkbox';i.checked=model.roles.includes(role);i.dataset.role=role;l.append(i,document.createTextNode(role));roles.append(l);}card.append(roles);
  const opts=el('div','roles');for(const [key,label] of [['local','Local server (no API fee)'],['tool_calling','Supports tool calling'],['pricing_confirmed','I checked these rates (0 only for a free endpoint)']]){const l=el('label'),i=el('input');i.type='checkbox';i.checked=model[key];fields[key]=i;l.append(i,document.createTextNode(label));opts.append(l);}card.append(opts);
  const tl=el('label','','Token limit parameter'),select=el('select');for(const value of ['max_tokens','max_completion_tokens']){const option=el('option','',value);option.value=value;select.append(option);}select.value=model.token_parameter;tl.append(select);card.append(tl);
  const actions=el('div','model-actions'),test=el('button','secondary','Test connection'),status=el('span','',''),remove=el('button','text-danger','Remove');test.onclick=action(async()=>{test.disabled=true;try{await saveSettings();const data=await api('/models/'+model.id+'/test',{method:'POST'});status.textContent=data.message;if(data.models.length&&!data.ok)status.textContent+=' · Available: '+data.models.slice(0,8).join(', ');if(data.ok){$('#connection-label').textContent=model.name;$('#connection-status .dot').className='dot green';}}finally{test.disabled=false;}});remove.onclick=()=>card.remove();actions.append(test,status,remove);card.append(actions);
  card.read=()=>({...model,...Object.fromEntries(Object.entries(fields).map(([k,i])=>[k,i.type==='checkbox'?i.checked:i.type==='number'?Number(i.value):i.value])),roles:[...roles.querySelectorAll('input:checked')].map(i=>i.dataset.role),token_parameter:select.value});return card;
}
function mediaCard(kind,profile){const card=el('details','media-card');card.append(el('summary','',({image:'Images',video:'Videos','3d':'AI 3D models'})[kind]));const grid=el('div','form-grid');const fields={};for(const [key,label,type] of [['model','Replicate owner/model or owner/model:version'],['prompt_field','Prompt input field'],['reserve_usd','Reserve per generation · USD','number']]){const [l,i]=field(label,profile[key],type);if(type==='number'){i.step='.01';i.min='0';}fields[key]=i;grid.append(l);}card.append(grid);const l=el('label','','Default inputs · JSON'),area=el('textarea','settings-textarea');area.value=JSON.stringify(profile.inputs,null,2);l.append(area);card.append(l);card.read=()=>({model:fields.model.value.trim(),prompt_field:fields.prompt_field.value.trim()||'prompt',reserve_usd:Number(fields.reserve_usd.value),inputs:JSON.parse(area.value||'{}')});card.dataset.kind=kind;return card;}
async function loadSettings(){await refreshBudget();const s=state.settings;$('#model-list').replaceChildren(...s.models.map(modelCard));$('#daily-limit').value=s.daily_budget_usd;$('#run-limit').value=s.run_budget_usd;$('#step-limit').value=s.max_steps;$('#search-provider').value=s.search_provider;$('#search-price').value=s.search_reserve_usd;$('#brave-key').textContent=state.keys.brave?'BRAVE_API_KEY is configured on the server.':'To use Brave, set BRAVE_API_KEY in the server environment and restart Buns.';$('#replicate-key').textContent=state.keys.replicate?'REPLICATE_API_TOKEN is configured. Choose a model for each type below.':'Set REPLICATE_API_TOKEN in the server environment and restart Buns to enable these connections.';$('#media-profiles').replaceChildren(...['image','video','3d'].map(k=>mediaCard(k,s.media[k]||{model:'',prompt_field:'prompt',inputs:{},reserve_usd:0})));}
async function saveSettings(){const updated={...state.settings,models:$$('#model-list .model-card').map(c=>c.read()),daily_budget_usd:Number($('#daily-limit').value),run_budget_usd:Number($('#run-limit').value),max_steps:Number($('#step-limit').value),search_provider:$('#search-provider').value,search_reserve_usd:Number($('#search-price').value),media:Object.fromEntries($$('#media-profiles .media-card').map(c=>[c.dataset.kind,c.read()]))};const result=await api('/settings',{method:'PUT',body:JSON.stringify(updated)});state.settings=result.settings;await refreshBudget();toast('Settings saved');}
$('#new-chat').onclick=action(newConversation);$$('[data-view]').forEach(b=>b.onclick=()=>switchView(b.dataset.view));$$('.starter').forEach(b=>b.onclick=()=>{$('#prompt').value=b.dataset.prompt;$('#prompt').focus();});$('#composer').onsubmit=action(send);$('#prompt').onkeydown=action(async e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();await send();}});$('#stop').onclick=action(async()=>{if(state.run){await api('/runs/'+state.run+'/stop',{method:'POST'});await pollRun(state.generation);}});$('#attach').onclick=()=>$('#file-input').click();$('#file-input').onchange=action(async e=>{await upload(e.target.files[0]);e.target.value='';});$('#menu').onclick=()=>$('#sidebar').classList.toggle('open');$('#activity-toggle').onclick=()=>{const rail=$('#activity-panel');if(innerWidth<=990)rail.classList.toggle('open');else rail.classList.toggle('hidden');};$('#save-settings').onclick=action(saveSettings);$('#refresh-files').onclick=action(async()=>{await api('/media/refresh',{method:'POST'});await loadFiles();});$('#add-model').onclick=()=>{const card=modelCard({id:'model-'+Date.now(),name:'New connection',model:'',base_url:'https://api.openai.com/v1',key_env:'BUNS_API_KEY',input_per_million:0,output_per_million:0,local:false,pricing_confirmed:false,tool_calling:true,roles:['coordinator','researcher','writer','coder','planner'],max_output_tokens:2048,token_parameter:'max_completion_tokens'});card.open=true;$('#model-list').append(card);};document.addEventListener('keydown',action(async e=>{if((e.metaKey||e.ctrlKey)&&e.key==='k'){e.preventDefault();await newConversation();}}));$('#auth-form').onsubmit=async e=>{e.preventDefault();state.token=$('#access-token').value;try{await api('/health');sessionStorage.setItem('buns-token',state.token);$('#access-token').value='';$('#auth-dialog').close();await boot();}catch(error){$('#auth-error').textContent=error.message;}};
async function boot(){await api('/health');await refreshBudget();await refreshNav();const first=state.settings.models[0];$('#connection-label').textContent=first?.name||'Connect a model';}
fillIcons();action(boot)();
