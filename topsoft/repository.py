import logging
from datetime import datetime
from typing import List

from sqlmodel import Session, select

from topsoft.db import engine
from topsoft.models import Acesso, Aluno, CartaoAcesso

logger = logging.getLogger(__name__)


def update_student_records(alunos_json):
    with Session(engine) as session:
        for data in alunos_json:
            # convert date string to datetime if needed
            if data.get("data_nascimento"):
                try:
                    data["data_nascimento"] = datetime.fromisoformat(
                        data["data_nascimento"]
                    )
                except ValueError:
                    pass  # leave as-is or set None

            # Build or update the Aluno instance
            aluno = session.get(Aluno, data["id"])
            if aluno:
                for key, val in data.items():
                    setattr(aluno, key, val)
            else:
                aluno = Aluno(**data)
                session.add(aluno)

        session.commit()

    logger.info(f"Synced {len(alunos_json)} alunos.")


def process_turnstile_event(event: dict):
    """
    event = {
        "marcacao": "010",
        "date": "15/10/2023",
        "time": "14:05",
        "cartao": "1234567890123456",
        "catraca": "03"
    }
    """

    with Session(engine) as session:
        # Convert date and time strings to datetime objects
        try:
            date_obj = datetime.strptime(event["date"], "%d/%m/%Y").date()
            time_obj = datetime.strptime(event["time"], "%H:%M").time()
        except ValueError as e:
            logger.error(f"Invalid date/time format: {e}")
            return None

        # Check if the card exists in the database
        card = session.exec(
            select(CartaoAcesso).where(CartaoAcesso.numeracao == event["cartao"])
        ).first()

        # If the card doesn't exist, create a new one
        if not card:
            card = CartaoAcesso(numeracao=event["cartao"])
            session.add(card)
            session.commit()

            # TODO: Necessário session.exec aqui para garantir que o ID seja atualizado ?
            card = session.exec(
                select(CartaoAcesso).where(CartaoAcesso.numeracao == event["cartao"])
            ).first()

        # Create a new access record (only if it doesn't exist):
        acesso = session.exec(
            select(Acesso).where(
                Acesso.cartao_acesso_id == card.id,
                Acesso.date == date_obj,
                Acesso.time == time_obj,
            )
        ).first()

        if acesso:
            logger.info(f"Access record already exists: {acesso}")
            return acesso

        acesso = Acesso(
            marcacao=event["marcacao"],
            date=date_obj,
            time=time_obj,
            cartao=event["cartao"],
            catraca=event["catraca"],
        )
        session.add(acesso)
        session.commit()

        # Return the created access record
        return acesso


def bulk_update_synced_acessos(results):
    """
    Bulk update the access records in the database.

    results = [
        (status_code, Acesso),
        ...
    ]

    status_code: int
        200: Success
        400: Bad Request
        401: Unauthorized
        403: Forbidden
        404: Not Found
        500: Internal Server Error
    """
    with Session(engine) as session:
        # TODO: Update "synced" field in bulk based on the results
        for status, acesso in results:
            if status == 200:
                acesso.synced = True
                session.add(acesso)
        session.commit()
        logger.info(f"Updated {len(results)} access records as synced.")


def get_not_synced_acessos():
    """
    Get all access records that are not synced.
    """

    with Session(engine) as session:
        acessos = session.exec(select(Acesso).where(Acesso.synced == False)).all()
        return acessos
