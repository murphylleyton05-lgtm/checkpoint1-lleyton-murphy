# Checkpoint 1 · Agente autónomo básico (Tools Agent) en n8n

**Entregable:** [`checkpoint1_lleyton_murphy.json`](./checkpoint1_lleyton_murphy.json) (n8n → *Workflows → Import from File*).

## Flujo

```
[Chat Trigger] → [AI Agent · Tools Agent] → [Log de Observabilidad] → [Reporte de Observabilidad (Gmail)] → [Respuesta al usuario]
                      ├─ OpenAI Chat Model (gpt-4o, temperature 0)
                      ├─ Tool: buscar_vacantes_remotas (HTTP, Remotive)
                      └─ Tool: registrar_vacante_interesante (Google Sheets)
```

## Cumplimiento de la consigna

| Requisito | Implementación |
|---|---|
| Trigger | `Chat Trigger` |
| AI Agent en modo Tools Agent | Nodo `AI Agent` con el modelo y las tools conectados como sub-nodos |
| Modelo | `OpenAI Chat Model`: **gpt-4o** |
| Guardrail de iteraciones | **Max Iterations = 6** (entre 5 y 10) |
| System Prompt modular | Rol → Ámbito → Objetivo → Reglas y restricciones → Escalamiento → Herramientas. Explicita lo que **no** puede hacer y no usa lenguaje inclusivo |
| Tool lateral con descripción extensa | `buscar_vacantes_remotas` y `registrar_vacante_interesante` (Google Sheets), las dos conectadas como `ai_tool`. Cada descripción dice cuándo usarla y cuándo no |
| Sin bloques lineales antes del agente | El agente va directo después del trigger |
| Observabilidad | Log en Data Table y reporte por **Gmail** con el mensaje, la respuesta del agente y la herramienta |

## Rol del agente

"Asistente de Búsqueda Laboral Remota" de Lleyton IA Automation: busca vacantes remotas reales y guarda en Google Sheets las que el usuario pide registrar.

---

Hecho por **Lleyton Murphy**
