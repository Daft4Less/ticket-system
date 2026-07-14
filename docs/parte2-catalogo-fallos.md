# Parte II — Catálogo de los 6 Puntos de Fallo (Chaos Scenarios)

Este documento relaciona cada uno de los 6 escenarios de fallo especificados en la
práctica con el mecanismo técnico específico usado para provocarlo de forma
controlada sobre el clúster Kubernetes de 2 nodos desplegado en la Parte I.

| # | Fallo | Descripción | Mecanismo técnico de inyección |
|---|---|---|---|
| 1 | **El Inventario Fantasma** (Disponibilidad) | El Servicio de Inventario se cae completamente mientras se procesa una reserva | `kubectl delete pod <pod-inventario>` para eliminar una réplica en vivo, o `kubectl scale deployment inventario --replicas=0` para tumbar ambas simultáneamente |
| 2 | **La Pasarela Lenta** (Latencia) | El Servicio de Pagos tarda 20 segundos en responder, dejando conexiones colgadas | Endpoint de chaos engineering integrado en el propio stub: `POST /chaos/slow-mode` con `enabled=true`, que fuerza un `sleep(20)` en cada request de pago |
| 3 | **El Diluvio de Peticiones** (Sobrecarga) | Pico de tráfico repentino que satura el API Gateway | Script de carga con **k6** generando cientos de peticiones concurrentes contra `http://<nodo>:30080/purchase` |
| 4 | **Base de Datos Intermitente** (Conectividad) | La conexión a PostgreSQL se pierde intermitentemente (flapping) durante escrituras | `kubectl delete pod <pod-postgres>` repetido en intervalos, o una `NetworkPolicy` que bloquee/permita intermitentemente el tráfico hacia el pod de PostgreSQL |
| 5 | **El Correo Perdido** (Fallo no crítico) | El Servicio de Notificaciones está inactivo; el usuario ya pagó y tiene su entrada | Endpoint de chaos engineering integrado en el propio stub: `POST /chaos/down-mode` con `enabled=true`, que hace responder 503 a toda solicitud |
| 6 | **Condición de Carrera** (Consistencia) | Dos usuarios compran el último asiento disponible al mismo tiempo | Script con múltiples clientes concurrentes (ej. `asyncio.gather` en Python, o varios `curl` lanzados en paralelo con `&`) apuntando al mismo `event_id` simultáneamente |

## Selección para las siguientes partes

De acuerdo con la estrategia definida para este trabajo:

- **Se implementan con patrón de resiliencia (Parte III/IV):** Inventario Fantasma,
  Pasarela Lenta, Diluvio de Peticiones, Correo Perdido.
- **Se analizan solo en teoría (Parte V):** Base de Datos Intermitente,
  Condición de Carrera.

Esta elección permite implementar los fallos más "mecánicos" y demostrables en vivo,
dejando para el análisis teórico los dos escenarios que se explican mejor con
fundamentos de sistemas distribuidos (teorema CAP y modelos de concurrencia).
