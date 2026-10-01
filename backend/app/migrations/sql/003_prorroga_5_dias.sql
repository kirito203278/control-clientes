-- 003: la prórroga dura hasta 5 días naturales desde que se activa (antes 15).
-- NOT VALID: la regla rige para toda fila nueva o modificada, pero no rechaza prórrogas viejas ya guardadas con la regla anterior
-- (así la migración no falla en una base con datos).
DO $$
DECLARE c record;
BEGIN
    FOR c IN SELECT conname FROM pg_constraint
             WHERE conrelid = 'paquetes_cliente'::regclass AND contype = 'c'
               AND pg_get_constraintdef(oid) LIKE '%prorroga_registrada_en + 15%'
    LOOP
        EXECUTE format('ALTER TABLE paquetes_cliente DROP CONSTRAINT %I', c.conname);
    END LOOP;
END $$;

ALTER TABLE paquetes_cliente ADD CONSTRAINT prorroga_max_5_dias CHECK (
    prorroga_hasta IS NULL OR
    (prorroga_hasta >= prorroga_registrada_en AND prorroga_hasta <= prorroga_registrada_en + 5)) NOT VALID;
