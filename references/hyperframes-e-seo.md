# Contrato HyperFrames & Guia Consolidado de SEO Multirede

Este manual garante que qualquer agente de IA execute validações/edições no **HyperFrames** e gere o arquivo obrigatório **`.txt` de SEO** mesmo em ambientes onde as skills externas (`/hyperframes`, `youtube-seo`, `instagram-seo`, `tiktok-captions`, `social-seo`) não estejam instaladas separadamente.

---

## Parte A — Contrato Técnico HyperFrames (Resumo Operacional)

### 1. Como Invocar o HyperFrames CLI em Qualquer Máquina
1. Consulte `python "<SKILL_DIR>/scripts/cutter_pipeline.py" doctor`:
   - Exporte `HYPERFRAMES_BROWSER_PATH` com o caminho de `chrome_browser` retornado:
     - **PowerShell (Windows):** `$env:HYPERFRAMES_BROWSER_PATH = "C:\Program Files\Google\Chrome\Application\chrome.exe"`
     - **Bash (macOS/Linux):** `export HYPERFRAMES_BROWSER_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"` (ou `/usr/bin/google-chrome`)
   - Use o comando indicado em `hyperframes_cli.command`:
     - Se o bundle estiver instalado: `node "<caminho>/plugin-cli.mjs" <subcomando>`
     - Caso contrário (qualquer agente com Node.js): `npx --yes hyperframes@0.9.72 <subcomando>`
2. **Importante:** Rode sempre os comandos **dentro da pasta do subprojeto** (`edicao/hf_<slug>`), nunca na raiz vazia do workspace.

### 2. As 10 Regras do Contrato HyperFrames (Ao Editar HTML Manualmente)
1. Todo elemento temporizado precisa de `class="clip"`, `data-start` e `data-duration` (em segundos). `data-track-index` organiza apenas as pistas visuais do Studio; a ordem de pintura é `z-index`.
2. A duração total do vídeo é controlada pelo `data-duration` do `#root` em `index.html`.
3. Toda composição (`index.html` e cada arquivo em `compositions/*.html`) deve registrar **uma timeline GSAP pausada** após declarar os tweens:
   `window.__timelines = window.__timelines || {}; window.__timelines["<data-composition-id>"] = tl;`
4. **Determinismo total:** proibido `Date.now()`, `Math.random()` sem seed, `setInterval`/`setTimeout`, `fetch` de rede ou `repeat: -1`. Tudo deve ser função pura do tempo `t`.
5. Nunca anime `display`, `visibility` ou `autoAlpha` diretamente em um `.clip`; anime um elemento filho.
6. Não combine `transform` via CSS estático no mesmo nó em que o GSAP anima transformações; anime `x`/`y`/`scale`/`rotation`, nunca `top`/`left`/`width`/`height`.
7. Vídeos com som usam `data-has-audio="true"` (sem `muted`); vídeos mudos/overlays usam `muted`. Nunca chame `.play()` ou `.pause()` via JS.
8. Todo `<audio>` exige um `id` único, caso contrário fica fora da mixagem final.
9. Fontes customizadas exigem `@font-face` apontando para `assets/fonts/...` (sem `/` inicial).
10. Tratamentos de cor, exposição, vinheta e dessaturação em `<video>` ou `<img>` devem usar o atributo `data-color-grading` do HyperFrames, nunca `filter:` CSS improvisado sobre vídeo. Sub-composições em `compositions/*.html` envolvem todo o conteúdo em `<template>`.

---

## Parte B — Guia Consolidado de SEO Multirede (`.txt` Obrigatório)

Todo `.mp4` renderizado em `cortes/<origem>/<slug>.mp4` **exige obrigatoriamente** um arquivo `cortes/<origem>/<slug>.txt` com copy pronta para copiar e colar nas 3 plataformas verticais.

### Princípios Universais (`social-seo`)
- **Plataformas sociais são motores de busca:** palavras-chave naturais no início valem muito mais do que listas gigantes de hashtags.
- **Zero invenção de métricas:** nunca invente volumes de busca; trabalhe a partir da intenção real do vídeo (nome do jogo/assunto + mecânica/conflito + nome do criador).
- **Sem keyword stuffing:** texto fluido, humano, sem clichês robóticos e sempre fiel ao que aparece visualmente no corte.

### Regras Específicas por Rede

