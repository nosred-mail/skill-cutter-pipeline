# Modo 1 — Produção em Lote (Geração 1)

Use este modo para transformar rapidamente uma lista de momentos (`.md`) ou timestamps diretos em cortes verticais padronizados (`1080×1920`, `30 fps`), sem cortes internos complexos.

> **Regra de ouro quando os timestamps já vieram prontos:** Não reavalie se o momento é bom nem pergunte ao usuário quais partes cortar. Processe diretamente todos os cortes pedidos (`--cortes all` ou `--cortes 1,3`).

---

## 1. Anatomia Visual do Preset Individual (`batch`)

- **Topo (`1080×768`):** Facecam fixa detectada automaticamente em 20 quadros pelo modelo YuNet local (`--facecam auto`), ou coordenadas manuais `--facecam x,y,w,h`. Caso não exista facecam (`--facecam none` ou não detectada), o vídeo inteiro é centralizado sobre fundo desfocado (`boxblur=30:3`).
- **Divisória (`y = 767px`):** linha escura sutil (`3px`) com sombra separando câmera e conteúdo.
- **Base (`1080×1152`):** Gameplay / cena principal centralizada sem distorção de aspecto (`setsar=1`).
- **Banner de Papel 3D Enrolando (`y = 768px`, `0s -> 5.92s`):**
  - Renderizado deterministicamente em `<canvas>` sincronizado ao GSAP + `hf-seek` e acompanhado de `sfx_papel_enrolando.wav`.
  - Desenrola da esquerda para a direita nos primeiros `~0.5s`, flutua sutilmente para manter vida visual e **enrola em cilindro 3D da direita para a esquerda** saindo antes de `6.0s`.
  - Destaca automaticamente palavras entre `*asteriscos*` em `#FFE500` (amarelo-ouro) com fonte `Montserrat-ExtraBold`.
- **Legendas palavra por palavra (`y = 1140px`):** blocos rápidos de até 3 palavras / 19 caracteres; palavra falada no instante recebe `#FFE500`, `scale(1.16)` e contorno preto espesso (`12px`).

---

## 2. Comandos de Execução (`batch`)

### 2.1 A partir de um arquivo `.md` (múltiplos cortes de uma vez)
```bash
python "<SKILL_DIR>/scripts/cutter_pipeline.py" batch \
  --md "<caminho/cortes.md>" \
  --cortes all \
  --idioma pt \
  --limpar-tmp \
  --saida-dir "edicao"
```
Para rodar apenas cortes específicos do `.md`, passe `--cortes "1,4"` ou os slugs separados por vírgula.

### 2.2 Corte avulso direto por linha de comando (sem `.md`)
```bash
python "<SKILL_DIR>/scripts/cutter_pipeline.py" batch \
  --fonte "<URL-ou-arquivo-local>" \
  --inicio "00:12:04" \
  --fim "00:12:52" \
  --gancho "Quando o lugar não aceita *Pix*" \
  --slug "buscar-lucia-sem-pix" \
  --idioma pt \
  --limpar-tmp \
  --saida-dir "edicao"
```

O comando imprime um JSON listando cada pasta `edicao/hf_<slug>` gerada, duração real, status da facecam e contagem de palavras transcritas.

---

## 3. Variante de Lote: Compilado Estilo TOP (`batch-top`)

Quando o usuário pedir especificamente um **compilado de ranking (`TOP 5`, `TOP 3 REAÇÕES`, etc.)**:
- Sem banner de papel na abertura.
- Lista `1..N` sempre visível no canto inferior esquerdo sobre gradiente escuro suave, com os nomes ocultos por **cadeado + barra fosca** e liberados um a um em ordem regressiva (`N -> 1`) conforme cada corte entra com `sfx_transicao.wav`.
- Cabeçalho do TOP aparece em destaque Hero (`scale 1.0`) nos primeiros `3.0s` e reduz para `scale 0.56`.
- Legendas centralizadas exatamente na divisória (`y = 768px`).

Crie um arquivo `top_config.json`:
```json
{
  "slug": "hf_top-reacoes",
  "titulo": "TOP 5 REAÇÕES",
  "subtitulo": "DESCOBERTAS NO MAPA",
  "bottomPx": 240,
  "gradientOpacity": 0.85,
  "heroSec": 3.0,
  "itens": [
    { "rank": 5, "nome": "Criador E", "fonte": "https://...", "inicio": "00:10:12", "fim": "00:10:28", "facecam": "auto" },
    { "rank": 4, "nome": "Criador D", "fonte": "https://...", "inicio": "01:04:00", "fim": "01:04:19", "facecam": "auto" }
  ]
}
```
E execute:
```bash
python "<SKILL_DIR>/scripts/cutter_pipeline.py" batch-top \
  --top-json "edicao/top_config.json" \
  --idioma pt \
  --limpar-tmp \
  --saida-dir "edicao"
```

---

## 4. Validação, Render e Entrega por Corte

Para cada pasta `edicao/hf_<slug>` gerada:
1. Defina `HYPERFRAMES_BROWSER_PATH` apontando para o Chrome/Edge detectado no `doctor`.
2. Rode `<HF_CLI> check --json` dentro de `edicao/hf_<slug>`.
3. Rode `<HF_CLI> snapshot --at 0.5,2.5,5.4,10.0` e inspecione visualmente os frames salvos (verifique se o rosto do streamer está centralizado no topo e se o banner desenrola/enrola limpo).
4. Renderize para a pasta final:
   `<HF_CLI> render --quality delivery -o "cortes/<pasta-origem>/<slug>.mp4"`
5. Gere obrigatoriamente `cortes/<pasta-origem>/<slug>.txt` usando as regras de [hyperframes-e-seo.md](./hyperframes-e-seo.md).
