# Modo 2 — Padrão Híbrido Narrativo (Geração 2)

Use este modo quando o objetivo for criar um **Short/Reel cinematográfico de alta retenção (~50s a 90s)** condensando uma história completa com múltiplos cortes internos, elementos gráficos narrativos, tratamento de cor e design de som — exatamente como no corte de referência *Corvette Sem Gasolina*.

Consulte sempre o exemplo real completo em [examples/exemplo_story_spec_hibrido.json](../examples/exemplo_story_spec_hibrido.json).

---

## 1. Princípios Visuais e Narrativos do Padrão Híbrido

1. **Proporção Limpa `31.25% / 68.75%` (`cam_height: 600` + `game_height: 1320`):**
   - Dá mais respiro vertical à ação principal (`1080×1320`) do que o modo em lote tradicional.
   - **Proibido vazar borda colorida/moldura da webcam:** inspecione o frame original (`evidence`) e defina `small_cam` (e `big_cam` se houver zoom na live) recortando *por dentro* da moldura da câmera do streamer.
2. **Cold Open em Flash-Forward (`0.0s -> ~3.9s`) + Banner Único:**
   - O vídeo abre direto no pico de tensão lá da frente (ex.: carro fumaçando com combustível crítico) junto ao **banner de papel 3D**, que desenrola e enrola dentro desses `~3.88s` e **nunca mais reaparece** no restante do vídeo.
3. **Volta Cronológica (`rewind_badge`):**
   - Flash branco curto + selo `◄◄ VOLTANDO NO TEMPO` + efeito sonoro `record_scratch.mp3` marcando o salto para o início da história (ex.: momento do roubo/descoberta).
4. **Ancoragem de Premissa (`promise_goal`):**
   - Quando o criador verbaliza o plano, entra `OBJETIVO:` (Montserrat) + meta em verde vibrante `#2BFF66` (Anton 80px) com `pop.mp3`.
5. **Prova Visual do Conflito (`hud_callout` + `joke_dissolve`):**
   - **Callout Real do HUD:** recorte ampliado real do jogo (`hud_callout.png` extraído por FFmpeg) provando o problema na tela (ex.: `GASOLINA: $48` vs saldo `$43` -> `FALTA $5 NO BOLSO!`) com `error.mp3`.
   - **Dissolve Cômico (`dissolve_special`):** fundo em tela cheia dessaturado/escurecido via `data-color-grading` nativo do HyperFrames + rosto estático/chocado do streamer em câmera lenta sobreposto a `~54%` de opacidade com máscara vertical suave + rótulo vazado (`*FALTAVAM $5 NO BOLSO*`) + `sad_trombone.mp3`.
6. **Punch-in de Câmera (`bigcam_punch`):**
   - Mantém o áudio 100% contínuo enquanto alterna o enquadramento da câmera para um plano mais fechado na frase de virada/ideia.
7. **Final Abrupto Estilo GTA (`abrupt_ending`):**
   - Clarão radial branco/carmim (`0.24s`) + freeze frame real da facecam e da cena final tratada em vermelho de alto contraste (`data-color-grading`) + texto curto de impacto em `Anton` `134px` (ex.: `"sem gasosa"`) + `wasted_boom.mp3`, terminando em **corte seco sem fade-out**.

---

## 2. Passo a Passo de Execução

### Passo 1 — Extrair Arco Bruto e Inspecionar Quadros
Se ainda não tiver o trecho base e a transcrição local:
```bash
python "<SKILL_DIR>/scripts/cutter_pipeline.py" extract \
  --fonte "<URL-ou-video>" \
  --inicio "01:28" --fim "05:20" \
  --idioma pt \
  --saida-dir "references/<slug-historia>"
```
Leia `transcript_lines.txt` e inspecione `evidence/overview.jpg` (gere pranchas extras com `evidence --step 1.0` nos momentos de HUD, reação e clímax para medir coordenadas exatas de `crop`).