#### 1. YouTube Shorts (`youtube-seo` + `social-seo`)
- **Título (`< 60` caracteres):** palavra-chave principal logo nos primeiros caracteres + gatilho de curiosidade/conflito. Evite CAIXA ALTA no título inteiro (use caixa alta apenas em 1 termo de ênfase se necessário).
- **Descrição *Search-First*:** as **2 primeiras frases (~160 caracteres)** devem conter naturalmente a palavra-chave primária e secundária resumindo o que acontece no vídeo, seguidas pelos créditos com link original e **3 a 5 hashtags**.
- **Tags:** lista separada por vírgulas com 6 a 10 termos relevantes do tópico/criador.

#### 2. Instagram Reels (`instagram-seo` — Framework MATCH)
- O Instagram cruza **análise semântica da legenda -> metadados -> visão computacional (Alt Text + cena visual)**. Uma legenda enganosa que não bate com o visual perde alcance.
- **Primeira frase (~125 caracteres):** ancore imediatamente a palavra-chave principal de cauda longa.
- **Corpo + CTA:** contextualize o conflito em 1–2 frases naturais e feche com pergunta/CTA incentivando **comentários ou salvamentos** (sinais mais fortes que curtidas).
- **Hashtags:** estritamente **3 a 5 hashtags** funcionando como rótulos de tópico.
- **Alt Text sugerido (obrigatório):** 1 parágrafo descritivo literal do que aparece na tela (quem está no topo, o que acontece na cena embaixo e qual texto/situação chave aparece), reforçando a palavra-chave.

#### 3. TikTok (`tiktok-captions` + `social-seo` — Triple Mention)
- **Técnica Triple Mention:** alinhe a mesma intenção de busca entre **fala transcrita + texto do gancho na tela + legenda do post**.
- **Estrutura da legenda:** Hook curto (`5 a 7 palavras`) abrindo a primeira linha + `1 a 2 frases` de contexto com palavras-chave naturais + CTA curto + créditos + **3 a 5 hashtags** de nicho.

### Gerando o `.txt` Padronizado via CLI (`seo-txt`)
Escreva um JSON temporário (ex.: `edicao/hf_<slug>/seo.json`):
```json
{
  "video_nome": "corvette-sem-gasolina.mp4",
  "creditos": [
    { "nome": "LipaoGamer", "url": "https://youtu.be/H1nQM59dBO8" }
  ],
  "youtube": {
    "titulo": "Roubou um Corvette no GTA 6 e faltou $5 pra gasolina!",
    "descricao": "LipaoGamer roubou um Corvette na Ocean Drive para tunar no GTA 6, mas ficou sem dinheiro na bomba faltando $5 e perdeu o carro para a polícia. Assista até o final!",
    "tags": ["gta 6", "gta vi", "lipaogamer", "corvette gta 6", "gta 6 gameplay", "cortes gta 6", "shorts"]
  },
  "instagram": {
    "legenda": "Roubou um Corvette no GTA 6 e faltou $5 pra gasolina no posto! LipaoGamer só queria tunar o carro na Vice City Customs, mas descobriu que tinha apenas $43 na conta para pagar $48 no combustível e teve que improvisar com a polícia na cola.\n\nVocê acha que dava pra escapar a pé no final? Comenta aí e salva esse Reel!",
    "hashtags": ["gta6", "gtavi", "lipaogamer", "reelsgames", "vicecity"],
    "alt_text": "Corte vertical de gameplay de GTA 6 com LipaoGamer na câmera superior reagindo enquanto tenta abastecer um Corvette azul no posto Globe Oil com apenas $43 no saldo para pagar $48 de gasolina, antes de ser cercado por viaturas policiais."
  },
  "tiktok": {
    "legenda": "Ele roubou um Corvette e faltaram $5 pra gasolina! LipaoGamer queria tunar o Corvette no GTA 6, mas com a polícia atrás descobriu no posto que só tinha $43 pra pagar $48. Comenta o que achou!",
    "hashtags": ["gta6", "gtavi", "lipaogamer", "gta6clips", "gamingbrasil"]
  }
}
```
E gere o `.txt` final:
```bash
python "<SKILL_DIR>/scripts/cutter_pipeline.py" seo-txt \
  --json "edicao/hf_<slug>/seo.json" \
  -o "cortes/<origem>/<slug>.txt"
```
