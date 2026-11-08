'use strict';
(()=>{
  const video=$('video'),canvas=$('templateCanvas'),photo=new Image(),logo=new Image(),frozen=document.createElement('canvas'),upperFrame=document.createElement('canvas');
  let photoURL='',logoURL='',assetID='',frame=0;
  const paper=[ [0,938],[82,925],[145,934],[210,916],[370,925],[490,914],[650,928],[805,921],[966,933],[1072,946],[1079,978],[1067,1015],[1077,1054],[1065,1110],[1080,1150],[1066,1203],[946,1214],[818,1206],[667,1221],[506,1211],[330,1224],[192,1210],[52,1217],[9,1200],[18,1163],[1,1120],[12,1083],[2,1044],[17,1008],[0,971] ];
  function view(ctx,source,x,y,w,h,focus=.5,zoom=1){
    const iw=source.videoWidth||source.naturalWidth||source.width,ih=source.videoHeight||source.naturalHeight||source.height;if(!iw||!ih)return;
    const scale=Math.max(w/iw,h/ih)*zoom,sw=w/scale,sh=h/scale;ctx.drawImage(source,(iw-sw)*focus,(ih-sh)/2,sw,sh,x,y,w,h);
  }
  function capture(){
    if(video.readyState<2)return;frozen.width=Math.min(1920,video.videoWidth);frozen.height=Math.round(frozen.width*video.videoHeight/video.videoWidth);frozen.getContext('2d').drawImage(video,0,0,frozen.width,frozen.height);
  }
  function captureUpper(){if(video.readyState<2)return;upperFrame.width=Math.min(1280,video.videoWidth);upperFrame.height=Math.round(upperFrame.width*video.videoHeight/video.videoWidth);upperFrame.getContext('2d').drawImage(video,0,0,upperFrame.width,upperFrame.height);}
  function path(ctx,points){ctx.beginPath();points.forEach(([x,y],i)=>i?ctx.lineTo(x,y):ctx.moveTo(x,y));ctx.closePath();}
  function lines(ctx,text,size){
    ctx.font=`900 ${size}px TemplateTitle,Arial,sans-serif`;const out=[];let line='';for(const word of text.split(/\s+/)){const next=(line+' '+word).trim();if(ctx.measureText(next).width>1000&&line){out.push(line);line=word;}else line=next;}if(line)out.push(line);return out;
  }
  function paint(target,kind){
    const ctx=target.getContext('2d');ctx.save();ctx.clearRect(0,0,target.width,target.height);ctx.scale(target.width/1080,target.height/1920);ctx.fillStyle='#000';ctx.fillRect(0,0,1080,1920);
    const lower=photo.complete&&photo.naturalWidth?photo:frozen;
    const upper=target===canvas?(!video.paused?video:(upperFrame.width?upperFrame:lower)):lower;
    if(kind==='red'){view(ctx,upper,0,84,1080,900);view(ctx,lower,0,984,1080,852,.5,1.25);}
    else if(kind==='compare'){view(ctx,upper,0,0,1080,960);view(ctx,lower,0,960,540,960,.25);view(ctx,lower,540,960,540,960,.75);}
    else{view(ctx,upper,0,0,1080,960);view(ctx,lower,0,960,1080,960,.5,1.5);}
    const center=kind==='red'?1080:960;
    if(kind==='red'){
      ctx.save();ctx.shadowColor='#0009';ctx.shadowBlur=9;ctx.shadowOffsetY=9;path(ctx,paper.map(([x,y],i)=>[Math.max(0,Math.min(1079,x+(i%3===0?8:-6))),y+(y<1000?-10:9)]));ctx.fillStyle='#f2f0e6';ctx.fill();ctx.restore();
      path(ctx,paper);ctx.fillStyle='#da000a';ctx.fill();ctx.save();ctx.clip();const shade=ctx.createLinearGradient(0,930,0,1225);shade.addColorStop(0,'#50000022');shade.addColorStop(.5,'#ff151500');shade.addColorStop(1,'#50000022');ctx.fillStyle=shade;ctx.fillRect(0,930,1080,300);ctx.restore();
    }else{
      const half=kind==='compare'?160:132,g=ctx.createLinearGradient(0,center-half,0,center+half);g.addColorStop(0,'#0000');g.addColorStop(.18,'#000');g.addColorStop(.82,'#000');g.addColorStop(1,'#0000');ctx.fillStyle=g;ctx.fillRect(0,center-half,1080,half*2);
    }
    const text=$('templateTitle').value.toUpperCase().trim();let size=82,rows=lines(ctx,text,size);while(size>30&&(rows.length>3||rows.length*size*1.08>230)){size-=2;rows=lines(ctx,text,size);}
    const marks=new Set($('templateHighlight').value.toLocaleUpperCase('pt-BR').replaceAll('|',' ').split(/\s+/));ctx.font=`900 ${size}px TemplateTitle,Arial,sans-serif`;ctx.textBaseline='top';
    for(let i=0;i<rows.length;i++){
      let x=(1080-ctx.measureText(rows[i]).width)/2;const y=center-rows.length*size*1.08/2+i*size*1.08;
      for(const word of rows[i].match(/\S+\s*/g)||[]){ctx.fillStyle=kind!=='red'&&marks.has(word.trim().replace(/[,.!?]/g,''))?'#ffdc00':'#fff';ctx.fillText(word,x,y);x+=ctx.measureText(word).width;}
    }
    const wm=watermarkValues();if(wm.enabled){ctx.save();ctx.globalAlpha=wm.opacity;const left=wm.position.endsWith('left'),top=wm.position.startsWith('top');
      if(wm.type==='logo'&&logo.complete&&logo.naturalWidth){const z=Math.min(1080*wm.size/100/logo.naturalWidth,480/logo.naturalHeight),w=logo.naturalWidth*z,h=logo.naturalHeight*z;ctx.drawImage(logo,left?38:1042-w,top?96:1824-h,w,h);}
      else if(wm.type==='text'&&wm.text){const fs=kind==='impact'?28:Math.max(6,Math.min(Math.round(1920*wm.size/100),Math.round(1080*.84/Math.max(1,wm.text.length)/.65)));ctx.font=kind==='impact'?'900 28px TemplateTitle':`${fs}px Arial`;ctx.fillStyle='#fff';ctx.shadowColor='#000';ctx.shadowBlur=2;const w=ctx.measureText(wm.text).width,x=kind==='impact'?(1080-w)/2:left?38:1042-w,y=kind==='impact'?center+rows.length*size*1.08/2+9:top?96:1824-fs;ctx.fillText(wm.text,x,y);if(kind==='impact')for(const ox of[x-28,x+w+8]){ctx.fillStyle='#fff';ctx.beginPath();ctx.arc(ox+10,y+12,10,0,Math.PI*2);ctx.fill();ctx.fillStyle='#ff000a';ctx.fillRect(ox+3,y+7,14,10);ctx.fillStyle='#fff';ctx.beginPath();ctx.moveTo(ox+8,y+9);ctx.lineTo(ox+8,y+15);ctx.lineTo(ox+13,y+12);ctx.fill();}}ctx.restore();
    }ctx.restore();
  }
  function draw(){
    const selected=$('templateSelect').value,active=selected!=='none'&&Boolean(state.asset);canvas.hidden=!active;video.hidden=active;
    if(!state.asset||video.readyState<2)return;if(!frozen.width)capture();if(active)paint(canvas,selected);
    if(!$('templatesPanel').hidden)document.querySelectorAll('.reference-canvas').forEach(target=>{paint(target,target.dataset.reference);target.parentElement.classList.add('has-video');});
  }
  function loop(){captureUpper();draw();if(!video.paused&&!video.ended)frame=requestAnimationFrame(loop);}
  video.addEventListener('play',()=>{cancelAnimationFrame(frame);loop();});
  for(const event of ['pause','seeked','loadeddata','loadedmetadata'])video.addEventListener(event,()=>{if(event==='loadeddata'||event==='seeked')captureUpper();draw();});
  document.addEventListener('studiochange',()=>{
    if(assetID!==state.asset?.id){assetID=state.asset?.id;frozen.width=0;upperFrame.width=0;photoURL='';photo.removeAttribute('src');}
    if(state.photo&&photoURL!==state.photo){photoURL=state.photo;photo.onload=draw;photo.src=photoURL;}
    if(state.logo?.url&&state.logo.url!==logoURL){logoURL=state.logo.url;logo.onload=draw;logo.src=logoURL;}
    draw();
  });document.fonts.ready.then(draw);draw();
})();
