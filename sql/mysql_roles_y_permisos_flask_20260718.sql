-- Respaldo de usuarios, roles y permisos SQL usados por la app Flask
-- Generado el 2026-07-18
-- Base de datos objetivo: hobbys_car_audio

-- Usuarios MySQL usados por la app

CREATE USER IF NOT EXISTS `admin_app`@`localhost` IDENTIFIED BY 'Cont5445';
GRANT USAGE ON *.* TO `admin_app`@`localhost`;
GRANT SELECT ON `hobbys_car_audio`.`configuracionsistema` TO `admin_app`@`localhost`;
GRANT EXECUTE ON PROCEDURE `hobbys_car_audio`.`sp_ventas_historial` TO `admin_app`@`localhost`;
GRANT `Administrador`@`%` TO `admin_app`@`localhost`;

CREATE USER IF NOT EXISTS `vendedor_app`@`localhost` IDENTIFIED BY 'Cont5445';
GRANT USAGE ON *.* TO `vendedor_app`@`localhost`;
GRANT SELECT ON `hobbys_car_audio`.`configuracionsistema` TO `vendedor_app`@`localhost`;
GRANT EXECUTE ON PROCEDURE `hobbys_car_audio`.`sp_ventas_historial` TO `vendedor_app`@`localhost`;
GRANT `Vendedor`@`%` TO `vendedor_app`@`localhost`;

CREATE USER IF NOT EXISTS `almacen_app`@`localhost` IDENTIFIED BY 'Cont5445';
GRANT USAGE ON *.* TO `almacen_app`@`localhost`;
GRANT SELECT ON `hobbys_car_audio`.`configuracionsistema` TO `almacen_app`@`localhost`;
GRANT `Almacenista`@`%` TO `almacen_app`@`localhost`;

CREATE USER IF NOT EXISTS `produccion_app`@`localhost` IDENTIFIED BY 'Cont5445';
GRANT USAGE ON *.* TO `produccion_app`@`localhost`;
GRANT SELECT ON `hobbys_car_audio`.`configuracionsistema` TO `produccion_app`@`localhost`;
GRANT `Produccion`@`%` TO `produccion_app`@`localhost`;

CREATE USER IF NOT EXISTS `consulta_app`@`localhost` IDENTIFIED BY 'Cont5445';
GRANT USAGE ON *.* TO `consulta_app`@`localhost`;
GRANT SELECT ON `hobbys_car_audio`.`configuracionsistema` TO `consulta_app`@`localhost`;
GRANT `Consulta`@`%` TO `consulta_app`@`localhost`;

CREATE USER IF NOT EXISTS `cliente_app`@`localhost` IDENTIFIED BY 'Cont5445';
GRANT USAGE ON *.* TO `cliente_app`@`localhost`;
GRANT SELECT, UPDATE ON `hobbys_car_audio`.`alertasistema` TO `cliente_app`@`localhost`;
GRANT SELECT ON `hobbys_car_audio`.`configuracionsistema` TO `cliente_app`@`localhost`;
GRANT EXECUTE ON PROCEDURE `hobbys_car_audio`.`sp_ventas_registrar` TO `cliente_app`@`localhost`;
GRANT `Cliente`@`%` TO `cliente_app`@`localhost`;

-- Roles MySQL usados por la app

CREATE ROLE IF NOT EXISTS `Administrador`@`%`;
GRANT RELOAD, PROCESS, REPLICATION SLAVE, REPLICATION CLIENT ON *.* TO `Administrador`@`%`;
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, DROP, REFERENCES, INDEX, ALTER, CREATE TEMPORARY TABLES, LOCK TABLES, EXECUTE, SHOW VIEW, EVENT, TRIGGER ON `hobbys_car_audio`.* TO `Administrador`@`%`;
GRANT SELECT ON `hobbys_car_audio`.`cliente` TO `Administrador`@`%`;
GRANT SELECT, UPDATE ON `hobbys_car_audio`.`persona` TO `Administrador`@`%`;
GRANT SELECT ON `hobbys_car_audio`.`rol` TO `Administrador`@`%`;
GRANT SELECT, INSERT, UPDATE ON `hobbys_car_audio`.`sesionusuario` TO `Administrador`@`%`;
GRANT SELECT, UPDATE ON `hobbys_car_audio`.`usuario` TO `Administrador`@`%`;
GRANT EXECUTE ON PROCEDURE `hobbys_car_audio`.`sp_ventas_historial` TO `Administrador`@`%`;

