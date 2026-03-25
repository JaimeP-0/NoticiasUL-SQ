-- ============================================
-- Script SQL para inicializar la base de datos
-- ============================================
-- Ejecutar este script después de crear la base de datos
-- mysql -u root -p noticias_ul < init_database.sql

-- Crear base de datos si no existe
CREATE DATABASE IF NOT EXISTS noticias_ul CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE noticias_ul;

-- Tabla de usuarios_nul
CREATE TABLE IF NOT EXISTS usuarios_nul (
    idUsuario INT AUTO_INCREMENT PRIMARY KEY,
    usuario VARCHAR(50) UNIQUE NOT NULL,
    contrasena VARCHAR(255) NOT NULL,
    nombre VARCHAR(100),
    email VARCHAR(100),
    rol VARCHAR(20) DEFAULT 'usuario',
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_usuario (usuario)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tabla de noticias_nul
CREATE TABLE IF NOT EXISTS noticias_nul (
    id INT AUTO_INCREMENT PRIMARY KEY,
    titulo VARCHAR(255) NOT NULL,
    contenido TEXT NOT NULL,
    autor VARCHAR(100) NOT NULL,
    fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    imagen_url VARCHAR(500),
    usuario_id INT,
    INDEX idx_fecha (fecha),
    INDEX idx_autor (autor),
    INDEX idx_titulo (titulo),
    INDEX idx_fecha_desc (fecha DESC)  -- Índice optimizado para ORDER BY fecha DESC
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Insertar usuario superadmin por defecto
-- Password: '1234' (en producción usar hash bcrypt o similar)
INSERT INTO usuarios_nul (usuario, contrasena, nombre, rol) 
VALUES ('superadmin', '1234', 'Super Administrador', 'superadmin')
ON DUPLICATE KEY UPDATE usuario=usuario;

-- Insertar usuario admin por defecto
INSERT INTO usuarios_nul (usuario, contrasena, nombre, rol) 
VALUES ('admin', '1234', 'Administrador', 'admin')
ON DUPLICATE KEY UPDATE usuario=usuario;

-- Tabla de acciones de usuarios (registro de actividades)
CREATE TABLE IF NOT EXISTS acciones_usuarios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    usuario VARCHAR(50) NOT NULL,
    accion VARCHAR(100) NOT NULL,
    nivel VARCHAR(20) NOT NULL DEFAULT 'movimiento',
    descripcion TEXT,
    ip VARCHAR(45),
    fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_usuario (usuario),
    INDEX idx_fecha (fecha),
    INDEX idx_nivel (nivel),
    INDEX idx_accion (accion)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Datos de ejemplo (opcional)
INSERT INTO noticias_nul (titulo, contenido, autor, imagen_url) VALUES
('Bienvenido a Noticias Universitarias', 'Este es el sistema de noticias universitarias. Puedes agregar noticias, comentar y más.', 'Sistema', ''),
('Cómo usar el sistema', 'Para agregar noticias, debes iniciar sesión con tu cuenta de administrador.', 'Sistema', '')
ON DUPLICATE KEY UPDATE titulo=titulo;
