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
