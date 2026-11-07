'use strict';
const form=document.getElementById('loginForm'),password=document.getElementById('password'),message=document.getElementById('loginError'),button=document.getElementById('loginButton');
const toggle=document.getElementById('showPassword');
toggle.addEventListener('click',()=>{const showing=password.type==='password';password.type=showing?'text':'password';toggle.textContent=showing?'Ocultar':'Mostrar';toggle.setAttribute('aria-pressed',String(showing));});
fetch('/api/auth/status',{credentials:'same-origin',cache:'no-store'}).then(r=>r.json()).then(status=>{if(status.authenticated)location.replace('/');else if(status.username)document.getElementById('username').value=status.username;}).catch(()=>{});
form.addEventListener('submit',async event=>{
  event.preventDefault();button.disabled=true;button.textContent='Entrando…';message.hidden=true;
  try{
    const response=await fetch('/api/auth/login',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:document.getElementById('username').value,password:password.value})});
    const result=await response.json();if(!response.ok)throw new Error(result.error||'Não foi possível entrar.');
    const check=await fetch('/api/auth/status',{credentials:'same-origin',cache:'no-store'});
    const session=await check.json();
    if(!session.authenticated)throw new Error('O navegador não manteve sua sessão. Abra o endereço em uma aba do Chrome ou Edge e tente novamente.');
    password.value='';location.replace('/');
  }catch(error){message.textContent=error.message||'Não foi possível conectar ao estúdio. Tente novamente.';message.hidden=false;password.focus();}
  finally{button.disabled=false;button.textContent='Entrar no estúdio →';}
});
