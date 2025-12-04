-- =========================================================
-- 01_ddl_cafe_marketplace.sql
-- Script DDL: creación de BD y tablas con PK/FK/NOT NULL/CHECK
-- =========================================================

DROP DATABASE IF EXISTS cafe_marketplace;
CREATE DATABASE cafe_marketplace
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE cafe_marketplace;

-- =========================================================
-- Tabla: plans
-- =========================================================
DROP TABLE IF EXISTS plan_features;
DROP TABLE IF EXISTS brand_grind_options;
DROP TABLE IF EXISTS brand_images;
DROP TABLE IF EXISTS grind_options;
DROP TABLE IF EXISTS coffee_brands;
DROP TABLE IF EXISTS plans;

CREATE TABLE plans (
  id VARCHAR(50) PRIMARY KEY,
  name VARCHAR(100) NOT NULL,
  description TEXT NULL,
  price_monthly INT NOT NULL,
  max_brands_to_choose INT NOT NULL,
  CONSTRAINT chk_price_monthly CHECK (price_monthly > 0),
  CONSTRAINT chk_max_brands CHECK (max_brands_to_choose >= 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- =========================================================
-- Tabla: plan_features
-- =========================================================
CREATE TABLE plan_features (
  id INT AUTO_INCREMENT PRIMARY KEY,
  plan_id VARCHAR(50) NOT NULL,
  feature_text VARCHAR(255) NOT NULL,
  CONSTRAINT fk_plan_features_plan
    FOREIGN KEY (plan_id)
    REFERENCES plans(id)
    ON DELETE CASCADE
    ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- =========================================================
-- Tabla: coffee_brands
-- =========================================================
CREATE TABLE coffee_brands (
  id VARCHAR(50) PRIMARY KEY,
  name VARCHAR(100) NOT NULL,
  origin VARCHAR(100) NULL,
  description TEXT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- =========================================================
-- Tabla: grind_options (catálogo de tipos de molienda)
-- =========================================================
CREATE TABLE grind_options (
  id VARCHAR(50) PRIMARY KEY,
  label VARCHAR(100) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- =========================================================
-- Tabla: brand_grind_options (relación N:M marca - molienda)
-- =========================================================
CREATE TABLE brand_grind_options (
  id INT AUTO_INCREMENT PRIMARY KEY,
  brand_id VARCHAR(50) NOT NULL,
  grind_id VARCHAR(50) NOT NULL,
  CONSTRAINT fk_bgo_brand
    FOREIGN KEY (brand_id)
    REFERENCES coffee_brands(id)
    ON DELETE CASCADE
    ON UPDATE CASCADE,
  CONSTRAINT fk_bgo_grind
    FOREIGN KEY (grind_id)
    REFERENCES grind_options(id)
    ON DELETE CASCADE
    ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- =========================================================
-- Tabla: brand_images
-- =========================================================
CREATE TABLE brand_images (
  id INT AUTO_INCREMENT PRIMARY KEY,
  brand_id VARCHAR(50) NOT NULL,
  type VARCHAR(50) NOT NULL,    -- logo | banner
  url  VARCHAR(255) NOT NULL,
  CONSTRAINT fk_brand_images_brand
    FOREIGN KEY (brand_id)
    REFERENCES coffee_brands(id)
    ON DELETE CASCADE
    ON UPDATE CASCADE,
  CONSTRAINT chk_brand_image_type
    CHECK (type IN ('logo','banner'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;