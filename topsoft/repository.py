import logging
from datetime import datetime
from typing import Dict, List

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


def bulk_process_turnstile_events(events: List[dict]) -> List[Acesso]:
    """
    Process multiple turnstile events efficiently using bulk operations.

    Parameters:
    - events: List of event dictionaries with keys: marcacao, date, time, cartao, catraca

    Returns:
    - List[Acesso]: List of processed access records
    """
    if not events:
        return []

    processed_acessos = []

    with Session(engine) as session:
        # Step 1: Collect all unique card numbers and ensure they exist
        unique_card_numbers = list(set(event["cartao"] for event in events))

        # Get existing cards
        existing_cards = session.exec(
            select(CartaoAcesso).where(CartaoAcesso.numeracao.in_(unique_card_numbers))
        ).all()

        existing_card_numbers = {card.numeracao for card in existing_cards}

        # Create missing cards in bulk
        missing_card_numbers = set(unique_card_numbers) - existing_card_numbers
        if missing_card_numbers:
            new_cards = [CartaoAcesso(numeracao=num) for num in missing_card_numbers]
            session.add_all(new_cards)
            session.commit()

            # Refresh to get all cards with IDs
            existing_cards = session.exec(
                select(CartaoAcesso).where(
                    CartaoAcesso.numeracao.in_(unique_card_numbers)
                )
            ).all()

        # Create a mapping of card number to card ID
        card_number_to_id = {card.numeracao: card.id for card in existing_cards}

        # Step 2: Process events and create access records
        access_records_to_create = []
        access_signatures = set()  # To track duplicates within the batch

        # Get existing access records to avoid duplicates
        existing_access_conditions = []
        for event in events:
            try:
                date_obj = datetime.strptime(event["date"], "%d/%m/%y").date()
                time_obj = datetime.strptime(event["time"], "%H:%M").time()
                cartao_id = card_number_to_id.get(event["cartao"])

                if cartao_id:
                    signature = (cartao_id, date_obj, time_obj)
                    existing_access_conditions.append(signature)
            except ValueError:
                logger.warning(f"Invalid date/time format in event: {event}")
                continue

        # Query existing access records in bulk
        existing_access_records = set()
        if existing_access_conditions:
            # Build a more efficient query to check for existing records
            # We'll check each unique combination
            for cartao_id, date_obj, time_obj in set(existing_access_conditions):
                existing = session.exec(
                    select(Acesso).where(
                        Acesso.cartao_acesso_id == cartao_id,
                        Acesso.date == date_obj,
                        Acesso.time == time_obj,
                    )
                ).first()
                if existing:
                    existing_access_records.add((cartao_id, date_obj, time_obj))

        # Step 3: Create new access records
        for event in events:
            try:
                date_obj = datetime.strptime(event["date"], "%d/%m/%y").date()
                time_obj = datetime.strptime(event["time"], "%H:%M").time()
                cartao_id = card_number_to_id.get(event["cartao"])

                if not cartao_id:
                    logger.warning(f"Card not found for event: {event}")
                    continue

                # Create unique signature for this access
                signature = (cartao_id, date_obj, time_obj)

                # Skip if already exists in database or in current batch
                if (
                    signature in existing_access_records
                    or signature in access_signatures
                ):
                    continue

                access_signatures.add(signature)

                acesso = Acesso(
                    marcacao=event["marcacao"],
                    date=date_obj,
                    time=time_obj,
                    catraca=event["catraca"],
                    cartao_acesso_id=cartao_id,
                    synced=False,
                )
                access_records_to_create.append(acesso)

            except ValueError as e:
                logger.warning(
                    f"Invalid date/time format in event: {event}, error: {e}"
                )
                continue
            except Exception as e:
                logger.warning(f"Error processing event: {event}, error: {e}")
                continue

        # Step 4: Bulk insert new access records
        if access_records_to_create:
            session.add_all(access_records_to_create)
            session.commit()

            # Refresh all records to get their IDs
            for acesso in access_records_to_create:
                session.refresh(acesso)
                processed_acessos.append(acesso)

            logger.info(
                f"Bulk processed {len(processed_acessos)} new access records from {len(events)} events"
            )
        else:
            logger.info(
                f"No new access records to create from {len(events)} events (all duplicates)"
            )

    return processed_acessos


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


