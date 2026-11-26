# Extração de Momentos, Evidências Visuais e Formato `.md`

Use este manual quando precisar **extrair cortes ou arcos narrativos de um vídeo longo/URL** ou quando precisar **ler/escrever arquivos `.md` de cortes**.

---

## 1. Extração a partir de Vídeo Bruto ou Link (`extract`)

Nunca escolha momentos às cegas sem ler a transcrição com timestamps e inspecionar os quadros do vídeo.

### 1.1 Transcrição + Grade Geral de Evidências
Para vídeos de até ~40 min (ou um trecho específico `--inicio` / `--fim` de uma live longa), baixe o vídeo + transcreva em GPU CUDA + gere a prancha visual e detecção de facecam em um único comando:

```bash
python "<SKILL_DIR>/scripts/cutter_pipeline.py" extract \
  --fonte "<URL-ou-caminho-local>" \
  --idioma pt \
  --saida-dir "references/<slug-fonte>"
```
*(Para lives de várias horas onde você quer primeiro mapear a fala inteira rapidamente, adicione `--apenas-audio`, escolha as janelas quentes em `transcript_lines.txt` e depois rode `extract` com `--inicio` e `--fim` sobre a janela escolhida).*

Arquivos gerados em `references/<slug-fonte>/`:
- `source.mp4` (ou `audio.m4a`): mídia local pronta para recortes rápidos sem re-download.
- `transcript.json`: segmentos + timestamps exatos palavra a palavra (`words`).
- `transcript_lines.txt`: linhas compactas `001 [MM:SS.ss -> MM:SS.ss] fala` ideais para leitura integral pelo agente.
- `evidence/overview.jpg`: grade visual do vídeo inteiro + JSON no stdout informando se o YuNet detectou facecam fixa e sugerindo filtros `crop_600` e `crop_768`.

### 1.2 Zoom Visual em Trechos Específicos (`evidence` & `detect-cam`)
Antes de fechar cortes cirúrgicos ou configurar crops customizados (ex.: onde fica a borda colorida da webcam, um menu de estatísticas ou o saldo de dinheiro no HUD):

```bash
python "<SKILL_DIR>/scripts/cutter_pipeline.py" evidence \
  --video "references/<slug-fonte>/source.mp4" \
  --inicio "02:10" --fim "02:35" --step 1.0 --cols 5 \
  --saida "references/<slug-fonte>/evidence/trecho_posto.jpg"
```
Leia sempre a imagem `.jpg` resultante com sua ferramenta de leitura de arquivo para verificar a cena real.

---

## 2. Critérios de Curadoria (O que vira Corte)

Um bom corte vertical **sobrevive sozinho sem o vídeo longo ao redor**:

### Para o Modo 1 — Produção em Lote (`20s` a `65s` por corte)
Escolha momentos onde as 3 condições sejam verdadeiras:
1. **Abre em pensamento completo:** se a primeira frase exige o minuto anterior para fazer sentido, descarte ou recue o início.
2. **Tem virada clara:** uma descoberta, teste de mecânica, opinião forte, susto, bug absurdo ou piada que complica/prova a premissa inicial.
3. **Fecha em fala ou reação conclusiva:** sem terminar em frase cortada ou silêncio morto.

**Descarte imediatamente:** leitura de doações/chat sem contexto, telas de loading, enrolação inicial (*"então galera, voltando aqui..."*).

### Para o Modo 2 — Padrão Híbrido Narrativo (`50s` a `90s` montados)
Procure uma **saga ou mini-história em 3 atos** espalhada por `2` a `6` minutos do vídeo original (como no caso do *Corvette Sem Gasolina*, extraído de `01:30 -> 05:14`):
- **Ato 1 (Desejo + Promessa):** o criador conquista/rouba algo raro ou assume um desafio claro (`OBJETIVO: ...`).
- **Ato 2 (Escalada de Complicações):** polícia, dano, falta de recurso absurda (`$43` vs `$48` na bomba), plano improvisado para salvar a situação.
- **Ato 3 (Clímax + Reversão Irônica):** quando parece que vai dar certo, tudo desmorona no último segundo -> corte abrupto de impacto.

### Regra Obrigatória de Margens (Lead-in & Follow-through)
- **Margem Anterior (*lead-in*):** inclua **3s a 5s antes** do lance/fala principal mostrando a aproximação/construção (jamais comece no meio de uma sílaba).
- **Margem Posterior (*follow-through*):** mantenha **2,5s a 4s depois** da reação/conclusão (exceto quando usar propositalmente o *card de final abrupto* do Modo Híbrido após a punchline).
- **Passes Longos e Gols:** mostre até a bola chegar no companheiro; se resultar em gol, mostre até o fim da celebração em campo, sem replay.

---

## 3. Formato Padronizado do Arquivo `.md` de Cortes

Ao salvar uma seleção de cortes em `.md` (ou ao ler um `.md` enviado pelo usuário com `parse-md`), utilize esta estrutura:

```markdown
# Título do Vídeo ou Live Original

Fonte: https://www.youtube.com/watch?v=ID_DO_VIDEO · NomeDoCriador

## Cortes Selecionados

### 1. Slug ou Título Curto do Corte
- **Intervalo:** 00:18:10 -> 00:19:15
- **Começa em:** "Primeiras palavras faladas no trecho..."
- **Termina em:** "...últimas palavras que fecham o raciocínio."
- **Por que funciona:** Resumo curto do conflito/descoberta (usado também para guiar o SEO).
- **Gancho na tela:** Frase curta com *DESTAQUE* em amarelo

### 2. Segundo Corte Selecionado
- **Intervalo:** 00:42:05 -> 00:43:02
- **Começa em:** "..."
- **Termina em:** "..."
- **Por que funciona:** ...
- **Gancho na tela:** O trem do jogo *REALMENTE PARA?*
```

- Palavras cercadas por `*asteriscos*` em **Gancho na tela** são renderizadas automaticamente em **amarelo-ouro (`#FFE500`)** no banner de papel 3D, enquanto o restante fica em branco (`#FFFFFF`).
- Veja um exemplo real pronto em [examples/exemplo_cortes_lote.md](../examples/exemplo_cortes_lote.md).
