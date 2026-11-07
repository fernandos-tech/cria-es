# Cria Studio

Estúdio de cortes e edição de vídeo para TikTok, Instagram Reels e YouTube Shorts.
Primeira versão funcional, com processamento local por FFmpeg e interface em português.

Para publicar a prévia no GitHub Pages ou hospedar o editor completo, consulte
[DEPLOY.md](DEPLOY.md). O repositório inclui workflow do Pages, Dockerfile e blueprint
do Render. A prévia estática não processa MP4; o serviço com FFmpeg processa.

## Iniciar

Requisitos: Python 3.12+, FFmpeg 7+ com libx264, AAC e libass, e fonte DejaVu Sans.
Não há dependências Python ou JavaScript para instalar.

```bash
cd /workspace/cria-es
python3 -m studio.server --port 8000
```

O servidor escuta somente na interface local por padrão. O endpoint `/api/health`
informa se o servidor está ativo e se FFmpeg e ffprobe estão disponíveis.
Use a interface pelo acesso ao servidor oferecido pelo ambiente de desenvolvimento.
É um aplicativo de um único proprietário. Em hospedagem externa, defina
`STUDIO_PASSWORD`: o site mostrará uma página de login, protegendo editor, API e vídeos.
O usuário padrão é `studio`; `STUDIO_USERNAME` permite escolher outro nome. A tela
preenche o usuário configurado. A senha aceita acentos e é a do estúdio no Render,
não necessariamente a senha da conta Render. Sessões duram até oito horas e são
encerradas pelo botão **Sair** ou pelo reinício do servidor. A senha não é guardada
no navegador; o identificador de sessão usa cookie HttpOnly. O teste `/api/health`
e os arquivos da tela de login permanecem públicos. O servidor recusa
escuta externa sem senha. Use HTTPS no provedor. Processos precisam ser reiniciados
em novas sessões.

## Fluxo disponível

1. Envie um vídeo de até 2 GB. MP4/H.264 oferece a melhor compatibilidade de prévia no navegador.
2. Escolha TikTok, Reels ou Shorts. Os três usam a mesma base de exportação nesta versão:
   MP4, H.264, AAC quando houver áudio, 30 fps e 1080 × 1920 no modo vertical.
3. Marque início e fim. Exporte a seleção ou divida o intervalo por uma duração configurável.
4. Preserve toda a imagem com barras, preencha a tela com corte central ou mantenha a proporção original.
5. Opcionalmente importe SRT com tempos relativos ao vídeo original. As legendas são
   recortadas, sincronizadas e gravadas em cada vídeo exportado. O estilo inicial é
   branco com contorno; outros estilos serão configurados conforme os padrões do projeto.
6. Exporte e baixe os cortes. Um trabalhador processa a fila, limitada a 30 cortes pendentes.
7. Em um corte concluído, use **Editar corte** ou **Aplicar template**. O original
   permanece disponível; a nova versão é renderizada a partir da mídia original,
   preservando a qualidade e evitando duplicar elementos já gravados.

É possível escolher qualidade e normalizar áudio. O botão **Salvar meu padrão** guarda
essas preferências no navegador, sem armazenar o vídeo ou a legenda no localStorage.
O guia central é ilustrativo, não uma garantia das áreas seguras de cada plataforma.
A prévia padrão é do vídeo original. Ao selecionar um template, um canvas mostra a
composição; fontes e quebras de linha podem variar ligeiramente em relação ao FFmpeg.
O arquivo exportado contém o enquadramento, título, legendas e marca d’água selecionados.

## Templates, marca d’água e publicação

- **Duplo impacto:** dois recortes sincronizados com faixa preta central, título
  branco e expressão em amarelo.
- **Comparativo:** plano superior e dois recortes inferiores do mesmo vídeo.
- **Faixa vermelha:** dois planos com título central em fundo vermelho.

Todos geram 1080 × 1920. O título e a expressão em destaque são editáveis. Os planos
usam recortes fixos do mesmo vídeo, sem detecção de rostos ou troca de câmeras.
O template de faixa vermelha usa uma faixa retangular; não reproduz a textura rasgada
da imagem de referência. Marcas, pessoas e imagens das referências não são incorporadas.

