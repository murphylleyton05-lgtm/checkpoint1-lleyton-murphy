# Chatfolio · Lleyton Murphy

Portfolio conversacional: en vez de leer el CV, el visitante le pregunta a un asistente de IA por la experiencia, los proyectos y el stack de Lleyton. Si quiere contactar a Lleyton, el bot toma sus datos y le avisa a Lleyton por Gmail.

## Arquitectura

```
                    ┌─────────────── Workflow 1 · Ingesta (se corre cuando actualizás tu info) ───────────────┐
 conocimiento/ ──►  │ Form Trigger (con clave) ─► Pinecone (insert, limpia namespace)                         │
                    │                               ├─ Lector de archivos ─ Divisor de texto (1000 / 150)     │
                    │                               └─ Embeddings OpenAI (text-embedding-3-small)              │
                    └──────────────────────────────────────────────────────────────────────────────────────────┘

                    ┌─────────────── Workflow 2 · Chat público ─────────────────────────────────────────────┐
 web/index.html ──► │ Chat Trigger (Embedded) ─► AI Agent ─► Log (Data Table) ─► Respuesta {output}          │
 (GitHub Pages)     │                             ├─ OpenAI gpt-4o-mini                                      │
                    │                             ├─ Memoria por sesión (10 mensajes)                        │
                    │                             ├─ Tool consultar_perfil_lleyton  (RAG en Pinecone)        │
                    │                             └─ Tool avisar_a_lleyton          (Gmail)                  │
                    └──────────────────────────────────────────────────────────────────────────────────────────┘
```

| Carpeta | Qué hay |
|---|---|
| `n8n/chatfolio_1_ingesta.json` | Formulario para subir tus archivos y cargarlos en Pinecone |
| `n8n/chatfolio_2_chat.json` | Agente público con RAG, memoria, log y aviso de contacto |
| `conocimiento/` | Plantillas de la base de conocimiento (perfil, experiencia, proyectos, stack, FAQ) |
| `web/index.html` | La página: presentación + chat propio, sin dependencias |

## Puesta en marcha

### 1. Pinecone (base vectorial, plan gratis)
1. Creá una cuenta en [pinecone.io](https://www.pinecone.io/).
2. Creá un index llamado **`chatfolio`**: dimensión **1536**, métrica **cosine** (lo que usa `text-embedding-3-small`).
3. Copiá la API key.

### 2. Credenciales en n8n
- **OpenAI**: la que ya usás en el Checkpoint 1.
- **Pinecone**: nueva, con la API key del paso 1.
- **Gmail**: la que ya usás.
- **Basic Auth**: usuario y clave a tu elección. Protege el formulario de carga para que nadie más pueda reemplazar tu información.

### 3. Revisar la base de conocimiento
`conocimiento/` ya tiene todo tu CV, con los links a cada proyecto y escrito para que el RAG lo encuentre bien. Revisalo y completá los pocos `[COMPLETAR: ...]` que quedan (modalidad, disponibilidad, qué estás aprendiendo). Lo que no quieras contar, borralo.

El teléfono quedó afuera a propósito: todo lo que está en estos archivos el bot lo puede decir.

Lo que hace que el bot responda bien (el "desafío del RAG"):
- **Bloques autocontenidos.** Cada sección se entiende sola y repite el nombre ("Lleyton trabajó en…"). El texto se corta en fragmentos de unos 1000 caracteres y el bot solo ve los fragmentos que encuentra.
- **Más allá del CV.** El CV solo no alcanza para preguntas abiertas. Por eso hay archivos de proyectos (problema → solución → resultado), stack con evidencia y preguntas frecuentes.
- **Formato pregunta-respuesta** en `05_preguntas_frecuentes.md`: es lo que mejor matchea con lo que escribe un reclutador.
- **Números concretos.** "Ahorró 6 h por semana" se recuerda; "mejoró procesos" no.
- **Nada sensible.** Nada de DNI, dirección ni teléfono personal: todo lo que esté acá el bot lo puede decir.

### 4. Workflow 1 · Ingesta
1. En n8n: *Workflows → Import from File* → `n8n/chatfolio_1_ingesta.json`.
2. Asigná las credenciales (Basic Auth en el formulario, Pinecone y OpenAI).
3. Publicá el workflow y abrí la **Production URL** del Form Trigger.
4. Subí **los 5 `.md` juntos**. No subas el CV en PDF: su contenido ya está en los `.md`, y el PDF trae tu teléfono.

Cada carga **reemplaza** lo anterior (limpia el namespace `lleyton`). Para actualizar algo, editás el archivo y volvés a subir todo.

### 5. Workflow 2 · Chat
1. Creá una Data Table `chatfolio_log` con 4 columnas de tipo texto: `fecha`, `session_id`, `pregunta`, `respuesta`.
2. Importá `n8n/chatfolio_2_chat.json`, asigná las credenciales y elegí la tabla en el nodo **Log de conversaciones**. Si el log falla, el chat sigue respondiendo igual.
3. Probalo con el botón de chat de n8n: "¿qué proyectos hizo?", "¿cuánto cobra?", "quiero contactar a Lleyton".
4. Publicá el workflow y copiá la **URL del Chat Trigger** (la de producción, no la de test).

### 6. La web (GitHub Pages, gratis)
1. En `web/index.html`, completá el bloque `CONFIG` (al final del archivo): `webhookUrl` (la URL del paso 5), `linkedin`, `email` y `cv`. Los links que quedan vacíos se ocultan solos.
2. Creá un repo público (por ejemplo `chatfolio`) y subí `index.html` y, si querés, tu CV en PDF.
3. En el repo: *Settings → Pages → Deploy from a branch → main / root*. Queda en `https://TU-USUARIO.github.io/chatfolio/`.

### 7. Antes de compartirlo en LinkedIn
- En el Chat Trigger, cambiá **Allowed Origins (CORS)** de `*` a `https://TU-USUARIO.github.io`, así solo tu página puede usar el webhook.
- En OpenAI, poné un **límite de gasto mensual** (Settings → Limits). Un chat público puede recibir tráfico inesperado. Con gpt-4o-mini cada conversación cuesta muy poco, pero el límite te cubre igual.
- Probá desde el celular: la mayoría de las visitas llegan desde la app de LinkedIn.

## Problemas comunes

| Síntoma | Causa probable |
|---|---|
| `Unsupported mime type` al subir un `.md` | Algunos sistemas mandan el `.md` sin tipo. Renombralo a `.txt` y volvé a subirlo. |
| La web dice "No pude responder" | La URL es la de test (no la de producción), el workflow no está publicado, o falta tu dominio en Allowed Origins. |
| El bot dice que no tiene información sobre algo que sí cargaste | Falta correr la ingesta, el namespace no es `lleyton` en los dos workflows, o el dato está mezclado en un bloque muy largo. |
| El bot se "olvida" de la conversación tras un reinicio de n8n | La memoria simple vive en la RAM de n8n. Para un portfolio alcanza; si querés persistirla, cambiala por Postgres Chat Memory. |

## Ideas para sumar después
- **Match con una búsqueda:** el reclutador pega la descripción del puesto y el bot explica qué tan bien encaja Lleyton, con evidencia.
- **Panel de preguntas:** con la Data Table ves qué preguntan los visitantes y qué te falta cargar en la base.
- **Link de agenda (Calendly)** cuando el visitante quiere una entrevista.
- **Imagen `og:image`** para que el link se vea con una buena tarjeta de vista previa en LinkedIn.
