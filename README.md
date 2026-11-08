# Cria Studio

Estúdio de cortes e edição de vídeo para TikTok, Instagram Reels e YouTube Shorts.
Primeira versão funcional, com processamento local por FFmpeg e interface em português.

Para publicar a prévia no GitHub Pages ou hospedar o editor completo, consulte
[DEPLOY.md](DEPLOY.md). O repositório inclui workflow do Pages, Dockerfile e blueprint
do Render. A prévia estática não processa MP4; o serviço com FFmpeg processa.

## Iniciar

Requisitos: Python 3.12+, FFmpeg 7+ com libx264, AAC e libass, e fonte DejaVu Sans.
Instale as dependências Python fixadas em `requirements.txt` em um ambiente virtual. Não há build JavaScript.

```bash
cd /workspace/cria-es
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m studio.server --port 8000
```

O servidor escuta somente na interface local por padrão. O endpoint `/api/health`
informa se o servidor está ativo e se FFmpeg e ffprobe estão disponíveis.
Use a interface pelo acesso ao servidor oferecido pelo ambiente de desenvolvimento.
É um aplicativo de um único proprietário. Em hospedagem externa, defina
`STUDIO_PASSWORD`: o site mostrará uma página de login, protegendo editor, API e vídeos.
O usuário padrão é `studio`; `STUDIO_USERNAME` permite escolher outro nome. A tela
preenche o usuário configurado. A senha aceita acentos e é a do estúdio no Render,
não necessariamente a senha da conta Render. Sessões duram até oito horas e são
encerradas pelo botão **Sair**, pela expiração ou pela perda do armazenamento. Reinícios que preservam `.studio` preservam a sessão; o editor permite reconectar sem fechar os ajustes. A senha não é guardada
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

- **Referência 1:** vídeo superior, faixa preta em degradê, título Montserrat Black branco/amarelo e foto fixa inferior. Quando ativada como texto, a marca aparece abaixo do título, com os ícones do modelo.
- **Referência 2:** vídeo superior, título branco/amarelo e foto inferior dividida em dois enquadramentos.
- **Referência 3:** dois planos com margens pretas, faixa vermelha com contorno irregular de papel rasgado e título branco.

Todos geram 1080 × 1920. A foto inferior é extraída automaticamente do meio do corte;
ela permanece estática enquanto o vídeo superior toca. As prévias usam os frames do seu
vídeo, sem imagens genéricas de demonstração. Os enquadramentos são fixos, sem detecção de rostos.
A composição segue as referências; o conteúdo vem do vídeo enviado e da sua própria marca.

**Marca d’água automática** aceita texto/@perfil ou logo PNG/JPEG de até 5 MB e
16 megapixels. Posição, opacidade e tamanho são configuráveis e ficam salvos no navegador.
A marca é aplicada em cada corte do lote. PNG transparente preserva o fundo.
Logos enviados ficam em `.studio/watermarks`; sua referência é reaproveitada no servidor.
A prévia de posição é aproximada no enquadramento padrão; confira o MP4 final.

### Títulos, legenda para publicação e hashtags automáticos

O servidor transcreve o áudio em português com Faster Whisper Tiny, CPU/int8. Cada
transcrição roda em um processo isolado que termina antes da renderização. O primeiro
corte com fala baixa o modelo público de Hugging Face; o cache fica em `STUDIO_MODEL_DIR`
(`/data/models` no Docker, `.studio/models` no ambiente local). Não exige chave de API.
A primeira execução pode demorar; o progresso aparece no cartão do corte.

Após concluir, o cartão oferece opções extraídas das frases reconhecidas. Escolha uma
para preencher título, destaque, legenda e hashtags. Não é necessário digitar um título;
o campo manual continua como ajuste opcional. O tema adicional e SRT também são opcionais.
A quantidade de opções depende da fala disponível. O modelo pode errar palavras; revise
antes de publicar. Não há análise de tendências nem garantia de viralização.

`AUTO_TRANSCRIBE=0` desliga a transcrição para ambientes de teste sem fala. `STUDIO_WHISPER_MODEL`
permite trocar o modelo; modelos maiores exigem mais memória. A prévia HTML não executa
Whisper: ela demonstra opções a partir de SRT e sinaliza a transcrição como recurso do servidor.

Se o modelo não puder ser baixado ou não houver fala reconhecida, o vídeo e a foto ainda
são gerados; um aviso informa que o template com título não foi aplicado. Não são inventados
títulos genéricos. É possível aplicar novamente o template depois de obter a transcrição.
As sugestões de publicação são separadas das legendas SRT gravadas no vídeo.

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
semântica dos melhores momentos ou acompanhamento de rosto. A transcrição automática se limita à fala do intervalo escolhido.
Não há publicação nas redes sociais, integrações externas ou chaves de API nesta versão.

## Verificação

```bash
.venv/bin/python -m unittest discover -s tests -v
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

## Recursos e validação

A exportação usa um trabalhador por vez. Templates são montados em duas etapas com um
intermediário H.264 sem perdas, que é apagado após o uso. A fonte é recortada antes de
redimensionar; imagens estáticas e o codificador usam uma thread e buffers reduzidos.
O modo de proporção original limita o maior lado a 1920 pixels para o serviço de memória limitada.
Os gráficos dos títulos são gerados em processo isolado; o servidor não retém essa memória.

Cada corte salva automaticamente sua foto inferior e uma capa JPEG. Sessões são persistidas
com identificadores em hash e arquivo privado em `.studio/.sessions.json`. Trocar senha ou
usuário invalida as sessões anteriores. Trabalhos interrompidos são identificados como erro
no reinício, sem confundir arquivos de transcrição com metadados de exportação. No plano
gratuito do Render, recriar a instância pode apagar arquivos e sessões; persistência completa
depende de armazenamento durável.

A integração de transcrição está instalada e a CPU suporta int8. O download do modelo
não pôde ser validado neste ambiente devido a bloqueio de rede para Hugging Face.
Essa validação permanece pendente até a liberação ou o primeiro teste real no Render.
