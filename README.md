# ☕ Coffee Box – Sistema de suscripción de café

Proyecto académico de bases de datos y desarrollo web que implementa un **sistema de suscripción mensual de café**.  
El usuario puede:

- Elegir un **plan** (básico, estándar, premium).
- Seleccionar una o varias **marcas de café**.
- Escoger el **tipo de molienda**.
- Registrar sus datos personales para crear una suscripción.

El foco del proyecto es el **modelado e implementación de la base de datos**, integrado con un frontend web y un backend sencillo en Express.

---

## 📚 Contenido

1. [Descripción general](#-descripción-general)
2. [Tecnologías utilizadas](#-tecnologías-utilizadas)
3. [Arquitectura general](#-arquitectura-general)
4. [Modelado de datos](#-modelado-de-datos)
   - [Normalización (0FN → 3FN)](#normalización-0fn--3fn)
   - [Modelo ER extendido](#modelo-er-extendido)
   - [Modelo relacional](#modelo-relacional)
   - [Diccionario de datos](#diccionario-de-datos)
5. [Estructura del repositorio](#-estructura-del-repositorio)
6. [Scripts SQL (DDL / DML)](#-scripts-sql-ddl--dml)
7. [Ejecución del proyecto](#-ejecución-del-proyecto)
8. [Autores](#-autores)

---

## 📝 Descripción general

Coffee Box representa un **marketplace de suscripción de café**.  
A nivel de bases de datos, se resuelve el problema de:

- Modelar los **planes** y sus **características**.
- Modelar las **marcas**, **tipos de molienda** e **imágenes de marca**.
- Registrar las **suscripciones** realizadas por los clientes.

Este proyecto se alinea con la rúbrica del curso de Bases de Datos:

- Modelo ER extendido.
- Modelo relacional.
- Normalización hasta 3FN.
- Diccionario de datos.
- Implementación SQL (DDL y DML).
- Frontend funcional y conexión con la BD.

---

## 🛠 Tecnologías utilizadas

- **Frontend**
  - HTML5, CSS3, Bootstrap 5
  - JavaScript (vanilla), consumo de JSON (`catalogo.json`)

- **Backend**
  - Node.js + Express
  - CORS, dotenv, mysql2

- **Base de datos**
  - MySQL (Workbench)
  - Scripts DDL y DML en `/sql`

---

## 🏗 Arquitectura general

Vista simplificada de la arquitectura del proyecto:

```text
[ Navegador ]
   |
   |  (Live Server)  HTML / CSS / JS
   v
[ Frontend Coffee Box ]
   |
   |  fetch() JSON / API REST
   v
[ Backend Express ]
   |
   |  consultas SQL (mysql2)
   v
[ MySQL: cafe_marketplace ]
   - plans
   - plan_features
   - coffee_brands
   - grind_options
   - brand_grind_options
   - brand_images
   - customers
   - subscriptions
   - subscription_brands