def bulk_update_acessos(acessos: List[Acesso]) -> bool:
    """
    Bulk update access records in the database.

    Parameters:
    - acessos: List of Acesso objects to be updated.

    Returns:
    - bool: True if the update was successful, False otherwise.
    """
    if not acessos:
        logger.warning("No access records to update.")
        return False

    with Session(engine) as session:
        try:
            # TODO: add_all para "update" ?
            session.add_all(acessos)
            session.commit()
            logger.info(f"Updated {len(acessos)} access records successfully.")
            return True
        except Exception as e:
            logger.error(f"Failed to bulk update access records: {e}")
            session.rollback()
            return False


def bulk_update_synced_status_acessos(acessos: List[Acesso], status: bool) -> bool:
    """
    Bulk update the synced status of access records in the database.

    Parameters:
    - acessos: List of Acesso objects to be updated.
    - status: Boolean indicating the new synced status.

    Returns:
    - bool: True if the update was successful, False otherwise.
    """

    if not acessos:
        logger.warning("No access records to update.")
        return False

    with Session(engine) as session:
        try:
            for acesso in acessos:
                acesso.synced = status
                session.add(acesso)
            session.commit()
            logger.info(f"Updated {len(acessos)} access records to synced={status}.")
            return True
        except Exception as e:
            logger.error(f"Failed to bulk update access records: {e}")
            session.rollback()
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


def get_or_create_aluno(nome: str, matricula: str = None, **kwargs) -> Aluno:
    """
    Get or create an Aluno by its name and optional matricula.
    """

    # Drop unknown kwargs
    valid_kwargs = {k: v for k, v in kwargs.items() if hasattr(Aluno, k)}

    with Session(engine) as session:
        aluno = session.exec(select(Aluno).where(Aluno.nome == nome)).first()

        if not aluno:
            aluno = Aluno(nome=nome, matricula=matricula, **valid_kwargs)
            session.add(aluno)
            session.commit()
            session.refresh(aluno)  # Ensure we have the latest state

        return aluno


# ===== NEW MODEL INTERFACE FUNCTIONS =====
# These functions use the updated models that handle sessions internally


def get_aluno_by_name_v2(nome: str) -> Aluno:
    """Get student by name using new model interface"""
    nome = nome.strip()
    try:
        return Aluno.filter_by(nome=nome)[0] if Aluno.filter_by(nome=nome) else None
    except Exception as e:
        logger.error(f"Error fetching Aluno by name {nome}: {e}")
        return None


def get_alunos_v2(sort_by=None, offset=None, limit=None):
    """Get all students using new model interface"""
    try:
        alunos = Aluno.get_all()

        # Apply sorting if specified
        if sort_by and hasattr(Aluno, sort_by):
            alunos = sorted(alunos, key=lambda x: getattr(x, sort_by) or "")

        # Apply pagination if specified
        if offset is not None and limit is not None:
            alunos = alunos[offset : offset + limit]
        elif limit is not None:
            alunos = alunos[:limit]

        return alunos
    except Exception as e:
        logger.error(f"Error fetching alunos: {e}")
        return []


def get_cartoes_acesso_v2():
    """Get all access cards using new model interface"""
    try:
        return CartaoAcesso.get_all()
    except Exception as e:
        logger.error(f"Error fetching cartoes de acesso: {e}")
        return []


def get_acessos_v2(offset=None, limit=None):
    """Get all access records using new model interface"""
    try:
        acessos = Acesso.get_all()

        # Apply pagination if specified
        if offset is not None and limit is not None:
            acessos = acessos[offset : offset + limit]
        elif limit is not None:
            acessos = acessos[:limit]

        return acessos
    except Exception as e:
        logger.error(f"Error fetching acessos: {e}")
        return []


def bind_matricula_to_cartao_acesso_v2(
    cartao_numeracao: str, aluno_matricula: str
) -> bool:
    """Bind a student to an access card using new model interface"""
    try:
        # Find the card
        cartao = CartaoAcesso.find_by_numeracao(cartao_numeracao)
        if not cartao:
            logger.error(f"Cartão {cartao_numeracao} not found")
            return False

        # Find the student
        aluno = Aluno.find_by_matricula(aluno_matricula)
        if not aluno:
            logger.error(f"Aluno with matricula {aluno_matricula} not found")
            return False

        # Bind them
        cartao.assign_to_aluno(aluno.id)
        logger.info(
            f"Successfully bound cartão {cartao_numeracao} to aluno {aluno.nome}"
        )
        return True

    except Exception as e:
        logger.error(f"Error binding cartão to aluno: {e}")
        return False


def bulk_update_acessos_v2(acesso_ids: List[int]) -> bool:
    """Mark multiple access records as synced using new model interface"""
    try:
        Acesso.bulk_mark_synced(acesso_ids)
        return True
    except Exception as e:
        logger.error(f"Error bulk updating acessos: {e}")
        return False
