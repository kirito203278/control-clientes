-- 006: plan de renovación. Al confirmar «va a renovar» se elige si sigue con el mismo paquete o cambia (paquete, tipo y costo);
-- se aplica cuando la renovación se concreta (al pagar). NULL = mismo paquete, tipo y costo.
ALTER TABLE paquetes_cliente
    ADD COLUMN renovara_paquete_id INTEGER REFERENCES catalogo_paquetes(id),
    ADD COLUMN renovara_tipo_id    INTEGER REFERENCES catalogo_tipos(id),
    ADD COLUMN renovara_costo      NUMERIC(10,2) CHECK (renovara_costo IS NULL OR renovara_costo >= 0);
