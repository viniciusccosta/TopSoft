import logging
from datetime import datetime
from typing import Dict, List

from sqlalchemy.orm import joinedload
from sqlmodel import Session, select

from topsoft.database import engine
from topsoft.models import Acesso, Aluno, CartaoAcesso

logger = logging.getLogger(__name__)


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
