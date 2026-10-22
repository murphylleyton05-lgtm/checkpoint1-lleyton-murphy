# Proyectos de Lleyton Murphy

## Proyecto: Agente de Búsqueda Laboral Remota (n8n · Tools Agent)
- **Problema:** buscar vacantes remotas reales en varios sitios y llevar el seguimiento a mano lleva mucho tiempo.
- **Solución:** Lleyton construyó en n8n un agente conversacional (AI Agent en modo Tools Agent) que entiende qué rol busca la persona, consulta en tiempo real el board de empleos remotos de Remotive y devuelve hasta 5 vacantes reales, con empresa, ubicación, salario (si está publicado) y link para postularse. Cuando el usuario lo pide, guarda la vacante elegida en una planilla de Google Sheets de seguimiento.
- **Decisiones de diseño:**
  - System prompt modular: Rol → Ámbito → Objetivo → Reglas → Escalamiento → Herramientas.
  - Reglas explícitas para no inventar vacantes ni URLs.
  - Guardrail de máximo 6 iteraciones del agente.
  - Descripciones de herramientas que dicen cuándo usarlas y cuándo no.
- **Observabilidad:** cada conversación queda registrada en una Data Table de n8n y se envía un reporte por Gmail con el mensaje, la respuesta y la herramienta usada.
- **Stack:** n8n, OpenAI GPT-4o, API HTTP de Remotive, Google Sheets, Gmail, n8n Data Tables.
- **Resultado:** [COMPLETAR: qué lograste o aprendiste; ej: cuántas vacantes encontraste, feedback de la entrega.]

## Proyecto: Chatfolio, portfolio conversacional con IA
- **Problema:** un CV en PDF no responde preguntas abiertas y la típica landing personal no muestra cómo trabaja alguien con IA.
- **Solución:** Lleyton creó este chatfolio: una web donde reclutadores y clientes conversan con un asistente que responde sobre su experiencia, proyectos y stack, y que puede tomar los datos de contacto del visitante y avisarle a Lleyton por email.
- **Cómo funciona por dentro:**
  - RAG: el CV y documentos complementarios se dividen en fragmentos, se convierten en embeddings (OpenAI text-embedding-3-small) y se guardan en Pinecone.
  - Un agente de n8n (OpenAI gpt-4o-mini) busca en esa base antes de responder, con reglas para no inventar.
  - Memoria de conversación por sesión, log de cada pregunta para ver qué consultan los visitantes, y aviso por Gmail cuando alguien quiere contactar.
  - Frontend propio en HTML/JS publicado en GitHub Pages.
- **Desafío principal:** el CV solo no alcanza para preguntas abiertas, así que Lleyton amplió las fuentes (perfil, proyectos, stack con contexto y preguntas frecuentes) y las estructuró en bloques autocontenidos para que la búsqueda encuentre el fragmento correcto.
- **Stack:** n8n, OpenAI, Pinecone, HTML/CSS/JavaScript, GitHub Pages.

## Proyecto: [COMPLETAR: nombre]
- **Problema:** [COMPLETAR]
- **Solución:** [COMPLETAR]
- **Stack:** [COMPLETAR]
- **Resultado:** [COMPLETAR: con números si podés]
- **Link:** [COMPLETAR: repo, demo o video]
