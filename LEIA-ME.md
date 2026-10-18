# Texto em Ondas — pacote para publicar

Este pacote contém o site e o servidor que gera os arquivos WAV. A hospedagem precisa aceitar Docker porque o conversor de voz usa o eSpeak NG instalado no servidor.

## Publicar no Render

1. Extraia o arquivo ZIP.
2. Crie um repositório no GitHub e envie para ele os arquivos desta pasta (`index.html`, `server.py`, `Dockerfile` e `render.yaml`) na raiz do repositório.
3. No Render, escolha **New → Blueprint** e conecte esse repositório. O arquivo `render.yaml` configura o serviço automaticamente.
4. Aguarde a publicação e abra o endereço `.onrender.com` criado para o site.

O plano gratuito do Render pode colocar o serviço em repouso após 15 minutos sem acessos; a primeira visita depois disso pode demorar cerca de um minuto para abrir. Você pode escolher outro plano no Render se quiser manter o site sempre disponível.

## Conversão de voz

O servidor oferece vozes sintetizadas em português do Brasil e de Portugal. O download é gerado em WAV. Os arquivos enviados são processados temporariamente durante a conversão e não são guardados pelo site.

O serviço limita cada texto a 100 mil caracteres e controla o número de conversões por endereço IP para reduzir abuso. Como o endereço publicado será público, acompanhe os limites de uso da hospedagem.