CREATE ROLE IF NOT EXISTS `Vendedor`@`%`;
GRANT USAGE ON *.* TO `Vendedor`@`%`;
GRANT SELECT ON `hobbys_car_audio`.`cliente` TO `Vendedor`@`%`;
GRANT SELECT, UPDATE ON `hobbys_car_audio`.`persona` TO `Vendedor`@`%`;
GRANT SELECT ON `hobbys_car_audio`.`productoterminado` TO `Vendedor`@`%`;
GRANT SELECT ON `hobbys_car_audio`.`rol` TO `Vendedor`@`%`;
GRANT SELECT, INSERT, UPDATE ON `hobbys_car_audio`.`sesionusuario` TO `Vendedor`@`%`;
GRANT SELECT ON `hobbys_car_audio`.`solicitudproduccion` TO `Vendedor`@`%`;
GRANT SELECT, UPDATE ON `hobbys_car_audio`.`usuario` TO `Vendedor`@`%`;
GRANT EXECUTE ON PROCEDURE `hobbys_car_audio`.`sp_solicitudproduccion_crear` TO `Vendedor`@`%`;
GRANT EXECUTE ON PROCEDURE `hobbys_car_audio`.`sp_ventas_historial` TO `Vendedor`@`%`;
GRANT EXECUTE ON PROCEDURE `hobbys_car_audio`.`sp_ventas_registrar` TO `Vendedor`@`%`;

CREATE ROLE IF NOT EXISTS `Almacenista`@`%`;
GRANT USAGE ON *.* TO `Almacenista`@`%`;
GRANT SELECT, UPDATE ON `hobbys_car_audio`.`alertasistema` TO `Almacenista`@`%`;
GRANT SELECT ON `hobbys_car_audio`.`cliente` TO `Almacenista`@`%`;
GRANT SELECT ON `hobbys_car_audio`.`compramateriaprima` TO `Almacenista`@`%`;
GRANT SELECT ON `hobbys_car_audio`.`compramateriaprimadetalle` TO `Almacenista`@`%`;
GRANT SELECT, INSERT, UPDATE ON `hobbys_car_audio`.`materiaprima` TO `Almacenista`@`%`;
GRANT SELECT ON `hobbys_car_audio`.`movimientomateriaprima` TO `Almacenista`@`%`;
GRANT SELECT, UPDATE ON `hobbys_car_audio`.`persona` TO `Almacenista`@`%`;
GRANT SELECT, INSERT, UPDATE ON `hobbys_car_audio`.`productoterminado` TO `Almacenista`@`%`;
GRANT SELECT, INSERT, UPDATE ON `hobbys_car_audio`.`proveedor` TO `Almacenista`@`%`;
GRANT SELECT, INSERT, UPDATE ON `hobbys_car_audio`.`receta` TO `Almacenista`@`%`;
GRANT SELECT, INSERT, UPDATE, DELETE ON `hobbys_car_audio`.`recetadetalle` TO `Almacenista`@`%`;
GRANT SELECT ON `hobbys_car_audio`.`rol` TO `Almacenista`@`%`;
GRANT SELECT, INSERT, UPDATE ON `hobbys_car_audio`.`sesionusuario` TO `Almacenista`@`%`;
GRANT SELECT ON `hobbys_car_audio`.`solicitudproduccion` TO `Almacenista`@`%`;
GRANT SELECT, INSERT, UPDATE, DELETE ON `hobbys_car_audio`.`tmp_compra_detalle` TO `Almacenista`@`%`;
GRANT SELECT ON `hobbys_car_audio`.`unidadmedida` TO `Almacenista`@`%`;
GRANT SELECT, UPDATE ON `hobbys_car_audio`.`usuario` TO `Almacenista`@`%`;
GRANT EXECUTE ON PROCEDURE `hobbys_car_audio`.`sp_dashboard_alertasstockmateriaprima` TO `Almacenista`@`%`;
GRANT EXECUTE ON PROCEDURE `hobbys_car_audio`.`sp_dashboard_alertasstockproducto` TO `Almacenista`@`%`;
GRANT EXECUTE ON PROCEDURE `hobbys_car_audio`.`sp_dashboard_defectos` TO `Almacenista`@`%`;
GRANT EXECUTE ON PROCEDURE `hobbys_car_audio`.`sp_dashboard_graficaanio` TO `Almacenista`@`%`;
GRANT EXECUTE ON PROCEDURE `hobbys_car_audio`.`sp_dashboard_graficames` TO `Almacenista`@`%`;
GRANT EXECUTE ON PROCEDURE `hobbys_car_audio`.`sp_dashboard_graficasemana` TO `Almacenista`@`%`;
GRANT EXECUTE ON PROCEDURE `hobbys_car_audio`.`sp_dashboard_kpishoy` TO `Almacenista`@`%`;
GRANT EXECUTE ON PROCEDURE `hobbys_car_audio`.`sp_dashboard_topgananciasemanaactual` TO `Almacenista`@`%`;
GRANT EXECUTE ON PROCEDURE `hobbys_car_audio`.`sp_dashboard_topgananciasemanaanterior` TO `Almacenista`@`%`;
GRANT EXECUTE ON PROCEDURE `hobbys_car_audio`.`sp_dashboard_topunidadessemanaactual` TO `Almacenista`@`%`;
GRANT EXECUTE ON PROCEDURE `hobbys_car_audio`.`sp_dashboard_topunidadessemanaanterior` TO `Almacenista`@`%`;
GRANT EXECUTE ON PROCEDURE `hobbys_car_audio`.`sp_finalizarcompradesdetmp` TO `Almacenista`@`%`;
GRANT EXECUTE ON PROCEDURE `hobbys_car_audio`.`sp_registrar_movimiento_mp` TO `Almacenista`@`%`;
GRANT EXECUTE ON PROCEDURE `hobbys_car_audio`.`sp_solicitudproduccion_crear` TO `Almacenista`@`%`;

