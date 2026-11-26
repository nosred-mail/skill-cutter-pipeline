# Cutter Pipeline — Skill de IA para Cortes Verticais Automáticos

Transforme lives e vídeos longos (do YouTube, Twitch, Kick ou arquivos salvos no seu computador) em **cortes verticais prontos para postar no YouTube Shorts, Instagram Reels e TikTok** — sem precisar saber editar vídeo do zero.

Com um único pedido em português no seu assistente de IA, a skill baixa ou lê o vídeo, transcreve a fala, encontra automaticamente o rosto do criador (para colocar a câmera em cima e o jogo/conteúdo embaixo), anima títulos e legendas palavra por palavra, adiciona efeitos sonoros e ainda entrega um arquivo `.txt` com título, descrição e hashtags prontas para copiar e colar.

---

## O que é uma "Skill" de IA?

Pense numa **Skill** como um "pacote de poderes" que você instala no seu assistente de IA (como **Antigravity**, **Claude Code**, **Cursor**, **Codex** ou **Windsurf**). Depois de instalada, a IA aprende exatamente como usar todas as ferramentas deste projeto sozinha — você só conversa com ela em português normal.

---

## Os 2 Modos de Edição

Você pode escolher o estilo do corte dependendo do que quer publicar:

| Modo | Ideal para... | O que vem no vídeo final |
| :--- | :--- | :--- |
| **Modo 1 — Produção em Lote** | Tirar vários cortes rápidos (20s a 65s) de uma live ou criar um compilado **TOP 5..1** | Câmera em cima + conteúdo embaixo, faixa animada estilo papel enrolando no topo, som de papel e legendas palavra por palavra. No estilo TOP, inclui ranking regressivo e cadeados que vão desbloqueando. |
| **Modo 2 — Estilo História / Cinema (Padrão Híbrido)** | Contar uma história completa (~50s a 90s) juntando vários trechos do vídeo | Abertura impactante (*Cold Open*), efeito de "volta no tempo", meta na tela (`OBJETIVO:`), zoom em detalhes importantes da tela, cortes cômicos em preto e branco, zoom na câmera, trilha de fundo com efeitos sonoros, final abrupto de impacto e **capas (thumbnails `9:16` e `16:9`)**. |

---

## O que você precisa ter no computador antes de começar

Você só precisa instalar **3 programas gratuitos** (o Chrome ou Edge você provavelmente já tem):

