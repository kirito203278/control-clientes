from sqlalchemy.orm import Session

from app.models import Bitacora, Usuario


def registrar(db: Session, usuario: Usuario | None, accion: str, detalle: dict | None = None) -> None:
    """Deja rastro de una acción sensible. No hace commit: va en la transacción del llamador."""
    db.add(Bitacora(usuario_id=usuario.id if usuario else None, accion=accion, detalle=detalle))
