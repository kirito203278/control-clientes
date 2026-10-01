-- 004: gracia = días en que, tras confirmar «va a renovar» dentro de la ventana de decisión, el paquete queda habilitado
-- aunque aún no esté pagado. Al terminar vuelve la ventana (prórroga o no renovó).
ALTER TABLE paquetes_cliente ADD COLUMN gracia_hasta DATE;