### Passo 2 — Escrever `SPEC.md` na Pasta de Edição
Antes de gerar o projeto, documente o plano criativo em `edicao/hf_<slug>/SPEC.md` contendo:
- `GOAL`, `OUTPUT` (`1080×1920`, `30 fps`), `TIME` estimado.
- `LOOK` (proporção do split, paleta, fontes e tratamentos de mídia).
- `OBJECTS` & `SHOTS` (tabela cronológica `00.00-03.90s`, timestamps da fonte, texto/overlay e SFX de cada batida).
- `BANNED` (sem barras pretas laterais, sem moldura cortada da webcam, sem banner repetido, sem fade-out no fim).

### Passo 3 — Escrever `story_spec.json` e Rodar `hybrid`
Monte o arquivo declarativo `edicao/hf_<slug>/story_spec.json` seguindo o modelo de [examples/exemplo_story_spec_hibrido.json](../examples/exemplo_story_spec_hibrido.json) e execute:

```bash
python "<SKILL_DIR>/scripts/cutter_pipeline.py" hybrid \
  --spec "edicao/hf_<slug>/story_spec.json" \
  --saida-dir "edicao/hf_<slug>"
```

O motor `hybrid`:
- Recorta, concatena e normaliza (`-14 LUFS`, `-r 30 -g 15`) todos os `segments` (`split`, `bigcam_punch`, `dissolve_special`).
- Extrai automaticamente `assets/hud_callout.png`, `assets/final_face_freeze.png` e `assets/final_game_freeze.png`.
- Remapeia as palavras do `transcript.json` para a timeline montada, ocultando legendas durante o Cold Open, o Rewind, o Dissolve e o Card Final, e garantindo `start < end` em todos os blocos.
- Gera `index.html` limpo + até **7 sub-composições editáveis** em `compositions/*.html` + mixagem de SFX/BGM do kit embutido em `<SKILL_DIR>/assets/sfx/` (`impact_bass.mp3`, `record_scratch.mp3`, `pop.mp3`, `police_siren.mp3`, `error.mp3`, `sad_trombone.mp3`, `cash_register.mp3`, `wasted_boom.mp3`, `whoosh.mp3`, `chase_loop.mp3`).

### Passo 4 — QA Visual Rigoroso (`check` + `snapshot`) e `REVIEW.md`
Dentro de `edicao/hf_<slug>`:
1. Rode `<HF_CLI> check --json`.
   - **Nota sobre `line_unread` no final abrupto:** se o card final durar ~`1.2s–1.4s` (intencional para impacto seco estilo GTA), o `check` pode emitir 1 `warning` `line_unread` (piso padrão de `2.0s`). Documente-o como intencional no `REVIEW.md`, mas **zere todos os `errors`**.
2. Rode `<HF_CLI> snapshot --at <lista-de-todos-os-beats>` cobrindo cada transição e overlay.
3. Inspecione todas as imagens geradas: se houver webcam duplicada no fundo, borda colorida vazando ou elemento importante do jogo cortado, ajuste o `game_crop` / `cam_crop` no `story_spec.json`, rode `hybrid` novamente e confira o novo snapshot.
4. Escreva `edicao/hf_<slug>/REVIEW.md` registrando escolhas narrativas, alternativas descartadas e verificações realizadas.

### Passo 5 — Render Final, Thumbnails (`9:16` e `16:9`) e `.txt` SEO
1. Renderize o vídeo final:
   `<HF_CLI> render --quality delivery -o "cortes/<origem>/<slug>.mp4"`
2. Se solicitado (ou para lançamentos completos), crie os templates HTML da capa (`thumb_9x16.html` em `1080×1920` e `thumb_16x9.html` em `1280×720`) destacando **Rosto em Expressão Forte + Objeto de Desejo + Card Visual do Conflito + Headline Curta em Anton (`#FFE500` / `#FFFFFF`)** e renderize ambos em PNG:
   ```bash
   node "<SKILL_DIR>/scripts/render_thumbs.mjs" \
     --html9x16 "edicao/hf_<slug>/thumb_9x16.html" --out9x16 "cortes/<origem>/<slug>-thumb-9x16.png" \
     --html16x9 "edicao/hf_<slug>/thumb_16x9.html" --out16x9 "cortes/<origem>/<slug>-thumb-16x9.png"
   ```
3. Gere o arquivo obrigatório `cortes/<origem>/<slug>.txt` conforme [hyperframes-e-seo.md](./hyperframes-e-seo.md).