CREATE ROLE IF NOT EXISTS `Produccion`@`%`;
GRANT USAGE ON *.* TO `Produccion`@`%`;
GRANT SELECT, UPDATE ON `hobbys_car_audio`.`alertasistema` TO `Produccion`@`%`;
GRANT SELECT ON `hobbys_car_audio`.`cliente` TO `Produccion`@`%`;
GRANT SELECT, UPDATE ON `hobbys_car_audio`.`persona` TO `Produccion`@`%`;
GRANT SELECT ON `hobbys_car_audio`.`produccion` TO `Produccion`@`%`;
GRANT SELECT ON `hobbys_car_audio`.`rol` TO `Produccion`@`%`;
GRANT SELECT, INSERT, UPDATE ON `hobbys_car_audio`.`sesionusuario` TO `Produccion`@`%`;
GRANT SELECT ON `hobbys_car_audio`.`solicitudproduccion` TO `Produccion`@`%`;
GRANT SELECT, UPDATE ON `hobbys_car_audio`.`usuario` TO `Produccion`@`%`;
GRANT EXECUTE ON PROCEDURE `hobbys_car_audio`.`sp_produccion_cancelar` TO `Produccion`@`%`;
GRANT EXECUTE ON PROCEDURE `hobbys_car_audio`.`sp_produccion_completadashoy` TO `Produccion`@`%`;
GRANT EXECUTE ON PROCEDURE `hobbys_car_audio`.`sp_produccion_finalizar` TO `Produccion`@`%`;
GRANT EXECUTE ON PROCEDURE `hobbys_car_audio`.`sp_produccion_iniciar` TO `Produccion`@`%`;
GRANT EXECUTE ON PROCEDURE `hobbys_car_audio`.`sp_produccion_kpishoy` TO `Produccion`@`%`;
GRANT EXECUTE ON PROCEDURE `hobbys_car_audio`.`sp_produccion_listardefectos` TO `Produccion`@`%`;
GRANT EXECUTE ON PROCEDURE `hobbys_car_audio`.`sp_produccion_listarporestado` TO `Produccion`@`%`;
GRANT EXECUTE ON PROCEDURE `hobbys_car_audio`.`sp_produccion_registrardefecto` TO `Produccion`@`%`;
GRANT EXECUTE ON PROCEDURE `hobbys_car_audio`.`sp_produccion_ver` TO `Produccion`@`%`;

