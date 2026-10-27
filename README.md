# LevelUp English — B2 to C1

MVP full-stack para diagnosticar y seguir el progreso de inglés entre A1 y C1. La experiencia principal es una evaluación general de 100 preguntas —25 de **Speaking**, **Writing**, **Reading** y **Listening**— con guardado automático después de cada respuesta.

## Qué incluye

- Registro e inicio de sesión por usuario (o correo) con contraseñas `bcrypt` y JWT con expiración configurable.
- Selector de nivel A1, A2, B1, B2 o C1 y 100 preguntas por evaluación.
- Generación dinámica con Ollama: cada evaluación recibe 100 preguntas nuevas y únicas.
- Reading con textos y Listening reproducible mediante la síntesis de voz del navegador.
- Evaluación reanudable: la respuesta, módulo actual y progreso quedan persistidos.
- Dashboard con historial, puntuación total, desglose por habilidad y recomendaciones.
- Salida JSON estructurada, validada antes de persistir cada lote generado.
- UI responsive en español, API documentada por OpenAPI y pruebas de integración.

## Arquitectura

```text
.
├── backend/              FastAPI + SQLAlchemy + PostgreSQL
│   ├── app/              API, autenticación, modelos y generación con Ollama
│   └── tests/            pruebas de integración sobre SQLite aislado
├── frontend/             React + Vite
├── .env.example          contrato único de configuración
├── docker-compose.yml    frontend + backend + PostgreSQL
└── Makefile              atajos de desarrollo
```

## Inicio rápido con Docker

Requisitos: Docker Desktop, Docker Compose y [Ollama](https://ollama.com/) ejecutándose en el equipo anfitrión.

Primero instala/inicia el modelo local:

```bash
ollama run qwen3.8
```

Para que el backend dentro de Docker pueda conectarse, Ollama debe escuchar en una interfaz accesible y no solo en `127.0.0.1`. Configura `OLLAMA_HOST=0.0.0.0:11434`, reinicia Ollama y limita el acceso al puerto mediante el firewall del equipo.

Cuando Ollama y el modelo estén disponibles, el resto del stack se puede encender directamente desde Docker Desktop, o por terminal:

```bash
cp .env.example .env
# Cambia POSTGRES_PASSWORD y JWT_SECRET en .env
docker compose up --build
```

Abre [http://localhost:3000](http://localhost:3000). La API vive en [http://localhost:8000](http://localhost:8000) y Swagger en [http://localhost:8000/docs](http://localhost:8000/docs).

El archivo `.env` de la raíz es el único archivo de variables y no se versiona. El backend usa `http://host.docker.internal:11434` para comunicarse con Ollama en macOS/Windows; `extra_hosts: host-gateway` proporciona el equivalente en Linux. `VITE_API_URL` debe ser una URL alcanzable desde el navegador.

## Desarrollo local

Requisitos: Python 3.11+, Node.js 20+ y PostgreSQL 15+ (también se puede usar SQLite para una prueba rápida).

```bash
cp .env.example .env
python3 -m venv b2toc1venv
source b2toc1venv/bin/activate
pip install -r backend/requirements-dev.txt
npm --prefix frontend install
```

Para ejecutar sin PostgreSQL, cambia temporalmente en `.env`:

```dotenv
DATABASE_URL=sqlite:///./b2toc1.sqlite3
```

Luego, en dos terminales:

```bash
make dev-backend
make dev-frontend
```

## Pruebas y compilación

```bash
make test
npm --prefix frontend run build
```

Las pruebas usan una base SQLite en memoria: no modifican la base de desarrollo.

## Generación local con Ollama

La configuración predeterminada es:

```dotenv
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=qwen3.8
OLLAMA_TIMEOUT_SECONDS=300
```

Al crear una evaluación, la API solicita cuatro lotes estructurados de 25 preguntas —uno por módulo—, valida opciones, respuesta correcta, contexto y tamaños, y persiste el conjunto completo en PostgreSQL. Reanudar una evaluación nunca vuelve a llamar al modelo. La primera generación puede tardar varios minutos según el equipo.

No existe un banco de preguntas ni un fallback pregrabado. Si Ollama está apagado, el modelo no existe o responde con datos inválidos, la API devuelve `503` con una instrucción útil y revierte la evaluación incompleta.

## Endpoints principales

| Método | Ruta | Descripción |
|---|---|---|
| POST | `/api/auth/register` | Crear usuario y emitir JWT |
| POST | `/api/auth/login` | Autenticar usuario |
| GET | `/api/auth/me` | Obtener usuario actual |
| POST | `/api/assessments` | Crear o recuperar evaluación activa |
| GET | `/api/assessments/current` | Reanudar evaluación |
| POST | `/api/assessments/{id}/answers` | Guardar y corregir respuesta |
| GET | `/api/assessments/{id}/results` | Obtener puntuaciones |
| GET | `/api/dashboard` | Progreso, historial y recomendaciones |

## Notas de seguridad y producción

- Sustituye `JWT_SECRET` por al menos 32 bytes aleatorios y usa una contraseña de PostgreSQL robusta.
- Sirve frontend y API sobre HTTPS. Restringe `CORS_ORIGINS` al dominio real.
- El JWT se guarda en `localStorage` para simplificar este MVP. Para un despliegue público de alta seguridad, migra a cookies `HttpOnly`, `Secure` y protección CSRF.
- La creación de tablas integrada facilita el MVP; para evolución en producción conviene incorporar Alembic.
- Todo el contenido generado permanece en la infraestructura local; no se utiliza ningún servicio de IA externo.
