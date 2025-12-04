-- =========================================================
-- 02_dml_cafe_marketplace.sql
-- Script DML: datos de prueba + consultas
-- =========================================================

USE cafe_marketplace;

-- ---------------------------------------------------------
-- 1. INSERT: Datos iniciales
-- ---------------------------------------------------------

-- Planes
INSERT INTO plans (id, name, description, price_monthly, max_brands_to_choose) VALUES
('basic',    'Plan Básico',   'Ideal para probar diferentes cafés cada mes.',            45000, 1),
('standard', 'Plan Estándar', 'Para amantes del café que quieren variedad constante.',   85000, 2),
('premium',  'Plan Premium',  'Experiencia completa con cafés de especialidad.',        130000, 3);

-- Características de cada plan
INSERT INTO plan_features (plan_id, feature_text) VALUES
('basic',    '1 bolsa de 250g al mes'),
('basic',    'Envío estándar'),
('basic',    'Selección manual de café'),

('standard', '2 bolsas de 250g al mes'),
('standard', 'Envío prioritario'),
('standard', 'Acceso a cafés especiales'),

('premium',  '3 bolsas de 250g al mes'),
('premium',  'Envío gratis'),
('premium',  'Cafés de origen único'),
('premium',  'Acceso a ediciones limitadas');

-- Marcas de café
INSERT INTO coffee_brands (id, name, origin, description) VALUES
('brand_juan_valdez', 'Juan Valdez', 'Colombia', 'Café colombiano de alta calidad.'),
('brand_devocion',    'Devoción',    'Colombia', 'Café de origen con tueste reciente.'),
('brand_local',       'Café Local',  'Micro-lotes Colombia', 'Pequeños productores, café artesanal.');

-- Tipos de molienda
INSERT INTO grind_options (id, label) VALUES
('whole',        'En grano'),
('espresso',     'Molienda Espresso'),
('filter',       'Molienda para filtro'),
('french_press', 'Molienda para prensa francesa');

-- Relación marca - molienda
INSERT INTO brand_grind_options (brand_id, grind_id) VALUES
('brand_juan_valdez', 'whole'),
('brand_juan_valdez', 'espresso'),
('brand_juan_valdez', 'filter'),
('brand_juan_valdez', 'french_press'),

('brand_devocion',    'whole'),
('brand_devocion',    'filter'),

('brand_local',       'whole'),
('brand_local',       'espresso'),
('brand_local',       'filter');

-- Imágenes de marca
INSERT INTO brand_images (brand_id, type, url) VALUES
('brand_juan_valdez', 'logo',   'img/brands/juan_valdez_logo.png'),
('brand_juan_valdez', 'banner', 'img/brands/juan_valdez_banner.jpg'),

('brand_devocion',    'logo',   'img/brands/devocion_logo.png'),
('brand_devocion',    'banner', 'img/brands/devocion_banner.jpg'),

('brand_local',       'logo',   'img/brands/local_logo.png'),
('brand_local',       'banner', 'img/brands/local_banner.jpg');


-- ---------------------------------------------------------
-- 2. CONSULTAS SELECT (JOIN, GROUP BY, operaciones matemáticas)
-- ---------------------------------------------------------

-- 2.1. JOIN de 2 tablas: planes con sus características
SELECT 
  p.id,
  p.name,
  pf.feature_text
FROM plans p
JOIN plan_features pf ON p.id = pf.plan_id
ORDER BY p.id, pf.id;

-- 2.2. JOIN de 3 tablas: marca + tipos de molienda + etiqueta de la molienda
SELECT 
  b.name           AS marca,
  b.origin        AS origen,
  g.id            AS id_molienda,
  g.label         AS tipo_molienda
FROM coffee_brands b
JOIN brand_grind_options bgo ON b.id = bgo.brand_id
JOIN grind_options g         ON g.id = bgo.grind_id
ORDER BY b.name, g.label;

-- 2.3. JOIN de 4 tablas: marca + molienda + imágenes
SELECT 
  b.name    AS marca,
  g.label   AS tipo_molienda,
  i.type    AS tipo_imagen,
  i.url     AS url_imagen
FROM coffee_brands b
JOIN brand_grind_options bgo ON b.id = bgo.brand_id
JOIN grind_options g         ON g.id = bgo.grind_id
JOIN brand_images i          ON i.brand_id = b.id
ORDER BY b.name, g.label, i.type;

-- 2.4. GROUP BY: cantidad de características por plan
SELECT 
  p.id,
  p.name,
  COUNT(pf.id) AS total_caracteristicas
FROM plans p
LEFT JOIN plan_features pf ON p.id = pf.plan_id
GROUP BY p.id, p.name
ORDER BY total_caracteristicas DESC;

-- 2.5. Operación matemática: precio anual de cada plan
SELECT
  id,
  name,
  price_monthly,
  price_monthly * 12 AS precio_anual
FROM plans
ORDER BY price_monthly;


-- ---------------------------------------------------------
-- 3. Ejemplos de operaciones DML (INSERT, UPDATE, DELETE)
-- ---------------------------------------------------------

-- 3.1. INSERT de un nuevo plan
INSERT INTO plans (id, name, description, price_monthly, max_brands_to_choose)
VALUES ('office', 'Plan Oficina', 'Ideal para oficinas con alto consumo.', 200000, 3);

INSERT INTO plan_features (plan_id, feature_text) VALUES
('office', '5 bolsas de 250g al mes'),
('office', 'Envío gratis'),
('office', 'Atención prioritaria a empresas');

-- 3.2. UPDATE: cambiar el precio de un plan
UPDATE plans
SET price_monthly = 90000
WHERE id = 'standard';

-- 3.3. DELETE: eliminar una imagen de una marca
DELETE FROM brand_images
WHERE brand_id = 'brand_local'
  AND type = 'banner';

-- 3.4. Consulta final para revisar cambios
SELECT * FROM plans;
SELECT * FROM brand_images WHERE brand_id = 'brand_local';
