PY := .venv/bin/python
MODO ?= pdf
MODELO ?= claude-opus-5-5
ESFUERZO ?= medium
CONFIG := --modo $(MODO) --modelo $(MODELO) --esfuerzo $(ESFUERZO)

.PHONY: instalar test demo extraer-dev evaluar-dev evaluar-test

instalar:
	python3 -m venv .venv
	.venv/bin/pip install -e ".[dev]"

test:
	$(PY) -m pytest -q

# Circuito completo con facturas sintéticas: no usa la API ni datos reales.
demo:
	$(PY) -m facturas.cli sinteticas --n 40 --sin-qr 4
	$(PY) -m facturas.cli inyectar --origen sintetica

# Las dos siguientes llaman a la API (cuestan plata). Necesitan ANTHROPIC_API_KEY.
extraer-dev:
	$(PY) -m facturas.cli extraer $(CONFIG) --split dev

evaluar-dev:
	$(PY) -m facturas.cli evaluar $(CONFIG) --split dev

# Correr una sola vez por versión de prompt que se vaya a reportar.
evaluar-test:
	$(PY) -m facturas.cli extraer $(CONFIG) --split test
	$(PY) -m facturas.cli evaluar $(CONFIG) --split test
