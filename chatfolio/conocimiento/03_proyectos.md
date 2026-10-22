# Proyectos de Lleyton Murphy

## Proyecto de Lleyton: Vaca Muerta Analytics, declinación y reservas de pozos (energía / Oil & Gas)
- **Problema:** estimar cuánto van a producir los pozos de Vaca Muerta y detectar a tiempo los que se desvían de lo esperado, usando datos públicos que hay que descargar, limpiar y validar.
- **Qué hizo Lleyton:**
  - Construyó un pipeline ETL que descarga, limpia y valida la producción oficial de más de 2.400 pozos (Secretaría de Energía, 2006–2026). Se actualiza solo cada mes con GitHub Actions.
  - Ajustó curvas de declinación de Arps para estimar reservas (EUR) y las validó con backtesting sobre producción que el modelo no había visto: alrededor de 9 % de error en el total de pozos a 36 meses.
  - Automatizó con n8n un monitoreo mensual que detecta pozos desviados de su curva esperada (posibles fallas o intervenciones) y manda alertas por Telegram.
- **Stack:** Python, SciPy, Streamlit, GitHub Actions, n8n.
- **Link:** https://murphylleyton05-lgtm.github.io/portfolio/hidrocarburos/

## Proyecto de Lleyton: Vaca Muerta Operations Intelligence + Well Performance ML
- **Qué hizo Lleyton:**
  - Armó un tablero de producción de petróleo y gas, pozos nuevos y ranking de 38 operadoras, con medidas DAX para Power BI.
  - Entrenó una regresión ridge y un random forest (train/test 70/30) para medir cuánto del rendimiento de un pozo se explica por el diseño de fractura y cuánto por la geología.
- **Stack:** Power BI (DAX), Python, machine learning.
- **Links:** tablero de operaciones https://murphylleyton05-lgtm.github.io/portfolio/operaciones/ · modelo de Well Performance https://murphylleyton05-lgtm.github.io/portfolio/performance/

## Proyecto de Lleyton: Frac Sand & Fuel Logistics, supply chain de arena de fractura
- **Qué hizo Lleyton:** modeló la logística de arena de fractura a partir del consumo real por pozo: política de reposición (s, S), lead time, OTIF, stock de seguridad, quiebres de stock y costo logístico.
- **Stack:** Python, pandas.
- **Link:** https://murphylleyton05-lgtm.github.io/portfolio/logistica/

## Proyecto de Lleyton: TechStore, sistema de BI end-to-end (Coderhouse)
- **Qué hizo Lleyton:**
  - Diseñó una base de datos relacional en tercera forma normal (PK/FK) y consultas de negocio con CTEs, INNER/LEFT JOIN, GROUP BY/HAVING y CASE.
  - Desarrolló el ETL en Power Query (duplicados, nulos, tipos de dato, Merge) y un modelo estrella en Power BI con medidas DAX.
  - Diseñó un dashboard ejecutivo en Excel sobre 2.400 operaciones, con KPIs contra meta, 4 segmentadores y gráfico de cascada.
  - Automatizó un reporte financiero en Excel con Power Query, macros VBA y análisis de VAN/TIR a 5 años.
- **Stack:** PostgreSQL, Power Query, Power BI, Excel, VBA.
- **Código:** https://github.com/murphylleyton05-lgtm/entrega-final-coderhouse

## Proyecto de Lleyton: Calificación de leads con IA y aprobación humana (proyecto final Coderhouse)
- **Problema:** calificar leads y responder con propuestas personalizadas sin perder control humano sobre lo que se envía.
- **Qué hizo Lleyton:**
  - Automatizó el circuito completo: webhook → alta en Airtable → clasificación y propuesta personalizada con Claude → aprobación humana en Slack → envío por Gmail.
  - Sumó manejo de errores (Error Trigger, log de fallos y protección anti-loop) y validó el flujo con 5 escenarios de prueba.
- **Stack:** n8n, Claude API, Airtable, Slack, Gmail.
- **Código:** https://github.com/murphylleyton05-lgtm/entrega-final-coderhouse

## Proyecto de Lleyton: serie de agentes de IA en n8n
- **Qué hizo Lleyton:** desarrolló un orquestador multi-agente Manager–Worker, un agente con memoria persistente, un agente de soporte con RAG integrado a Gmail, HubSpot y Slack, un agente de voz (Whisper) y un supervisor de calidad AI-as-a-Judge.
- **Stack:** n8n, OpenAI, Whisper, HubSpot.
- **Código:** https://github.com/murphylleyton05-lgtm/portfolio

## Proyecto de Lleyton: Agente de Búsqueda Laboral Remota (n8n · Tools Agent)
- **Problema:** buscar vacantes remotas reales y llevar el seguimiento a mano lleva mucho tiempo.
- **Qué hizo Lleyton:** construyó en n8n un agente conversacional (AI Agent en modo Tools Agent) que consulta en tiempo real el board de empleos remotos de Remotive y devuelve hasta 5 vacantes reales con empresa, ubicación, salario (si está publicado) y link para postularse. Si el usuario lo pide, guarda la vacante en una planilla de Google Sheets de seguimiento.
- **Decisiones de diseño:** system prompt modular (Rol → Ámbito → Objetivo → Reglas → Escalamiento → Herramientas), reglas para no inventar vacantes ni URLs, máximo 6 iteraciones del agente y herramientas que dicen cuándo usarlas y cuándo no.
- **Observabilidad:** cada conversación queda registrada en una Data Table de n8n y se envía un reporte por Gmail.
- **Stack:** n8n, OpenAI GPT-4o, API de Remotive, Google Sheets, Gmail, n8n Data Tables.
- **Código:** https://github.com/murphylleyton05-lgtm/checkpoint1-lleyton-murphy

## Proyecto de Lleyton: Chatfolio, este portfolio conversacional
- **Problema:** un CV en PDF no responde preguntas abiertas.
- **Qué hizo Lleyton:** una web donde reclutadores y clientes conversan con un asistente que responde sobre su experiencia, proyectos y stack, analiza si encaja en una búsqueda laboral y toma los datos de contacto del visitante para avisarle por email.
- **Cómo funciona:** un agente de n8n (gpt-4o-mini, memoria por sesión) con RAG agéntico: elige qué archivo de su base de conocimiento leer y lo trae en vivo desde GitHub, con reglas para no inventar. Si la IA no está disponible, la web busca en la misma base desde el navegador, así nunca queda sin responder.
- **Desafío principal:** el CV solo no alcanza para preguntas abiertas, así que Lleyton sumó fuentes (perfil, proyectos con contexto, stack y preguntas frecuentes) y las escribió en bloques autocontenidos para que la búsqueda encuentre el fragmento correcto.
- **Stack:** n8n, OpenAI, Gmail, HTML/CSS/JavaScript, GitHub Pages y GitHub Actions.
- **Link:** https://murphylleyton05-lgtm.github.io/portfolio/chat/
