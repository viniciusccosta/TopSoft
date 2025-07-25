import logging
from datetime import datetime
from typing import List

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
    # Convert date and time strings to datetime objects
    try:
        date_obj = datetime.strptime(event["date"], "%d/%m/%y").date()
        time_obj = datetime.strptime(event["time"], "%H:%M").time()
    except ValueError as e:
        logger.error(f"Invalid date/time format: {e}")
        return None

    # Get or create the card using model method
    card = CartaoAcesso.get_or_create_by_numeracao(event["cartao"])

    # Check if access record already exists
    acesso = Acesso.get_existing_access(card.id, date_obj, time_obj)
    if acesso:
        return acesso

    # Create new access record using model method
    acesso = Acesso.create_access_record(
        marcacao=event["marcacao"],
        date_obj=date_obj,
        time_obj=time_obj,
        catraca=event["catraca"],
        cartao_id=card.id,
    )
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

    # Step 1: Collect all unique card numbers and ensure they exist
    unique_card_numbers = list(set(event["cartao"] for event in events))

    # Create missing cards using model method
    CartaoAcesso.bulk_create_missing(unique_card_numbers)

    # Get all cards (existing + newly created) using model method
    all_cards = CartaoAcesso.filter_by()  # Get all cards, we'll filter by numeracao
    card_number_to_id = {}
    for card in all_cards:
        if card.numeracao in unique_card_numbers:
            card_number_to_id[card.numeracao] = card.id

    # Step 2: Process events and prepare access records
    access_records_to_create = []
    access_signatures = set()  # To track duplicates within the batch

    # Check existing access records to avoid duplicates
    existing_access_checks = set()
    for event in events:
        try:
            date_obj = datetime.strptime(event["date"], "%d/%m/%y").date()
            time_obj = datetime.strptime(event["time"], "%H:%M").time()
            cartao_id = card_number_to_id.get(event["cartao"])

            if cartao_id:
                # Check if this access already exists
                existing = Acesso.get_existing_access(cartao_id, date_obj, time_obj)
                if existing:
                    existing_access_checks.add((cartao_id, date_obj, time_obj))
        except ValueError:
            logger.warning(f"Invalid date/time format in event: {event}")
            continue

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
            if signature in existing_access_checks or signature in access_signatures:
                continue

            access_signatures.add(signature)

            access_records_to_create.append(
                {
                    "marcacao": event["marcacao"],
                    "date": date_obj,
                    "time": time_obj,
                    "catraca": event["catraca"],
                    "cartao_id": cartao_id,
                }
            )

        except ValueError as e:
            logger.warning(f"Invalid date/time format in event: {event}, error: {e}")
            continue
        except Exception as e:
            logger.warning(f"Error processing event: {event}, error: {e}")
            continue

    # Step 4: Bulk create access records using model method
    if access_records_to_create:
        processed_acessos = Acesso.bulk_create_access_records(access_records_to_create)
        logger.info(
            f"Bulk processed {len(processed_acessos)} new access records from {len(events)} events"
        )
        return processed_acessos
    else:
        logger.info(
            f"No new access records to create from {len(events)} events (all duplicates)"
        )
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
