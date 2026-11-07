'use strict';
const $ = id => document.getElementById(id);
const state = { asset:null, preset:'tiktok', uploading:false, polling:false, submitting:false, previewing:false, lastJobs:'', editing:null, logo:null };
const previewMode = Boolean(window.CRIA_PREVIEW);
let toastTimer;
function toast(message) { $('toast').textContent=message; $('toast').hidden=false; clearTimeout(toastTimer); toastTimer=setTimeout(()=>$('toast').hidden=true,6500); }
async function api(path, options={}) {
  if (previewMode) return window.CRIA_PREVIEW.api(path,options);
  const response=await fetch(path,options); const data=await response.json();
  if (!response.ok) throw new Error(data.error || 'Falha na comunicação com o estúdio.');
  return data;
}
function scrollToStudio() { $('workspace').scrollIntoView({behavior:document.documentElement.dataset.motion==='paused'?'instant':'smooth',block:'start'}); }
function showTab(name) {
  const editor=name==='editor';
  $('editorPanel').hidden=!editor; $('templatesPanel').hidden=editor;
  $('editorNav').classList.toggle('active',editor);$('templatesNav').classList.toggle('active',!editor);
  for (const [id,selected] of [['tabEditor',editor],['tabTemplates',!editor]]) {
    $(id).setAttribute('aria-selected',String(selected)); $(id).tabIndex=selected?0:-1;
  }
}
$('tabEditor').onclick=()=>showTab('editor'); $('tabTemplates').onclick=()=>showTab('templates');
for (const id of ['tabEditor','tabTemplates']) $(id).addEventListener('keydown',event=>{
  if (['ArrowLeft','ArrowRight','Home','End'].includes(event.key)) {
    event.preventDefault(); const editor=event.key==='Home'||(event.key!=='End'&&id==='tabTemplates');
    showTab(editor?'editor':'templates'); $(editor?'tabEditor':'tabTemplates').focus();
  }
});
$('templatesNav').onclick=event=>{event.preventDefault();showTab('templates');scrollToStudio();};
$('editorNav').onclick=event=>{event.preventDefault();showTab('editor');scrollToStudio();};
function choosePreset(name) {
  state.preset=name;
  document.querySelectorAll('[data-preset]').forEach(button=>{
    button.classList.toggle('selected',button.dataset.preset===name);
    button.setAttribute('aria-pressed',String(button.dataset.preset===name));
  }); update();
}
document.querySelectorAll('[data-preset]').forEach(button=>button.onclick=()=>choosePreset(button.dataset.preset));
function watermarkValues() {
  return {enabled:$('watermarkEnabled').checked,type:$('watermarkType').value,text:$('watermarkText').value,
    logo_id:state.logo?.id||'',position:$('watermarkPosition').value,opacity:Number($('watermarkOpacity').value)/100,size:Number($('watermarkSize').value)};
}
function values() {
  return {asset_id:state.asset?.id,reedit_of:state.editing,preset:state.preset,start:Number($('start').value),end:Number($('end').value),
    layout:$('layout').value,batch:$('mode').value==='batch',length:Number($('length').value),crf:Number($('crf').value),normalize:$('normalize').checked,
    subtitles:$('subtitles').value,watermark:watermarkValues(),template:{id:$('templateSelect').value,title:$('templateTitle').value,highlight:$('templateHighlight').value,topic:$('clipTopic').value}};
}
function update() {
  const options=values(),duration=Math.max(0,options.end-options.start),wm=options.watermark;
  $('selectedDuration').textContent=duration.toLocaleString('pt-BR',{maximumFractionDigits:1})+' s selecionados';
  $('lengthField').hidden=!options.batch; $('batchHelp').hidden=!options.batch;
  $('exportButton').disabled=!state.asset||state.uploading||state.submitting;
  $('exportButton').firstChild.textContent=previewMode?'Pré-visualizar cortes ':state.editing?'Salvar nova versão ':options.batch?'Gerar cortes ':'Exportar seleção ';
  const count=options.batch?Math.ceil(duration/options.length):1;
  $('exportNote').textContent=state.asset?`${Number.isFinite(count)?count:'—'} corte(s) · ${options.template.id!=='none'||options.layout!=='original'?'1080 × 1920':'proporção original'} · ${previewMode?'simulação sem gerar MP4':'30 fps'}`:'Envie um vídeo para começar.';
  $('editingBanner').hidden=!state.editing;
  $('templateFields').hidden=options.template.id==='none';
  $('watermarkFields').hidden=!wm.enabled; $('watermarkTextField').hidden=wm.type!=='text'; $('watermarkLogoField').hidden=wm.type!=='logo';
  $('watermarkOpacityValue').textContent=Math.round(wm.opacity*100)+'%'; $('watermarkSizeValue').textContent=wm.size+'%';
  const overlay=$('watermarkPreview');
  overlay.hidden=!state.asset||!wm.enabled||options.template.id!=='none'; overlay.dataset.position=wm.position; overlay.style.opacity=wm.opacity;
  $('watermarkTextPreview').textContent=wm.type==='text'?wm.text:'';
  $('watermarkTextPreview').style.fontSize=Math.max(10,Math.min(30,wm.size*3))+'px';
  $('watermarkLogoPreview').hidden=wm.type!=='logo'||!state.logo;
  if(state.logo){$('watermarkLogoPreview').src=state.logo.url;$('watermarkLogoPreview').style.width=(wm.size*3)+'px';}
  if(state.asset){
    $('timelineSelection').style.left=Math.max(0,Math.min(100,options.start/state.asset.duration*100))+'%';
    $('timelineSelection').style.right=Math.max(0,Math.min(100,100-options.end/state.asset.duration*100))+'%';
  }
  document.dispatchEvent(new Event('studiochange'));
}
function applyWatermark(wm={},logo=null) {
  $('watermarkEnabled').checked=Boolean(wm.enabled); $('watermarkType').value=wm.type||'text'; $('watermarkText').value=wm.text||'';
  $('watermarkPosition').value=wm.position||'top-right'; $('watermarkOpacity').value=Math.round((wm.opacity??.8)*100); $('watermarkSize').value=wm.size??4;
  state.logo=logo||(wm.logo_id?(previewMode?window.CRIA_PREVIEW.getLogo(wm.logo_id):{id:wm.logo_id,url:'/watermarks/'+wm.logo_id+'.png'}):null);
  $('watermarkFileStatus').textContent=state.logo?'Logo carregado. Será aplicado a todos os cortes.':'PNG transparente preserva o fundo do vídeo.';
}
function storeWatermark() {
  try { const wm=watermarkValues(); if(previewMode&&wm.type==='logo'){wm.enabled=false;wm.logo_id='';} localStorage.setItem('cria-watermark-v1',JSON.stringify(wm)); } catch { /* Optional storage. */ }
}
for(const id of ['start','end','layout','mode','length','crf','normalize','templateSelect','templateTitle','templateHighlight','clipTopic']) $(id).addEventListener('input',update);
for(const id of ['watermarkEnabled','watermarkType','watermarkText','watermarkPosition','watermarkOpacity','watermarkSize']) $(id).addEventListener('input',()=>{
  if(id==='watermarkType') $('watermarkSize').value=$('watermarkType').value==='logo'?20:4;
  update();storeWatermark();
});
$('showGuide').onchange=()=>$('safeGuide').hidden=!$('showGuide').checked;
function setBusy(busy){state.uploading=busy;$('videoFile').disabled=busy;$('selectVideo').disabled=busy;$('replaceVideo').disabled=busy;update();}
function applyAsset(info){
  state.asset=info;state.editing=null;state.previewing=false;$('video').pause();$('video').src=info.url;
  $('dropzone').hidden=true;$('previewWrap').hidden=false;$('filename').textContent=info.name;
  $('videoInfo').textContent=`${info.width} × ${info.height} · ${Math.round(info.duration)} s`;
  $('start').value=0;$('end').value=info.duration.toFixed(3);
  for(const id of ['start','end','markStart','markEnd','previewSelection'])$(id).disabled=false;
  $('subtitles').value='';$('srtFile').value='';$('publicationText').value='';update();
}
function upload(file){
  if(!file||state.uploading)return;
  if(file.size>2*1024**3)return toast('O limite é de 2 GB por vídeo.');
  if(previewMode)return window.CRIA_PREVIEW.upload(file,{setBusy,applyAsset,toast});
  setBusy(true);$('uploadProgress').hidden=false;$('progressBar').value=0;
  const request=new XMLHttpRequest();request.open('POST','/api/upload');request.setRequestHeader('Content-Type','application/octet-stream');request.setRequestHeader('X-Filename',encodeURIComponent(file.name));
  request.upload.onprogress=event=>{const percent=event.lengthComputable?Math.round(event.loaded/event.total*100):0;$('progressBar').value=percent;$('progressText').textContent=percent>=100?'Verificando o vídeo…':`Enviando… ${percent}%`;};
  request.onload=()=>{try{const info=JSON.parse(request.responseText);if(request.status!==201)throw new Error(info.error||'Falha no envio.');applyAsset(info);toast('Vídeo pronto para editar.');}catch(error){toast(error.message);}finally{setBusy(false);$('uploadProgress').hidden=true;$('videoFile').value='';}};
  request.onerror=()=>{setBusy(false);$('uploadProgress').hidden=true;toast('O envio foi interrompido. Tente novamente.');};request.send(file);
}
$('videoFile').onchange=event=>upload(event.target.files[0]);$('selectVideo').onclick=()=>$('videoFile').click();$('replaceVideo').onclick=()=>$('videoFile').click();
for(const name of ['dragenter','dragover'])$('dropzone').addEventListener(name,event=>{event.preventDefault();$('dropzone').classList.add('dragging');});
for(const name of ['dragleave','drop'])$('dropzone').addEventListener(name,event=>{event.preventDefault();$('dropzone').classList.remove('dragging');});
$('dropzone').addEventListener('drop',event=>upload(event.dataTransfer.files[0]));
$('markStart').onclick=()=>{$('start').value=$('video').currentTime.toFixed(1);update();};$('markEnd').onclick=()=>{$('end').value=$('video').currentTime.toFixed(1);update();};
$('previewSelection').onclick=async()=>{
  if(!$('video').paused){$('video').pause();state.previewing=false;return;}
  const {start,end}=values();if(end<=start)return toast('O fim deve ser maior que o início.');
  state.previewing=true;$('video').currentTime=start;try{await $('video').play();}catch{toast('Não foi possível reproduzir. Tente MP4 H.264.');}
};
$('video').addEventListener('timeupdate',()=>{if(state.previewing&&$('video').currentTime>=Number($('end').value)){$('video').pause();state.previewing=false;}});
$('video').addEventListener('play',()=>$('previewSelection').lastChild.textContent=' Pausar prévia');
$('video').addEventListener('pause',()=>$('previewSelection').lastChild.textContent=' Reproduzir seleção');
$('srtFile').onchange=async event=>{const file=event.target.files[0];if(!file)return;if(file.size>500000)return toast('A legenda deve ter até 500 KB.');$('subtitles').value=await file.text();toast('Legenda importada.');};
$('watermarkFile').onchange=async event=>{
  const file=event.target.files[0];if(!file)return;if(file.size>5*1024**2)return toast('O logo deve ter até 5 MB.');
  $('watermarkFile').disabled=true;
  try{
    if(previewMode)state.logo=await window.CRIA_PREVIEW.uploadLogo(file);
    else state.logo=await api('/api/watermark',{method:'POST',headers:{'Content-Type':'application/octet-stream'},body:file});
    $('watermarkFileStatus').textContent='Logo carregado. Será aplicado a todos os cortes.';update();storeWatermark();toast('Marca pronta para aplicação automática.');
  }catch(error){toast(error.message);}finally{$('watermarkFile').disabled=false;}
};
function applyOptions(options){
  for(const id of ['layout','crf'])if(options[id]!==undefined)$(id).value=options[id];
  $('normalize').checked=options.normalize??true;
  const template=options.template||{};$('templateSelect').value=template.id||'none';$('templateTitle').value=template.title||'';$('templateHighlight').value=template.highlight||'';$('clipTopic').value=template.topic||'';
  if(options.watermark)applyWatermark(options.watermark);
  choosePreset(options.preset||'tiktok');
}
function publicationText(publication){return publication?[publication.caption,(publication.hashtags||[]).join(' ')].filter(Boolean).join('\n\n'):'';}
$('suggestPublication').onclick=async()=>{
  try{const response=await api('/api/suggest',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(values())});
    if(!response.title)return toast(response.source);
    if(!$('templateTitle').value.trim())$('templateTitle').value=response.title;
    $('publicationText').value=publicationText(response);update();toast('Sugestão criada. Revise o texto e as hashtags antes de publicar.');
  }catch(error){toast(error.message);}
};
$('copyPublication').onclick=async()=>{
  if(!$('publicationText').value.trim())return toast('Gere ou escreva a legenda antes de copiar.');
  try{await navigator.clipboard.writeText($('publicationText').value);toast('Legenda e hashtags copiadas.');}catch{$('publicationText').focus();$('publicationText').select();toast('Texto selecionado. Use Ctrl+C ou a opção Copiar.');}
};
async function editJob(job,openTemplates=false){
  try{
    const info=await api('/api/assets/'+job.asset_id);applyAsset(info);applyOptions(job.options);
    state.editing=job.id;$('start').value=job.options.start;$('end').value=job.options.end;$('mode').value='single';$('subtitles').value=job.subtitles||'';
    $('publicationText').value=publicationText(job.publication);$('editingLabel').textContent=`Editando ${job.name} · a nova versão preserva o corte anterior.`;
    showTab(openTemplates?'templates':'editor');update();scrollToStudio();
  }catch(error){toast(error.message);}
}
$('cancelEdit').onclick=()=>{state.editing=null;if(state.asset){$('start').value=0;$('end').value=state.asset.duration.toFixed(3);}update();};
document.querySelectorAll('[data-template]').forEach(button=>button.onclick=()=>{
  $('templateSelect').value=button.dataset.template;showTab('editor');update();scrollToStudio();
  toast(state.asset?'Template selecionado. Ajuste o título e exporte a nova versão.':'Template selecionado. Envie um vídeo para começar.');
});
$('savePreset').onclick=()=>{try{const {preset,layout,batch,length,crf,normalize,template}=values();localStorage.setItem('cria-preset-v1',JSON.stringify({preset,layout,batch,length,crf,normalize,template}));storeWatermark();toast('Padrão e marca d’água salvos neste navegador.');}catch{toast('Não foi possível salvar neste navegador.');}};
try{
  const saved=JSON.parse(localStorage.getItem('cria-preset-v1')||'null');
  if(saved){applyOptions(saved);$('mode').value=saved.batch?'batch':'single';if(saved.length)$('length').value=saved.length;}
  const wm=JSON.parse(localStorage.getItem('cria-watermark-v1')||'null');if(wm)applyWatermark(wm);
}catch{/* Optional preferences. */}
$('exportButton').onclick=async()=>{
  const options=values();if(!Number.isFinite(options.start)||!Number.isFinite(options.end)||options.end-options.start<.1)return toast('Escolha um intervalo de pelo menos 0,1 segundo.');
  if(options.watermark.enabled&&(options.watermark.type==='text'?!options.watermark.text.trim():!state.logo))return toast('Digite sua marca ou envie o logo.');
  state.submitting=true;update();
  try{
    const result=await api('/api/export',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(options)});
    toast(previewMode?`${result.jobs.length} prévia(s) criadas. Nenhum MP4 foi gerado.`:`${result.jobs.length} corte(s) na fila.`);await refreshJobs();
    $('exports').scrollIntoView({behavior:document.documentElement.dataset.motion==='paused'?'instant':'smooth',block:'start'});
  }catch(error){toast(error.message);}finally{state.submitting=false;update();}
};
function element(tag,className,text){const node=document.createElement(tag);if(className)node.className=className;if(text!==undefined)node.textContent=text;return node;}
async function refreshJobs(){
  if(state.polling)return;state.polling=true;
  try{
    const {jobs}=await api('/api/jobs');const signature=JSON.stringify(jobs);if(signature===state.lastJobs)return;state.lastJobs=signature;
    $('emptyExports').hidden=jobs.length>0;$('jobsCount').textContent=String(jobs.length).padStart(2,'0');$('exportCount').textContent=jobs.filter(j=>j.status==='done'||j.status==='preview').length;
    const fragment=document.createDocumentFragment();
    for(const job of jobs.slice().reverse()){
      const card=element('article','job');card.dataset.status=job.status;card.append(element('h3','',job.name));
      card.append(element('p','',`${job.options.start.toFixed(1)} s → ${job.options.end.toFixed(1)} s · ${job.options.preset}`));
      const labels={queued:'◷ Na fila',processing:'◌ Exportando…',done:'✓ Pronto para baixar',error:'Falha na exportação',preview:'Prévia de corte · sem MP4 gerado'};
      card.append(element('span','job-status '+(job.status==='error'?'error':''),labels[job.status]||job.status));
      if(job.status==='error')card.append(element('p','',job.error));
      if(job.download){const video=element('video');video.controls=true;video.preload='none';video.src=job.download;card.append(video);const link=element('a','button secondary','↓ Baixar MP4');link.href=job.download;link.download='corte.mp4';card.append(link);}
      if(job.asset_id&&['done','preview'].includes(job.status)){
        const actions=element('div','job-actions');const edit=element('button','button secondary','Editar corte');edit.onclick=()=>editJob(job);
        const template=element('button','button primary','Aplicar template');template.onclick=()=>editJob(job,true);actions.append(edit,template);card.append(actions);
        if(job.publication?.caption){const details=element('details','publication-details');details.append(element('summary','','Legenda e hashtags sugeridas'));const text=element('textarea');text.rows=6;text.value=publicationText(job.publication);text.setAttribute('aria-label','Sugestão editável para '+job.name);details.append(text);card.append(details);}
      }
      fragment.append(card);
    }$('jobs').replaceChildren(fragment);
  }catch{/* Preserve existing cards during a disconnect. */}finally{state.polling=false;}
}
choosePreset(state.preset);refreshJobs();setInterval(refreshJobs,2500);