**Marca d’água automática** aceita texto/@perfil ou logo PNG/JPEG de até 5 MB e
16 megapixels. Posição, opacidade e tamanho são configuráveis e ficam salvos no navegador.
A marca é aplicada em cada corte do lote. PNG transparente preserva o fundo.
Logos enviados ficam em `.studio/watermarks`; sua referência é reaproveitada no servidor.
A prévia de posição é aproximada no enquadramento padrão; confira o MP4 final.

Informe o **Tema do corte** ou importe SRT e clique em **Sugerir título, legenda e
hashtags**. A sugestão é local, baseada nesse texto e nas falas SRT do intervalo;
não usa análise semântica por IA, dados de tendências ou alegações de viralização.
A legenda para publicação é editável e copiável. Ela é separada das legendas SRT
gravadas no vídeo. Não há publicação automática em redes sociais.

A reedição usa intervalos do vídeo original. Metadados de fonte e parentesco ficam
salvos junto às exportações para que as versões concluídas possam ser editadas após reiniciar.

## Interface e motion

A prévia portátil está em `preview.html`: baixe e abra o arquivo no navegador.
Ela inclui fonte, estilos e scripts, sem depender de rede ou servidor. Permite
explorar os motions, abrir vídeo local, experimentar templates, marca d’água,
sugestões e reedição. Os cartões criados no HTML são identificados como prévias;
nenhum MP4 é gerado. Vídeos, logos e cartões dessa simulação duram até fechar/recarregar
a página. A exportação real exige a aplicação com servidor. Para atualizar o HTML após
alterar a interface, execute `python3 scripts/build_preview.py`.

O visual usa verde neon e ciano sobre fundo escuro, cartões em perspectiva e animações
CSS e Web Animations nativas. O **Motion Lab** alterna entre Impacto, Fluxo e Órbita
na demonstração visual da interface; esses estilos não adicionam efeitos aos MP4.
O botão **Pausar animações** persiste a preferência no navegador. A preferência de
movimento reduzido do sistema é respeitada, inclusive na rolagem após exportar.
Animações CSS são pausadas quando a aba fica oculta. O editor funciona por teclado
e adapta o layout a telas pequenas. A fonte Space Grotesk é servida localmente,
com licença OFL incluída em `studio/web/fonts/OFL.txt`; não há CDN em tempo de execução.

Uploads, metadados, legendas ajustadas e exportações ficam em `.studio/`, ignorado pelo Git.
Defina `STUDIO_DATA_DIR` para usar outro diretório. Exportações concluídas são recuperadas
quando o servidor reinicia; tarefas em processamento não são retomadas automaticamente.
Arquivos não são apagados automaticamente. A divisão atual é por duração, sem análise
semântica, detecção de melhores momentos, transcrição automática ou acompanhamento de rosto.
Não há publicação nas redes sociais, integrações externas ou chaves de API nesta versão.

## Verificação

```bash
python3 -m unittest discover -s tests -v
node --check studio/web/app.js
```

Os testes geram vídeos sintéticos, enviam pela API, exportam cortes verticais com áudio
e legendas, baixam os MP4 e verificam duração, dimensões, codec e taxa de quadros.
Também verificam entradas inválidas, intervalos de streaming e vídeos sem áudio.
Os testes de templates verificam os pixels da faixa e do logo no vídeo final,
o vínculo da nova versão com o original e o tratamento literal de texto da marca.
Os testes de autenticação verificam cookies seguros, login com senha acentuada,
usuário personalizado, rejeição de senha errada, expiração, logout e bloqueio de
acesso à API e aos vídeos sem sessão. `HEAD /api/health` também é suportado.

## Referências de plataformas

- YouTube Shorts: https://support.google.com/youtube/answer/15424877?hl=pt-BR
- TikTok (especificações de anúncios, não uma regra universal para posts orgânicos): https://ads.tiktok.com/help/article/video-ads-specifications?lang=en
- Instagram Reels: https://www.facebook.com/business/help/103816146375741

As consultas a essas páginas foram bloqueadas pela política de rede do ambiente durante
a implementação. Os presets são uma base técnica comum e editável; não representam
verificação atual dos limites de publicação das plataformas. A duração é configurável.
