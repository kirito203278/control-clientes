import pytest
from sqlalchemy import func, select, text

from app.models import ArchivoNoRenovado, Cliente, PaqueteCliente, Usuario
from app.security.crypto import decrypt_value, encrypt_value
from app.security.passwords import generate_secure_password, hash_password, verify_password
from app.dates import hoy
from app.seed import sembrar


def test_cifrado_aes_gcm_ida_y_vuelta_y_nonce_aleatorio():
    a, b = encrypt_value("secreto"), encrypt_value("secreto")
    assert a != b and "secreto" not in a
    assert decrypt_value(a) == decrypt_value(b) == "secreto"


def test_cifrado_detecta_manipulacion():
    token = encrypt_value("secreto")
    roto = token[:-4] + ("AAAA" if token[-4:] != "AAAA" else "BBBB")
    with pytest.raises(Exception):
        decrypt_value(roto)


def test_contrasena_generada_18_caracteres_y_bcrypt():
    pwd = generate_secure_password()
    assert len(pwd) == 18
    assert any(c.islower() for c in pwd) and any(c.isupper() for c in pwd) and any(c.isdigit() for c in pwd)
    assert verify_password(pwd, hash_password(pwd)) and not verify_password(pwd + "x", hash_password(pwd))
    assert generate_secure_password() != pwd


def test_seed(db, tmp_path):
    cred = tmp_path / "cred.txt"
    resumen = sembrar(db, credenciales_path=cred)
    assert resumen == {"usuarios": 5, "clientes": 15}

    # contraseñas solo en el archivo; en BD solo hash bcrypt
    texto = cred.read_text()
    for u in db.scalars(select(Usuario)):
        assert u.password_hash.startswith("$2") and u.password_hash not in texto
        pwd = next(l.split("\t")[2] for l in texto.splitlines() if l.startswith(u.username + "\t"))
        assert verify_password(pwd, u.password_hash)

    # credenciales FB cifradas y recuperables
    c = db.scalars(select(Cliente).where(Cliente.nombre == "Panadería La Espiga")).one()
    assert "@" not in c.correo_fb_enc and decrypt_value(c.correo_fb_enc).endswith("@fb.ejemplo.test")

    # escenarios clave presentes
    assert db.scalar(select(func.count()).select_from(Cliente).where(Cliente.cm_id.is_(None))) == 1
    assert db.scalar(select(func.count()).select_from(ArchivoNoRenovado)) == 3
    multi = db.scalars(select(Cliente).where(Cliente.nombre == "Dra. Mariana Vélez")).one()
    assert len(multi.paquetes) == 2
    vencida = db.scalars(select(PaqueteCliente).where(PaqueteCliente.estado == "renovado")).one()
    assert vencida.restante == 1000 and vencida.prorroga_hasta < hoy()  # prórroga vencida con deuda


def test_seed_se_niega_si_ya_hay_usuarios(db, tmp_path):
    sembrar(db, credenciales_path=tmp_path / "c.txt")
    with pytest.raises(RuntimeError):
        sembrar(db, credenciales_path=tmp_path / "c.txt")
