# Chatfolio · Lleyton Murphy

Portfolio conversacional: en vez de leer el CV, el visitante le pregunta a un asistente por la experiencia, los proyectos y el stack de Lleyton. Puede pegar una búsqueda laboral y ver qué tanto encaja, y si quiere contactar a Lleyton, el bot toma sus datos y le avisa por Gmail.

**En vivo:** https://murphylleyton05-lgtm.github.io/portfolio/chat/

## Cómo funciona

```
 Visitante ──► web/index.html (GitHub Pages)
                  │
                  ├─ Modo IA ──► n8n: Chat Trigger ─► AI Agent (gpt-4o-mini + memoria por sesión)
                  │                                    ├─ Tool leer_base_de_conocimiento ─► conocimiento/*.md (GitHub)
                  │                                    └─ Tool avisar_a_lleyton ─────────► Gmail
                  │
                  └─ Modo sin IA (n8n sin conectar o caído) ─► busca en conocimiento/*.md desde el navegador
```

- **RAG agéntico, sin base vectorial.** El agente decide qué archivo de la base leer (perfil, experiencia, proyectos, stack o FAQ) y lo trae en vivo desde GitHub. Para actualizar lo que sabe el bot, se edita el `.md` y listo: no hay que reindexar ni volver a subir nada.
- **Nunca queda muerta.** Si n8n no está conectado o se cae, la página responde igual buscando en la misma base (puntaje tipo BM25, sin IA) y lo avisa.
- **Análisis de búsquedas.** El reclutador pega la descripción del puesto y recibe coincidencias con evidencia, lo que no figura en el perfil y una conclusión.
- **Contacto.** El agente pide nombre, email y mensaje, y le manda un email a Lleyton.
- **Bilingüe.** Si el navegador está en inglés, la interfaz está en inglés y el agente responde en inglés.
- **Vista previa para LinkedIn.** El deploy genera `og.png` (1200×627) desde `web/og.html`, así el link se comparte con una buena tarjeta de vista previa.

| Archivo | Qué es |
|---|---|
| `n8n/chatfolio.json` | El workflow de n8n (un solo archivo para importar) |
| `conocimiento/` | La base de conocimiento: perfil, experiencia, proyectos, stack y FAQ |
| `web/index.html` | La página: presentación + chat, sin dependencias |
| `web/og.html` | Plantilla de la imagen de vista previa |

## Conectar la IA (unos 10 minutos)

1. En n8n: *Workflows → Import from File* → `n8n/chatfolio.json`.
2. Asigná tus credenciales: **OpenAI** en el nodo *OpenAI Chat Model* y **Gmail** en *avisar_a_lleyton*. No hace falta nada más: la base se lee desde GitHub.
3. Probalo con el botón de chat de n8n: "¿qué hizo con datos de Vaca Muerta?", "¿cuánto cobra?", "quiero contactar a Lleyton".
4. **Publicá** el workflow, abrí el nodo *Chat Trigger* y copiá la **Production URL** (termina en `/chat`).
5. En GitHub, abrí `chatfolio/web/index.html`, tocá el lápiz, pegá la URL en `CONFIG.webhookUrl` (al final del archivo) y guardá en `main`. En 2 o 3 minutos el chat pasa a "responde con IA".

Opcional: para ver qué preguntan los visitantes, creá una Data Table `chatfolio_log` con las columnas de texto `fecha`, `session_id`, `pregunta` y `respuesta`, elegila en el nodo *Log de conversaciones (opcional)* y activalo.

### Antes de compartirlo en LinkedIn
- En OpenAI, poné un **límite de gasto mensual** (Settings → Limits). Con gpt-4o-mini cada conversación cuesta muy poco, pero un link público puede recibir tráfico inesperado.
- Probalo desde el celular: la mayoría de las visitas llegan desde la app de LinkedIn.
- Si la tarjeta del link no muestra la imagen, pasalo por el [Post Inspector de LinkedIn](https://www.linkedin.com/post-inspector/) para que la vuelva a leer.

## Actualizar lo que sabe el bot

Editá el archivo de `conocimiento/` que corresponda y guardá en `main`. Lo toman los dos modos (GitHub tarda hasta 5 minutos en servir la versión nueva).

Lo que hace que el bot responda bien:
- **Bloques autocontenidos.** Cada sección (`## ...`) se entiende sola y repite el nombre ("Lleyton trabajó en…"). En modo sin IA se muestra la sección entera que mejor coincide.
- **Títulos específicos.** El título de cada sección pesa mucho en la búsqueda: "Git, GitHub Actions y Docker" funciona mejor que "Herramientas".
- **Más allá del CV.** Proyectos contados como problema → solución → resultado, stack con evidencia y preguntas frecuentes.
- **Formato pregunta-respuesta** en `05_preguntas_frecuentes.md`: es lo que mejor coincide con lo que escribe un reclutador.
- **Nada sensible.** Todo lo que está en la base el bot lo puede decir. Por eso el teléfono del CV quedó afuera.

Si agregás un archivo nuevo, sumalo a `CONFIG.kbFiles` en `web/index.html` y a la lista de archivos del system prompt y de la herramienta en el workflow.

## Problemas comunes

| Síntoma | Causa probable |
|---|---|
| La web dice "La IA no está disponible" | La URL es la de test (no la de producción), el workflow no está publicado o n8n está apagado. Mientras tanto, la web responde con la base. |
| El agente dice que no tiene un dato que sí está | El cambio todavía no está en `main`, o GitHub sigue sirviendo la versión anterior (hasta 5 minutos). |
| El bot se "olvida" de la conversación tras reiniciar n8n | La memoria simple vive en la RAM de n8n. Para un portfolio alcanza; si querés persistirla, cambiala por Postgres Chat Memory. |
| La tarjeta de LinkedIn no tiene imagen | LinkedIn guarda la vista previa en caché: usá el Post Inspector. |

## Ideas para sumar después
- **Link de agenda (Calendly)** cuando el visitante quiere una entrevista.
- **Panel de preguntas** con la Data Table, para ver qué preguntan y qué falta en la base.
- **Base vectorial (Pinecone o Supabase)** si la base crece a decenas de documentos; con 5 archivos, leerlos enteros es más preciso y más simple.
