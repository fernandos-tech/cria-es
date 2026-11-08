# Publicação

## Prévia pública: GitHub Pages

O workflow `.github/workflows/pages.yml` gera uma página independente em cada push
para `main`. Ele publica somente a prévia: vídeos são abertos no navegador e cortes
são simulados. Não publica uploads, logos, credenciais ou o diretório `.studio`.

Ative uma vez em **Settings → Pages → Build and deployment → Source → GitHub Actions**.
Depois execute **Actions → Publicar prévia no GitHub Pages → Run workflow**, se necessário.
O endereço definitivo é o URL informado pelo job de deploy, não uma confirmação prévia
de que a publicação funcionou. A disponibilidade em repositórios privados depende do plano.

## Editor completo: Render

[Preparar implantação no Render](https://render.com/deploy?repo=https://github.com/fernandos-tech/cria-es)

O link abre a configuração; não cria um serviço até você entrar no Render, conectar
o repositório e confirmar a implantação. O blueprint `render.yaml` seleciona o plano
gratuito e usa o `Dockerfile` com Python, FFmpeg e fontes. Verifique o plano oferecido
na tela antes de confirmar; disponibilidade e limites são definidos pelo provedor.
Nenhuma credencial do Render é incluída no código ou precisa ser enviada no chat.

O serviço escuta em `0.0.0.0:$PORT`. `/api/health` é público para a verificação do provedor.
O restante exige login pela página **/login**: usuário padrão **studio**, senha
**STUDIO_PASSWORD**, gerada no Render e consultável pelo proprietário na configuração
segura do serviço. **STUDIO_USERNAME** permite configurar outro usuário, se desejado;
a tela preenche o nome configurado. Não use STUDIO_DATA_DIR para configurar usuário:
essa variável deve permanecer **/data** neste contêiner.

Use o endereço HTTPS fornecido pelo Render. O servidor recusa escuta externa sem senha.
O login usa uma sessão de até oito horas, com cookie HttpOnly, SameSite=Strict e Secure
em HTTPS. O botão **Sair** invalida a sessão. Reinícios que preservam `/data` preservam a sessão. Se os dados forem apagados, o editor permite reconectar sem fechar os ajustes.
A senha não é armazenada em localStorage ou no cookie. A janela de autenticação
HTTP Basic foi substituída pela página para evitar pedidos repetitivos no navegador.
Se o navegador bloquear cookies, a página avisa e orienta abrir em uma aba externa.

O plano gratuito usa armazenamento temporário e pode suspender o serviço quando ocioso.
Baixe os vídeos concluídos: uploads, logos e versões podem desaparecer quando a instância
for recriada. Exportação em 1080p depende dos recursos e limites do plano; não há promessa
de processamento em tempo real. Persistência exige um volume ou outro armazenamento
configurado à parte, com avaliação de custos pelo usuário.

É um editor privado de um único proprietário, não um serviço multiusuário. A senha
protege também mídia e downloads. Para hospedar para vários usuários, são necessários
contas, isolamento de arquivos, quotas e um servidor de produção apropriado.

## Docker em outro servidor

```bash
docker build -t cria-studio .
# Configure STUDIO_PASSWORD de forma segura no ambiente antes de iniciar.
docker run --rm -p 127.0.0.1:10000:10000 -e STUDIO_PASSWORD \
  --mount type=volume,src=cria-data,dst=/data cria-studio
```

Use um proxy reverso com HTTPS para acesso externo. O volume preserva os arquivos
entre reinícios. O usuário do contêiner tem UID 10001; diretórios montados precisam
permitir escrita para esse usuário. Não inclua `.env`, senhas ou vídeos na imagem.

## Modelo de fala e foto automática

A imagem Docker instala `requirements.txt` e ativa `AUTO_TRANSCRIBE=1`. O primeiro corte
com fala baixa Whisper Tiny em `/data/models`. Permita acesso a `huggingface.co` e aos
CDNs de modelos usados por Hugging Face. O cache é temporário no plano gratuito.
A imagem não inclui credenciais nem pesos baixados sem verificação.

Depois de gerar um corte com fala, confirme no cartão as opções de título/legenda e
a foto automática. O modelo e o renderizador rodam em sequência para reduzir o pico
de memória. Vídeos muito longos e modelos maiores podem exceder os limites do plano.
