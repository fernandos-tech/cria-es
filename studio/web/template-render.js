'use strict';
(() => {
  const canvas=document.getElementById('templateCanvas'), video=document.getElementById('video'), ctx=canvas.getContext('2d');
  const logo=new Image();let logoURL='',frame=0;
  function view(x,y,w,h,focus=.5,zoom=1){
    const scale=Math.max(w/video.videoWidth,h/video.videoHeight)*zoom,sw=w/scale,sh=h/scale;
    ctx.drawImage(video,(video.videoWidth-sw)*focus,(video.videoHeight-sh)/2,sw,sh,x,y,w,h);
  }
  function titleLines(text,size,columns){
    ctx.font=`900 ${size}px Arial,sans-serif`;const lines=[];let line='';
    for(const word of text.split(/\s+/)){const next=line?line+' '+word:word;if((ctx.measureText(next).width>1000||next.length>columns)&&line){lines.push(line);line=word;}else line=next;}
    if(line)lines.push(line);return lines;
  }
  function draw(){
    const selected=document.getElementById('templateSelect').value;
    const active=selected!=='none'&&Boolean(state.asset);
    canvas.hidden=!active;video.hidden=active;if(!active||video.readyState<2)return;
    ctx.clearRect(0,0,1080,1920);view(0,0,1080,820);
    if(selected==='compare'){view(0,1100,540,820,.25);view(540,1100,540,820,.75);}else view(0,1100,1080,820,.5,1.5);
    ctx.fillStyle=selected==='red'?'#c60013':'#000';ctx.fillRect(0,820,1080,280);
    const text=(document.getElementById('templateTitle').value.trim()||'SEU TÍTULO AQUI').toUpperCase();
    let columns=18,size=80,lines=titleLines(text,size,columns);while(lines.length>3&&columns<120){columns++;size=Math.max(30,Math.round(80*18/columns));lines=titleLines(text,size,columns);}
    const highlight=document.getElementById('templateHighlight').value.toUpperCase().trim();
    ctx.font=`900 ${size}px Arial,sans-serif`;ctx.textBaseline='middle';
    for(let i=0;i<lines.length;i++){
      const line=lines[i],y=960+(i-(lines.length-1)/2)*size*1.2,x=(1080-ctx.measureText(line).width)/2;
      ctx.fillStyle='#fff';const at=highlight?line.indexOf(highlight):-1;
      if(at<0)ctx.fillText(line,x,y);else{
        const before=line.slice(0,at),after=line.slice(at+highlight.length);ctx.fillText(before,x,y);
        const markX=x+ctx.measureText(before).width;ctx.fillStyle='#ffdd00';ctx.fillText(highlight,markX,y);
        ctx.fillStyle='#fff';ctx.fillText(after,markX+ctx.measureText(highlight).width,y);
      }
    }
    const wm=watermarkValues();
    if(wm.enabled){ctx.save();ctx.globalAlpha=wm.opacity;const left=wm.position.endsWith('left'),top=wm.position.startsWith('top');
      if(wm.type==='logo'&&logo.complete&&logo.naturalWidth){const scale=Math.min(1080*wm.size/100/logo.naturalWidth,480/logo.naturalHeight),w=logo.naturalWidth*scale,h=logo.naturalHeight*scale;ctx.drawImage(logo,left?38:1042-w,top?96:1824-h,w,h);}
      if(wm.type==='text'&&wm.text){const fs=Math.max(6,Math.min(Math.round(1920*wm.size/100),Math.round(1080*.84/Math.max(1,wm.text.length)/.65)));ctx.font=`${fs}px Arial,sans-serif`;ctx.fillStyle='#fff';ctx.textBaseline='top';ctx.shadowColor='#000';ctx.shadowBlur=2;const w=ctx.measureText(wm.text).width;ctx.fillText(wm.text,left?38:1042-w,top?96:1824-fs);}
      ctx.restore();
    }
  }
  function loop(){draw();if(!video.paused&&!video.ended)frame=requestAnimationFrame(loop);}
  video.addEventListener('play',()=>{cancelAnimationFrame(frame);loop();});
  for(const event of ['pause','seeked','loadeddata','loadedmetadata'])video.addEventListener(event,draw);
  document.addEventListener('studiochange',()=>{
    const url=state.logo?.url||'';if(url&&url!==logoURL){logoURL=url;logo.onload=draw;logo.src=url;}
    draw();
  });draw();
})();
