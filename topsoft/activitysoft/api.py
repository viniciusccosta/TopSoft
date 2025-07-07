import logging
from datetime import datetime
from functools import partial
from typing import Tuple

import aiometer
import httpx

from topsoft.constants import API_BASE_URL, MAX_AT_ONCE, MAX_PER_SECOND
from topsoft.models import Acesso
from topsoft.secrets import get_api_key
from topsoft.settings import get_cutoff

logger = logging.getLogger(__name__)


def get_header():
    """
    Get the header for the API request.
    This function retrieves the API key from the secrets and returns it in the required format.
    """

    # TODO: I don't think this is the appropriate place for this function.

    api_key = get_api_key()
    if not api_key:
        logger.error("API key not found")
        raise ValueError("API key is required for API requests")

    return {
        "Authorization": api_key,
    }


def get_students_from_api():
    # Attempt to fetch the list of students from the API:
    try:
        with httpx.Client(base_url=API_BASE_URL, headers=get_header()) as client:
            response = client.get("lista_alunos/")

            # Raise an error if the request was not successful:
            response.raise_for_status()

            # If the request was successful, return the JSON response:
            return response.json()
    except httpx.RequestError as e:
        logger.error(f"Request error while fetching students: {e}")
        raise Exception("Failed to fetch students from the API") from e

    # If the request fails, return None:
    return None


async def post_acesso(client, acesso) -> Tuple[Acesso, bool] | Tuple[None, None]:
    """
    Function to post a single access record to the API.
    This function checks if the access record is already synced and if it is valid before attempting to post it to the API.
    """

    # If already synced, skip posting:
    if acesso.synced is True:
        return acesso, False

    # If access record is not valid, skip posting:
    acesso_dt = datetime.combine(acesso.date, acesso.time)
    cutoff = datetime.strptime(get_cutoff(), "%d/%m/%Y")

    if acesso_dt < cutoff:
        return acesso, False

    # Ignore acesso where there is not aluno associated with the card:
    if not acesso.cartao_acesso or not acesso.cartao_acesso.aluno:
        logger.warning(f"Access record {acesso} has no associated cartao.")
        # TODO: Print every single error is making the logs too verbose and too slow.
        return acesso, False

    # API Request to post data:
    try:
        # Post the access record to the API:
        response = await client.post(
            "marcar_frequencia_aluno/",
            json={
                "data_hora": f"{acesso_dt.strftime('%Y-%m-%dT%H:%M:%S')}",
                "tipo_entrada_saida": ("E" if acesso.marcacao == "010" else "S"),
                "matricula": acesso.cartao_acesso.aluno.matricula,
                "id_responsavel_acompanhante": None,
                "comentario": None,
            },
        )

        # Raise an error if the request was not successful:
        response.raise_for_status()

        # Return acesso if successful:
        if response.status_code == 200:
            # Log the successful post:
            logger.debug(f"Access record {acesso.id} posted successfully.")

            # Return the access record and success status:
            return acesso, True
    except Exception as e:
        logger.error(f"Failed to send payload {acesso}")
        logger.exception(e)

    return acesso, False


async def post_accessos_concurrently(acessos, stop_event=None):
    """
    Send data to ActivitySoft concurrently using the API.
    This function takes a list of access records (bilhetes),
    checks if they are valid and not already synced, and posts them to the API.
    It returns a list of results containing the access records and their corresponding status codes.

    Parameters:
    - bilhetes (List[Acesso]): A list of access records to be posted.
    - stop_event (threading.Event, optional): An event to signal when to stop processing.

    Returns:
    - Async generator yielding tuples of (Acesso, bool) where bool indicates success.
    """

    # TODO: Use stop_event somehow...

    total = len(acessos)
    logger.info(f"Starting to post {total} access records")

    async with httpx.AsyncClient(base_url=API_BASE_URL, headers=get_header()) as client:
        try:
            # Use aiometer to post access records concurrently:
            results = await aiometer.run_all(
                [partial(post_acesso, client, acesso) for acesso in acessos],
                max_at_once=MAX_AT_ONCE,
                max_per_second=MAX_PER_SECOND,
            )

            return results
        except Exception as e:
            logger.error(f"Error in aiometer.run_all: {e}")
            logger.exception(e)
            raise

    # Log final summary
    logger.info(f"Completed posting {total} records")
