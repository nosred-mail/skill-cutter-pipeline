---
name: cutter-pipeline
description: >-
  Pipeline completo e autocontido de extração, edição vertical (1080x1920, 30 fps) e empacotamento SEO
  de cortes de vídeos e lives via Python + FFmpeg + Whisper CUDA + HyperFrames. Use quando o usuário
  pedir para extrair melhores momentos/histórias de um vídeo ou URL, processar um arquivo .md com
  timestamps, produzir cortes em lote (Modo 1: Produção em Lote com banner 3D enrolando e legendas
  palavra a palavra) ou criar cortes cinematográficos de storytelling (Modo 2: Padrão Híbrido Narrativo
  com Cold Open, Rewind, Objetivo, HUD Callout, Dissolve, BGM/SFX, Final Abrupto e Thumbnails).
---

# Cutter Pipeline (Extração + Edição Lote & Híbrida + SEO)

Esta skill é **100% autocontida e compatível com qualquer agente de IA** (Antigravity, Claude Code, Codex, Cursor, Windsurf). Todos os modelos (`face_detection_yunet_2023mar.onnx`), fontes (`Montserrat-ExtraBold.ttf`, `Anton-Regular.ttf`), texturas (`torn_paper_banner_base.png`) e efeitos sonoros residem em `<SKILL_DIR>/assets/`, onde `<SKILL_DIR>` é a pasta que contém este `SKILL.md`.

> **Escopo:** Cobre exclusivamente os fluxos consolidados de **Extração de Momentos/Arcos**, **Modo 1 — Produção em Lote (Geração 1)** e **Modo 2 — Padrão Híbrido Narrativo (Geração 2)**. Se a skill `/hyperframes` estiver instalada no agente atual, consulte-a em conjunto; caso contrário, todas as regras necessárias do contrato HyperFrames estão em [references/hyperframes-e-seo.md](./references/hyperframes-e-seo.md).

---

## 1. Árvore de Decisão Rápida

Identifique primeiro **o que já existe** e **qual modo de edição** o pedido exige:

| Situação de Entrada | Ação Inicial | Manual a Ler |
| :--- | :--- | :--- |
| **Vídeo bruto ou URL sem timestamps definidos** | Rodar `extract` (transcrição + `transcript_lines.txt` + `overview.jpg`), inspecionar cenas e selecionar momentos/arco respeitando margens obrigatórias. | [references/extracao-e-formato-md.md](./references/extracao-e-formato-md.md) |
| **Arquivo `.md` com timestamps ou timestamps diretos no prompt** | Ler intervalos via `parse-md` **sem reavaliar nem perguntar quais partes cortar** (salvo se o usuário pedir curadoria). | [references/extracao-e-formato-md.md](./references/extracao-e-formato-md.md) |

| Modo de Edição | Quando Usar | Manual Obrigatório |
| :--- | :--- | :--- |
| **Modo 1 — Produção em Lote (`batch` / `batch-top`)** | Vários cortes diretos de uma live/vídeo (20–65s), corte único rápido com banner 3D enrolando + legendas palavra a palavra, ou compilado estilo `TOP N..1`. | [references/modo-lote.md](./references/modo-lote.md) |
| **Modo 2 — Padrão Híbrido Narrativo (`hybrid`)** | Corte especial de **storytelling encadeado** (~50–90s, estilo *Corvette Sem Gasolina*) unindo múltiplos trechos da fonte com Cold Open, volta no tempo, promessa (`OBJETIVO`), zoom de HUD, dissolve cômico, punch-in de câmera, BGM/SFX e final abrupto estilo GTA. | [references/modo-hibrido-narrativo.md](./references/modo-hibrido-narrativo.md) |

---

## 2. Regras Inegociáveis de Corte e Qualidade

1. **Margem Anterior e Posterior Obrigatórias:** Ao extrair ou ajustar timestamps de qualquer lance/momento, garanta **lead-in de 3s a 5s antes** da ação/fala principal (nunca corte no meio de uma palavra) e **follow-through de 2,5s a 4s depois** do desfecho/reação. Em lances esportivos/jogos com passe longo ou gol, mostre até a bola chegar ou até o fim da celebração em campo, sem incluir replay.
2. **Áudio Normalizado e Seek Limpo:** Todos os vídeos gerados pelo motor usam `1080×1920`, `30 fps`, keyframes a cada `0.5s` (`-g 15`) e normalização EBU R128 (`loudnorm=I=-14:TP=-1.5:LRA=11`).
3. **Navegador Real com GPU no HyperFrames:** Antes de rodar `check`, `snapshot`, `preview` ou `render`, aponte `HYPERFRAMES_BROWSER_PATH` para o Chrome/Edge instalado na máquina (evita travamentos do `chrome-headless-shell` em vídeo H.264/Canvas).

