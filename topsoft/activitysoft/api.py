import logging
from datetime import datetime
from functools import partial

import aiometer
import httpx

from topsoft.constants import API_BASE_URL, MAX_AT_ONCE, MAX_PER_SECOND
from topsoft.secrets import get_api_key
from topsoft.settings import get_cutoff

logger = logging.getLogger(__name__)


def fetch_students():
    api_key = get_api_key()
    if not api_key:
        logger.error("API key not found")
        return None

    # Set up the headers for the API request:
    headers = {"Authorization": api_key}

    # Attempt to fetch the list of students from the API:
    try:
        with httpx.Client(base_url=API_BASE_URL, headers=headers) as client:
            response = client.get("lista_alunos/")
            response.raise_for_status()
            if response.status_code != 200:
                logger.error(f"Failed to fetch students: {response.status_code}")
                return None
            return response.json()
    except httpx.RequestError as e:
        logger.error(f"Request error while fetching students: {e}")
    except Exception as e:
        logger.error(f"Unexpected error while fetching students: {e}")

    # If the request fails, return None:
    return None


async def post_acessos(bilhetes):
    """
    Send data to ActivitySoft concurrently using the API.
    This function takes a list of access records (bilhetes),
    checks if they are valid and not already synced, and posts them to the API.
    It returns a list of results containing the access records and their corresponding status codes.
    """

    # API Key:
    api_key = get_api_key()
    if not api_key:
        logger.error("API key not found")
        return False

    # Concurrently post data to the API:
    async with httpx.AsyncClient(
        base_url=API_BASE_URL, headers={"Authorization": api_key}
    ) as client:
        results = await aiometer.run_all(
            [partial(post_acesso, client, bilhete) for bilhete in bilhetes],
            max_at_once=MAX_AT_ONCE,
            max_per_second=MAX_PER_SECOND,
        )
        # TODO: Update database for each result

    # Return the results
    return results


async def post_acesso(client, acesso):
    """
    Function to post a single access record to the API.
    This function checks if the access record is already synced and if it is valid
    before attempting to post it to the API.
    """

    # If already synced, skip posting:
    if acesso.synced is True:
        return None, None

    # If access record is not valid, skip posting:
    acesso_dt = datetime.combine(acesso.date, acesso.time)
    cutoff = datetime.strptime(get_cutoff(), "%d/%m/%Y")

    if acesso_dt < cutoff:
        return None, None

    # Ignore acesso where there is not aluno associated with the card:
    if not acesso.cartao_acesso or not acesso.cartao_acesso.aluno:
        # logger.warning(f"Access record {acesso.id} has no associated student.")
        return None, None

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

        # Return the access record and its status code:
        return acesso, response.status_code
    except Exception as e:
        logger.error(f"Failed to send payload {acesso}")
        logger.exception(e)
        return None, None
