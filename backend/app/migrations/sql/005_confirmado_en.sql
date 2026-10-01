-- 005: día en que se confirmó «va a renovar». Ese día es el INICIO del nuevo contrato (aunque el pago se complete después,
-- dentro de la prórroga).
ALTER TABLE paquetes_cliente ADD COLUMN confirmado_en DATE;
