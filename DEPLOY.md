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
O restante exige autenticação HTTP Basic: usuário **studio**, senha **STUDIO_PASSWORD**,
gerada no Render e consultável pelo proprietário na configuração segura do serviço.
Use o endereço HTTPS fornecido pelo Render. O servidor recusa escuta externa sem senha.

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