---

## 3. Fluxo Padrão de Execução (5 Etapas)

### Etapa 0 — Diagnóstico Rápido (`doctor` / `setup`)
Na primeira execução em um workspace desconhecido, verifique o ambiente:
```bash
python "<SKILL_DIR>/scripts/cutter_pipeline.py" doctor
```
Se `python_media_ready` for `false`, crie/instale o ambiente local automaticamente com:
```bash
python "<SKILL_DIR>/scripts/cutter_pipeline.py" setup
```
O comando `doctor` também retorna `chrome_browser` (para `HYPERFRAMES_BROWSER_PATH`) e `hyperframes_cli.command` (`plugin-cli.mjs` quando instalado ou `npx --yes hyperframes@0.9.72`).

### Etapa 1 — Obter ou Extrair os Intervalos
- **Com `.md` pronto:** rode `python "<SKILL_DIR>/scripts/cutter_pipeline.py" parse-md "<arquivo.md>"`.
- **A partir de vídeo bruto ou link:** siga [references/extracao-e-formato-md.md](./references/extracao-e-formato-md.md) (`extract` → ler `transcript_lines.txt` + ver `evidence/overview.jpg` → gerar `.md` para Lote ou `SPEC.md` + `story_spec.json` para Híbrido).

### Etapa 2 — Construir o(s) Projeto(s) HyperFrames
- **Modo 1 (Produção em Lote):** siga [references/modo-lote.md](./references/modo-lote.md) (`cutter_pipeline.py batch ...`).
- **Modo 2 (Padrão Híbrido Narrativo):** siga [references/modo-hibrido-narrativo.md](./references/modo-hibrido-narrativo.md) (`cutter_pipeline.py hybrid --spec story_spec.json --saida-dir edicao/hf_<slug>`).

### Etapa 3 — Validar, Inspecionar Visualmente e Renderizar
Dentro de **cada subpasta gerada** (`edicao/hf_<slug>`), com `HYPERFRAMES_BROWSER_PATH` definido:
1. **Check completo:** `<HF_CLI> check --json` — corrija qualquer `error` antes de prosseguir (veja [references/hyperframes-e-seo.md](./references/hyperframes-e-seo.md)).
2. **Inspeção visual obrigatória de quadros (`snapshot`):**
   - No Modo Lote: `<HF_CLI> snapshot --at 0.5,2.5,5.4,8.5`
   - No Modo Híbrido: `<HF_CLI> snapshot --at <tempos-de-cada-beat>` (gancho, volta no tempo, objetivo, HUD, dissolve, clímax e card final).
   - **Abra e inspecione os PNGs/JPGs gerados** em `.hyperframes/artifacts/snapshots/` usando sua ferramenta de leitura de imagem para confirmar enquadramento da facecam (sem bordas cortadas), legibilidade e ausência de sobreposições.
3. **Render final para MP4:**
   ```bash
   <HF_CLI> render --quality delivery -o "<pasta-cortes>/<slug>.mp4"
   ```
   Valide o `.mp4` gerado com `ffprobe` (duração exata, stream H.264 `1080×1920` e stream AAC `48000 Hz`).

### Etapa 4 — Empacotamento Final Obrigatório (`.txt` SEO + Capas Opcionais)
Para **cada `.mp4` entregue**, gere obrigatoriamente na mesma pasta o arquivo `<slug>.txt` com copy otimizada para **YouTube Shorts**, **Instagram Reels (Framework MATCH + Alt Text)** e **TikTok (Triple Mention)** seguindo as diretrizes e o comando `seo-txt` em [references/hyperframes-e-seo.md](./references/hyperframes-e-seo.md). Se o usuário pedir thumbnails (ou em entregas principais do Modo Híbrido), gere as capas `9:16` e `16:9` com `<SKILL_DIR>/scripts/render_thumbs.mjs`.
