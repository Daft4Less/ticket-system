# Sistema de Reservas de Entradas — Práctica de Tolerancia a Fallos

Sistema de venta de entradas para eventos, desplegado sobre un clúster Kubernetes
real de 2 nodos, con mecanismos de resiliencia frente a fallos comunes en sistemas
distribuidos.

## Integrantes
- Daniela Auquilla (dani5G)
- José Salamea (Daft4Less)

## Arquitectura

El sistema está compuesto por 6 componentes:

- **API Gateway** - punto de entrada único para los clientes (gateway/)
- **Reservas (Core)** - orquesta la compra: Inventario, Pagos y Notificaciones (reservas/)
- **Inventario** - verifica y descuenta asientos disponibles, con persistencia en PostgreSQL (inventario/)
- **Pagos (stub)** - simula el cobro, con latencia y fallos aleatorios (pagos-stub/)
- **Notificaciones (stub)** - simula el envio de confirmacion por email (notificaciones-stub/)
- **Base de Datos** - PostgreSQL 16

Todos los servicios propios estan escritos en Python con FastAPI y se comunican
entre si via REST (HTTP/JSON) usando httpx.

## Infraestructura

El cluster corre sobre k3s (Kubernetes liviano), con 2 nodos fisicos:

- danipc - control-plane (maquina de Daniela)
- daft - worker (maquina de Jose)

Como ambas maquinas trabajan desde redes distintas (universidad, y luego cada casa),
los dos nodos estan conectados mediante una red privada Tailscale, que les da una
IP fija sin importar en que red fisica esten.

El Servicio de Inventario esta desplegado con 2 replicas, forzadas mediante una regla
de podAntiAffinity a quedar repartidas una en cada nodo - asi, si un nodo se cae,
la otra replica sigue funcionando.

## Como desplegar el sistema

### 1. Requisitos previos
- 2 maquinas con Ubuntu (o WSL2 en Windows) y Docker instalado.
- k3s instalado: un nodo como server, el otro como agent, conectados por Tailscale.
- Ambos nodos deben verse entre si (tailscale ip -4 y hacer ping cruzado).

### 2. Aplicar los manifiestos de Kubernetes

Todos los manifiestos estan en la carpeta k8s/. Desde el nodo server:

kubectl apply -f k8s/

Esto crea, en orden: la base de datos PostgreSQL, y los 5 servicios (Inventario,
Pagos, Notificaciones, Reservas, Gateway), cada uno con su Deployment y Service.

### 3. Verificar que todo quedo corriendo

kubectl get pods -o wide

Deberian verse 7 pods en estado Running, con las 2 replicas de inventario
repartidas entre los dos nodos (columna NODE).

### 4. Probar una compra completa

El Gateway expone un NodePort en el puerto 30080:

curl -X POST "http://localhost:30080/purchase?event_id=concierto-2026&email=cliente@example.com&amount=15"

Deberia devolver un JSON con "purchase_status": "completed", mostrando el
resultado de cada paso (inventario, pago, notificacion).

## Imagenes Docker

Las 5 imagenes estan publicadas publicamente en Docker Hub bajo la cuenta danielaag5:

- danielaag5/gateway
- danielaag5/reservas
- danielaag5/inventario
- danielaag5/pagos-stub
- danielaag5/notificaciones-stub

Los manifiestos en k8s/ ya apuntan a las versiones correctas de cada una.

## Mecanismos de resiliencia implementados

| Fallo | Patron | Donde |
|---|---|---|
| Inventario Fantasma | Retry con backoff exponencial (tenacity) | reservas/ |
| Pasarela Lenta | Circuit Breaker (aiobreaker) | reservas/ |
| Diluvio de Peticiones | Bulkhead (asyncio.Semaphore) | gateway/ |
| Correo Perdido | Fallback | reservas/ |

Los otros 2 fallos del catalogo (Base de Datos Intermitente y Condicion de Carrera)
se analizan a nivel teorico en el informe, sin implementacion de codigo.

## Estructura del repositorio

- gateway/ - API Gateway
- reservas/ - Servicio de Reservas (Core)
- inventario/ - Servicio de Inventario
- pagos-stub/ - Stub de Pagos
- notificaciones-stub/ - Stub de Notificaciones
- k8s/ - Manifiestos de Kubernetes
- docs/ - Documentacion de la Parte II (catalogo de fallos)
- README.md
