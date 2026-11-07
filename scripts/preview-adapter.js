// Portable preview: local media and simulated cuts, never real exports.
window.CRIA_PREVIEW=(()=>{
  const assets=new Map(),logos=new Map(),jobs=[];
  const uid=()=>crypto.randomUUID().replaceAll('-','');
  function suggest(raw){
    const topic=(raw.template?.topic||'').trim();
    const text=(raw.subtitles||'').split(/\n/).filter(l=>l.trim()&&!/^\d+$/.test(l.trim())&&!l.includes('-->')).join(' ');
    const title=topic||text.slice(0,90);
    if(!title)return{title:'',caption:'',hashtags:[],source:'Informe o tema ou importe um SRT.'};
    const words=(topic||text).normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().match(/[a-z]{4,}/g)||[];
    const hashtags=[...new Set(words.filter(w=>!['para','como','sobre','mais','voce','essa','esse','isso'].includes(w)).slice(0,4).map(w=>'#'+w).concat(['#cortes','#'+(raw.preset||'video')]))];
    return{title,caption:(topic?topic+'. ':'')+(text?text.slice(0,240)+'\n\n':'')+'Qual é a sua opinião? Conte nos comentários.',hashtags};
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
        if(raw.template.id!=='none'&&!raw.template.title.trim()){raw.template.title=suggest(raw).title;if(!raw.template.title)throw new Error('Informe o título ou o tema do template.');}
        const created=[];
        for(let i=0;i<count;i++){
          const start=raw.start+i*length,end=Math.min(raw.end,start+length);if(end-start<.1)continue;
          const job={id:uid(),asset_id:asset.id,parent_id:raw.reedit_of,name:raw.reedit_of?'Corte · nova versão (prévia)':`Corte ${i+1} (prévia)`,status:'preview',options:{...raw,start,end},subtitles:raw.subtitles,publication:suggest(raw)};
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
