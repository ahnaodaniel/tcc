# Registro de decisões (ADR leve)

Decisões delegadas ao agente durante a refatoração do SPECTRA. Formato: decisão + motivo.

## Fase 0 — Higiene

**D-001 — Versão do Python: 3.10 a 3.12, alvo 3.12.**
MediaPipe (`mediapipe==0.10.21`) publica wheels para Windows até CPython 3.12; não há wheel
para 3.13. 3.12 é o maior denominador comum entre o Windows do autor e o WSL de desenvolvimento.

**D-002 — Configuração do pytest no `pyproject.toml`, sem `pytest.ini`.**
O enunciado pedia os dois, mas `pytest.ini` tem precedência sobre `pyproject.toml` e a presença
dos dois esconderia a configuração. Mantida uma única fonte da verdade (`[tool.pytest.ini_options]`),
conforme a decisão fixa de usar `pyproject.toml` para black/isort/ruff/pytest.

**D-003 — Cobertura configurada em `.coveragerc`.**
Mantido arquivo separado porque a decisão fixa sobre `pyproject.toml` não cita cobertura e os
repositórios de referência do autor usam `.coveragerc`.

**D-004 — `hand_landmarker.task` continua versionado.**
O arquivo já está no histórico do Git (removê-lo não reduz o tamanho do repositório) e mantê-lo
permite rodar offline. O `.gitignore` ignora qualquer outro `*.task` (cópias baixadas no diretório
de dados), com exceção explícita para a cópia da raiz.

**D-005 — `requirements.txt` (runtime) separado de `requirements-dev.txt` (lint/teste).**
A máquina de testes headless não precisa de MediaPipe nem de webcam; a separação evita instalar
o stack de visão em CI.

**D-006 — Versões fixadas (`==`) nas dependências de runtime.**
Reprodutibilidade é requisito de um TCC: o avaliador precisa conseguir reproduzir o ambiente.
`numpy` usa faixa (`>=1.26,<2.2`) por ser dependência transitiva compartilhada.

## Fase 1 — Separação em pacote

**D-007 — Texto na tela passa por uma dobra ASCII (`spectra/ui/text.py`).**
O OpenCV só tem fontes vetoriais Hershey, que não renderizam acentos: `"Educação"` sairia
corrompido. O catálogo mantém o pt-BR correto (necessário para relatórios e painel) e a camada
de desenho remove os diacríticos no último momento. Alternativa descartada: embutir uma fonte
TrueType via Pillow — custo de desempenho por frame e mais uma dependência no app do paciente.

**D-008 — A detecção retorna `DetectionResult`/`DetectedHand` em vez de duas listas paralelas.**
O código original passava `lm_list` e `hd_list` juntos e reconstruía a rotulagem em cada modo.
Um objeto com `for_label()` já implementa a decisão fixa de "uma mão por sessão".

**D-009 — MediaPipe é importado de forma tardia (dentro de `HandDetector.__init__`).**
Permite importar qualquer módulo do pacote — e rodar toda a suíte de testes — em Linux/WSL sem o
stack de visão instalado.

**D-010 — `winsound` isolado em `spectra/ui/sound.py` por trás de `SoundPlayer`.**
Fora do Windows o import falha e todo beep vira *no-op*, sem `try/except` espalhado pelo código.

**D-011 — Os valores dos enums `AppMode` e `PhysioExercise` são chaves de i18n.**
`AppMode.PHYSIO.value == "physio"` resolve `mode.physio` no catálogo, eliminando um mapa paralelo
entre enum e rótulo e garantindo que todo modo novo precise de tradução.

**D-012 — `logging` no lugar de `print`, e `ESC` como saída de emergência.**
O painel e os testes precisam capturar as mensagens. A interação do paciente continua 100% por
gestos; `ESC` existe apenas como interrupção de segurança para o fisioterapeuta.

**D-013 — Modo "Desenho Guiado" fora do menu até a fase 3.**
A fase 1 é movimentação de código sem mudança de comportamento; o item do menu seria um botão
morto. A entrada do enum já existe (`AppMode.GUIDED_DRAW`).

**D-014 — Saídas gravadas no diretório de dados, nunca no diretório de trabalho.**
`pintura_*.png` vai para `<data_dir>/drawings` e o CSV de fisioterapia para `<data_dir>/exports`.
Era a causa do PNG solto na raiz do repositório.

