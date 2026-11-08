// Portable preview: local media and simulated cuts, never real exports.
window.CRIA_PREVIEW=(()=>{
  const assets=new Map(),logos=new Map(),jobs=[];
  const uid=()=>crypto.randomUUID().replaceAll('-','');
  function suggest(raw){
    const topic=(raw.template?.topic||'').trim(),text=(raw.subtitles||'').split(/\n/).filter(l=>l.trim()&&!/^\d+$/.test(l.trim())&&!l.includes('-->')).join(' ');
    if(!topic&&!text)return{title:'',caption:'',hashtags:[],choices:[],source:'A transcrição automática do áudio é feita no servidor. Esta prévia HTML não transcreve fala.'};
    const phrases=[...new Set([topic,...text.split(/[.!?]+\s*/),...text.split(/(?<=\S)\s+(?=(?:\S+\s+){0,10}\S+$)/)].map(v=>v.trim()).filter(v=>v.length>8))].slice(0,3);
    const words=(topic||text).normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().match(/[a-z]{4,}/g)||[];
    const hashtags=[...new Set(words.filter(w=>!['para','como','sobre','mais','voce','essa','esse','isso'].includes(w)).slice(0,4).map(w=>'#'+w).concat(['#cortes','#'+(raw.preset||'video')]))];
    const choices=phrases.map((title,i)=>({id:String(i+1),title,highlight:title.split(' ').filter(w=>w.length>5).slice(-2).join('|'),caption:title+'\n\n'+text,hashtags}));
    return{...choices[0],choices};
  }
  async function automaticPhoto(asset,start,end){
    return new Promise(resolve=>{const video=document.createElement('video');video.preload='auto';video.muted=true;video.onloadedmetadata=()=>{video.currentTime=start+(end-start)/2;};video.onseeked=()=>{const c=document.createElement('canvas');c.width=video.videoWidth;c.height=video.videoHeight;c.getContext('2d').drawImage(video,0,0);resolve(c.toDataURL('image/jpeg',.9));video.removeAttribute('src');};video.onerror=()=>resolve(null);video.src=asset.url;});
  }
  return{
    getLogo(id){return logos.get(id)||null;},
    async api(path,options={}){
      if(path==='/api/jobs')return{jobs:jobs.slice()};
      if(path.startsWith('/api/assets/')){const asset=assets.get(path.split('/').pop());if(!asset)throw new Error('Reabra o vídeo local para editar.');return asset;}
      const raw=JSON.parse(options.body||'{}');
      if(path==='/api/suggest')return suggest(raw);
      if(path==='/api/export'){
        const asset=assets.get(raw.asset_id);if(!asset)throw new Error('Abra um vídeo primeiro.');
        if(raw.end>asset.duration||raw.start<0||raw.end-raw.start<.1)throw new Error('Intervalo inválido.');
        const length=raw.batch?raw.length:raw.end-raw.start;if(!Number.isFinite(length)||length<.1)throw new Error('Duração inválida.');
        const count=Math.ceil((raw.end-raw.start)/length);if(count>30)throw new Error('Use até 30 cortes por lote.');
        if(raw.template.id!=='none'&&!raw.template.title.trim()){raw.template.title=suggest(raw).title;}
        const created=[];
        for(let i=0;i<count;i++){
          const start=raw.start+i*length,end=Math.min(raw.end,start+length);if(end-start<.1)continue;
          const photo=await automaticPhoto(asset,start,end);
          const job={photo,id:uid(),asset_id:asset.id,parent_id:raw.reedit_of,name:raw.reedit_of?'Corte · nova versão (prévia)':`Corte ${i+1} (prévia)`,status:'preview',options:{...raw,start,end},subtitles:raw.subtitles,publication:suggest(raw)};
          created.push(job);jobs.push(job);
        }return{jobs:created};
      }throw new Error('Disponível na aplicação com servidor.');
    },
    upload(file,{setBusy,applyAsset,toast}){
      setBusy(true);const url=URL.createObjectURL(file),video=document.createElement('video');video.preload='metadata';
      video.onloadedmetadata=()=>{
        if(!Number.isFinite(video.duration)||!video.videoWidth){URL.revokeObjectURL(url);setBusy(false);return toast('Formato inválido. Tente MP4 H.264.');}
        const asset={id:uid(),name:file.name,url,duration:video.duration,width:video.videoWidth,height:video.videoHeight};assets.set(asset.id,asset);applyAsset(asset);setBusy(false);toast('Vídeo aberto localmente, sem envio ao servidor.');
      };video.onerror=()=>{URL.revokeObjectURL(url);setBusy(false);toast('Formato incompatível com este navegador.');};video.src=url;
    },
    async uploadLogo(file){
      if(!['image/png','image/jpeg'].includes(file.type))throw new Error('Use um PNG ou JPEG.');
      const url=URL.createObjectURL(file);const image=new Image();image.src=url;try{await image.decode();}catch{URL.revokeObjectURL(url);throw new Error('Não foi possível ler o logo.');}
      const logo={id:uid(),url};logos.set(logo.id,logo);return logo;
    }
  };
})();