CREATE ROLE IF NOT EXISTS `Consulta`@`%`;
GRANT USAGE ON *.* TO `Consulta`@`%`;
GRANT SELECT ON `hobbys_car_audio`.`cliente` TO `Consulta`@`%`;
GRANT SELECT ON `hobbys_car_audio`.`corteventadiario` TO `Consulta`@`%`;
GRANT SELECT ON `hobbys_car_audio`.`materiaprima` TO `Consulta`@`%`;
GRANT SELECT, UPDATE ON `hobbys_car_audio`.`persona` TO `Consulta`@`%`;
GRANT SELECT ON `hobbys_car_audio`.`productoterminado` TO `Consulta`@`%`;
GRANT SELECT ON `hobbys_car_audio`.`receta` TO `Consulta`@`%`;
GRANT SELECT ON `hobbys_car_audio`.`recetadetalle` TO `Consulta`@`%`;
GRANT SELECT ON `hobbys_car_audio`.`rol` TO `Consulta`@`%`;
GRANT SELECT, INSERT, UPDATE ON `hobbys_car_audio`.`sesionusuario` TO `Consulta`@`%`;
GRANT SELECT ON `hobbys_car_audio`.`unidadmedida` TO `Consulta`@`%`;
GRANT SELECT, UPDATE ON `hobbys_car_audio`.`usuario` TO `Consulta`@`%`;
GRANT SELECT ON `hobbys_car_audio`.`venta` TO `Consulta`@`%`;
GRANT SELECT ON `hobbys_car_audio`.`ventadetalle` TO `Consulta`@`%`;
GRANT EXECUTE ON PROCEDURE `hobbys_car_audio`.`sp_dashboard_alertasstockmateriaprima` TO `Consulta`@`%`;
GRANT EXECUTE ON PROCEDURE `hobbys_car_audio`.`sp_dashboard_alertasstockproducto` TO `Consulta`@`%`;
GRANT EXECUTE ON PROCEDURE `hobbys_car_audio`.`sp_dashboard_defectos` TO `Consulta`@`%`;
GRANT EXECUTE ON PROCEDURE `hobbys_car_audio`.`sp_dashboard_graficaanio` TO `Consulta`@`%`;
GRANT EXECUTE ON PROCEDURE `hobbys_car_audio`.`sp_dashboard_graficames` TO `Consulta`@`%`;
GRANT EXECUTE ON PROCEDURE `hobbys_car_audio`.`sp_dashboard_graficasemana` TO `Consulta`@`%`;
GRANT EXECUTE ON PROCEDURE `hobbys_car_audio`.`sp_dashboard_kpishoy` TO `Consulta`@`%`;
GRANT EXECUTE ON PROCEDURE `hobbys_car_audio`.`sp_dashboard_topgananciasemanaactual` TO `Consulta`@`%`;
GRANT EXECUTE ON PROCEDURE `hobbys_car_audio`.`sp_dashboard_topgananciasemanaanterior` TO `Consulta`@`%`;
GRANT EXECUTE ON PROCEDURE `hobbys_car_audio`.`sp_dashboard_topunidadessemanaactual` TO `Consulta`@`%`;
GRANT EXECUTE ON PROCEDURE `hobbys_car_audio`.`sp_dashboard_topunidadessemanaanterior` TO `Consulta`@`%`;

CREATE ROLE IF NOT EXISTS `Cliente`@`%`;
GRANT USAGE ON *.* TO `Cliente`@`%`;
GRANT SELECT, UPDATE ON `hobbys_car_audio`.`cliente` TO `Cliente`@`%`;
GRANT SELECT, UPDATE ON `hobbys_car_audio`.`persona` TO `Cliente`@`%`;
GRANT SELECT ON `hobbys_car_audio`.`produccion` TO `Cliente`@`%`;
GRANT SELECT ON `hobbys_car_audio`.`productoterminado` TO `Cliente`@`%`;
GRANT SELECT ON `hobbys_car_audio`.`rol` TO `Cliente`@`%`;
GRANT SELECT, INSERT, UPDATE ON `hobbys_car_audio`.`sesionusuario` TO `Cliente`@`%`;
GRANT SELECT, INSERT ON `hobbys_car_audio`.`solicitudproduccion` TO `Cliente`@`%`;
GRANT SELECT, INSERT, UPDATE ON `hobbys_car_audio`.`tarjetacliente` TO `Cliente`@`%`;
GRANT SELECT, UPDATE ON `hobbys_car_audio`.`usuario` TO `Cliente`@`%`;
GRANT SELECT ON `hobbys_car_audio`.`venta` TO `Cliente`@`%`;
GRANT SELECT ON `hobbys_car_audio`.`ventadetalle` TO `Cliente`@`%`;
GRANT EXECUTE ON PROCEDURE `hobbys_car_audio`.`sp_clientes_registrar` TO `Cliente`@`%`;
GRANT EXECUTE ON PROCEDURE `hobbys_car_audio`.`sp_perfil_actualizarcliente` TO `Cliente`@`%`;
GRANT EXECUTE ON PROCEDURE `hobbys_car_audio`.`sp_ventas_registrar` TO `Cliente`@`%`;

FLUSH PRIVILEGES;
