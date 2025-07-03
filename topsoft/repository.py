import logging
from datetime import datetime

from sqlalchemy.orm import joinedload
from sqlmodel import Session, select

from topsoft.database import engine
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
                    if hasattr(Aluno, key):
                        setattr(aluno, key, val)
            else:
                valid_data = {
                    key: val for key, val in data.items() if hasattr(Aluno, key)
                }
                aluno = Aluno(**valid_data)
                session.add(aluno)

        session.commit()

    logger.info(f"Synced {len(alunos_json)} alunos.")


def process_turnstile_event(event: dict) -> Acesso:
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
            date_obj = datetime.strptime(event["date"], "%d/%m/%y").date()
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

        # If access record already exists, return it
        if acesso:
            return acesso

        # If access record does not exist, create a new one and return it
        acesso = Acesso(
            marcacao=event["marcacao"],
            date=date_obj,
            time=time_obj,
            catraca=event["catraca"],
            cartao_acesso_id=card.id,
            synced=False,
        )
        session.add(acesso)
        session.commit()
        return acesso


def bulk_update_synced_acessos(acessos):
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
        for acesso in acessos:
            acesso.synced = True
            session.add(acesso)

        session.commit()
        logger.info(f"Updated {len(acessos)} access records as synced.")


def get_not_synced_acessos():
    """
    Get all access records that are not synced, with related cartao_acesso and aluno eagerly loaded.
    """

    with Session(engine) as session:
        acessos = session.exec(
            select(Acesso)
            .where(Acesso.synced == False)
            .options(joinedload(Acesso.cartao_acesso).joinedload(CartaoAcesso.aluno))
        ).all()

        return acessos


def get_acessos(offset=None, limit=None):
    """
    Get access records with pagination, ordered from most recent to oldest,
    including foreign key fields.
    """

    with Session(engine) as session:
        query = (
            select(Acesso)
            .options(joinedload(Acesso.cartao_acesso))
            .order_by(Acesso.date.desc(), Acesso.time.desc())
        )

        # Apply pagination if offset and limit are provided
        if offset is not None:
            query = query.offset(offset)
        if limit is not None:
            query = query.limit(limit)

        acessos = session.exec(query).all()
        return acessos


def get_alunos(sort_by=None, offset=None, limit=None):
    """
    Get all students from the database.
    """
    with Session(engine) as session:
        alunos = session.exec(select(Aluno)).all()
        if sort_by:
            alunos = sorted(alunos, key=lambda x: getattr(x, sort_by))
        return alunos


def get_cartoes_acesso():
    """
    Get all access cards from the database.
    """
    with Session(engine) as session:
        cartoes = session.exec(
            select(CartaoAcesso).options(joinedload(CartaoAcesso.aluno))
        ).all()
        return cartoes


def bind_cartao_acesso_to_aluno(cartao_acesso_id: int, aluno_id: int):
    """
    Bind a card to a student.
    """
    with Session(engine) as session:
        cartao_acesso = session.get(CartaoAcesso, cartao_acesso_id)
        aluno = session.get(Aluno, aluno_id)

        if not cartao_acesso or not aluno:
            logger.error("Card or student not found.")
            return False

        cartao_acesso.aluno_id = aluno.id
        session.add(cartao_acesso)
        session.commit()
        return True


def bind_matricula_to_cartao_acesso(cartao_numeracao: int, aluno_matricula: str):
    """
    Bind a card to a student by their registration number.
    """
    # with Session(engine) as session:
    #     cartao_acesso = session.get(CartaoAcesso, cartao_acesso_id)
    #     aluno = session.exec(
    #         select(Aluno).where(Aluno.matricula == matricula)
    #     ).first()

    #     if not cartao_acesso or not aluno:
    #         logger.error("Card or student not found.")
    #         return False

    #     cartao_acesso.aluno_id = aluno.id
    #     session.add(cartao_acesso)
    #     session.commit()
    #     return True

    with Session(engine) as session:
        cartao = session.exec(
            select(CartaoAcesso).where(CartaoAcesso.numeracao == cartao_numeracao)
        ).first()

        aluno = session.exec(
            select(Aluno).where(Aluno.matricula == aluno_matricula)
        ).first()

        if cartao and aluno:
            cartao.aluno_id = aluno.id
            session.add(cartao)
            session.commit()
            return True

    return False


def update_acesso(acesso_id: int, **kwargs):
    """
    Update an access record by its ID.
    """

    with Session(engine) as session:
        acesso = session.get(Acesso, acesso_id)
        if not acesso:
            logger.error(f"Acesso with ID {acesso_id} not found.")
            return False

        for key, value in kwargs.items():
            if hasattr(acesso, key):
                setattr(acesso, key, value)

        session.add(acesso)
        session.commit()
        return True


def get_or_create_cartao_acesso(numeracao: str) -> CartaoAcesso:
    """
    Get or create a CartaoAcesso by its numeracao.
    """

    # TODO: Numeração com 0s à esquerda sempre!
    # Ensure it is 16 characters long # TODO: Poderia ser 5...
    numeracao = numeracao.zfill(16)

    with Session(engine) as session:
        cartao = session.exec(
            select(CartaoAcesso).where(CartaoAcesso.numeracao == numeracao)
        ).first()

        if not cartao:
            cartao = CartaoAcesso(numeracao=numeracao)
            session.add(cartao)
            session.commit()
            session.refresh(cartao)  # Ensure we have the latest state

        return cartao


def get_aluno_by_matricula(matricula: str) -> Aluno:
    """
    Get an Aluno by its matricula.
    """
    with Session(engine) as session:
        try:
            aluno = session.exec(
                select(Aluno).where(Aluno.matricula == matricula)
            ).first()
            return aluno
        except Exception as e:
            logger.error(f"Error fetching Aluno by matricula {matricula}: {e}")
            return None