1. **Google Chrome ou Microsoft Edge** — usado nos bastidores para gerar as animações e legendas com perfeição.
2. **Node.js (versão 18 ou superior)** — baixe em [nodejs.org](https://nodejs.org/) clicando no botão verde **LTS** e avance até concluir.
3. **Python (versão 3.10, 3.11 ou 3.12)** — baixe em [python.org/downloads](https://www.python.org/downloads/).
   > **ATENÇÃO NO WINDOWS:** Na primeira tela do instalador do Python, **marque a caixinha `Add python.exe to PATH`** lá embaixo antes de clicar em *Install Now*. Isso evita o erro mais comum de iniciantes.
4. *(Opcional)* **Placa de vídeo NVIDIA (GTX/RTX)** — deixa a transcrição de áudio muito mais rápida. Se o seu PC não tiver placa NVIDIA, funciona normalmente usando o processador.

> **Você NÃO precisa baixar manualmente** FFmpeg, Whisper, fontes, efeitos sonoros nem detector de rosto: tudo isso já vem dentro deste repositório ou é instalado automaticamente no Passo 2 abaixo.

---

## Instalação Passo a Passo (para iniciantes)

### Passo 1 — Instalar a skill na sua IA

Escolha **apenas uma** das opções abaixo (a Opção A é a mais rápida):

#### Opção A — Um comando só (Jeito mais rápido)

1. No Windows, clique no menu Iniciar, digite **PowerShell** e abra. (No Mac/Linux, abra o **Terminal**.)
2. Cole o comando abaixo e aperte **Enter**:

```bash
npx skills add nosred-mail/skill-cutter-pipeline
```

3. Se aparecer a pergunta `Ok to proceed? (y)`, digite **`y`** e aperte **Enter**.
4. Siga as opções na tela para escolher os seus agentes de IA (Antigravity, Claude Code, Cursor, etc.).

#### Opção B — Sem usar Git (baixando o ZIP aqui pelo GitHub)

Se não quiser usar `npx` ou Git:

1. Aqui no topo desta página do GitHub, clique no botão verde **`<> Code`** e depois em **`Download ZIP`**.
2. Clique com o botão direito no arquivo `.zip` baixado e escolha **Extrair Tudo...**.
3. Abra a pasta extraída, clique na barra de endereço da pasta, digite **`powershell`** (ou abra o Terminal nessa pasta) e aperte **Enter**.
4. Rode o comando abaixo para copiar a skill para todos os seus agentes automaticamente:

```bash
python scripts/install_skill.py
```

#### Opção C — Usando Git (alternativa)

```bash
git clone https://github.com/nosred-mail/skill-cutter-pipeline.git
cd skill-cutter-pipeline
python scripts/install_skill.py
```

*(Por padrão, o `install_skill.py` instala automaticamente para Antigravity, agentes padrão `.agents` e Claude Code. Se quiser escolher apenas alguns, use `--targets antigravity,agents`.)*

---

### Passo 2 — Instalar as ferramentas de vídeo (só na 1ª vez)

Depois de instalar a skill, você precisa preparar o ambiente de vídeo/áudio uma única vez. Você tem dois jeitos:

- **Pela própria IA (mais fácil):** abra o seu assistente de IA e mande:
  > *"Rode o setup da skill cutter-pipeline para preparar meu ambiente."*
- **Ou direto no terminal** (dentro da pasta onde você baixou/instalou a skill):

```bash
python scripts/cutter_pipeline.py setup
```

> **Paciência na primeira vez:** esse passo baixa o Whisper, OpenCV, `yt-dlp`, FFmpeg e bibliotecas de GPU automaticamente. Pode levar alguns minutos dependendo da sua internet. Depois disso, não precisa rodar de novo.

---

### Passo 3 — Conferir se deu tudo certo (opcional)

Para ter certeza de que o computador está 100% pronto, rode no terminal:

```bash
python scripts/cutter_pipeline.py doctor
```

Se no final da resposta aparecer **`"ok": true`**, está tudo pronto para gerar seus vídeos!

---

## Como usar no dia a dia

Depois de instalada, **você não precisa decorar comandos**. Basta abrir seu assistente de IA na pasta do seu projeto e pedir normalmente em português.

### Exemplos prontos (copie, cole e troque pelo seu link ou arquivo)

**1. Fazer vários cortes rápidos de uma live ou vídeo (Modo 1 — Lote):**
> *"Use a skill `cutter-pipeline` para analisar esse vídeo `https://www.youtube.com/watch?v=...` e gerar os melhores cortes em Produção em Lote (com legenda e texto SEO)."*

**2. Criar um vídeo contando uma história cinematográfica (Modo 2 — Híbrido Narrativo):**
> *"Use a skill `cutter-pipeline` para encontrar a melhor história completa em `live_gravada.mp4` e editar no Padrão Híbrido Narrativo, com efeitos sonoros, thumbnails e arquivos `.txt` de SEO."*

**3. Você já tem um arquivo `.md` com os horários dos cortes:**
> *"Use a skill `cutter-pipeline` para ler o arquivo `meus_cortes.md` e renderizar todos os vídeos a partir de `vod.mp4` em Produção em Lote."*

*(Este formato `.md` é 100% compatível com a skill [skill-extrator-de-clips](https://github.com/nosred-mail/skill-extrator-de-clips), caso você já gere seus relatórios por lá!)*

---

## O que você recebe pronto no final

Para cada corte finalizado, o sistema salva na sua pasta de saída:

- **`nome-do-corte.mp4`** — Vídeo vertical Full HD (`1080×1920`, `30 fps`), áudio normalizado, câmera enquadrada automaticamente e legendas sincronizadas.
- **`nome-do-corte.txt`** — Arquivo de texto pronto para copiar e colar ao publicar no:
  - **YouTube Shorts** (título, descrição e tags)
  - **Instagram Reels** (legenda pensada para busca + *Alt Text* para o algoritmo)
  - **TikTok** (legenda com palavras-chave + hashtags estratégicas)
- **Thumbnails `.png`** *(no Modo 2 — Híbrido)* — Duas capas prontas: uma vertical (`9:16`) para Reels/Shorts/TikTok e uma horizontal (`16:9`).

---

## Perguntas Frequentes (FAQ)

<details>
<summary><strong>Deu erro "'python' não é reconhecido como um comando interno ou externo" no Windows. O que fazer?</strong></summary>

1. Tente trocar `python` por `py` no comando (ex.: `py scripts/install_skill.py`).
2. Se mesmo assim não funcionar, desinstale ou rode o instalador do Python novamente e lembre de marcar a caixinha **`Add python.exe to PATH`** na primeira tela antes de instalar. Depois feche e abra o PowerShell novamente.

</details>

<details>
<summary><strong>A primeira transcrição demorou bastante. É normal?</strong></summary>

Sim! Na primeiríssima vez que você transcreve um vídeo, o Whisper baixa o modelo de voz (`large-v3-turbo`) uma única vez e salva no cache do seu computador. Nas próximas vezes já começa direto. Se você não tiver placa de vídeo NVIDIA, o processamento na CPU também leva um pouco mais de tempo — isso é esperado.

</details>

<details>
<summary><strong>Funciona se o vídeo não tiver webcam (facecam)?</strong></summary>

Sim! O sistema verifica automaticamente se existe um rosto fixo na gravação. Se não encontrar câmera de criador, ele adapta o enquadramento para preencher a tela vertical de forma limpa, sem barra vazia.

</details>

<details>
<summary><strong>Qual a diferença entre o <code>skill-extrator-de-clips</code> e este repositório (<code>skill-cutter-pipeline</code>)?</strong></summary>

- O [`skill-extrator-de-clips`](https://github.com/nosred-mail/skill-extrator-de-clips) faz **apenas a Etapa 1**: lê o áudio/legenda e devolve um arquivo `.md` dizendo quais minutos cortar.
- O **`skill-cutter-pipeline`** (este repositório) é o **pipeline completo**: extrai os momentos **e** já recorta, detecta câmera, edita no HyperFrames (nos modos Lote ou Híbrido Narrativo), renderiza o `.mp4` final e gera o `.txt` de SEO. E se você já tiver um `.md` gerado pelo `skill-extrator-de-clips`, ele lê e edita direto!

</details>

---

## O que vem dentro desta pasta

```text
skill-cutter-pipeline/
├── SKILL.md                  # Cérebro da skill (regras que a IA segue)
├── README.md                 # Este guia passo a passo
├── LICENSE                   # Licença livre (MIT)
├── assets/                   # Arquivos prontos (fontes, banner, detector de rosto e 12 efeitos sonoros)
├── examples/                 # Modelos prontos de arquivo .md e roteiro narrativo .json
├── references/               # Manuais detalhados de extração, Modo Lote, Modo Híbrido e SEO
└── scripts/
    ├── cutter_pipeline.py    # Motor principal (setup, diagnóstico, corte, edição e SEO)
    ├── install_skill.py      # Instalador automático para Antigravity, Claude Code e agentes .agents
    └── render_thumbs.mjs     # Gerador de capas (thumbnails 9:16 e 16:9)
```

---

## Licença

Distribuído sob a licença [MIT](./LICENSE) — livre para usar, adaptar e compartilhar.
