import asyncio
import logging
import os
from datetime import datetime
from functools import partial
from time import sleep

import aiometer
import httpx
from pygtail import Pygtail

from topsoft.constants import API_BASE_URL, OFFSET_PATH
from topsoft.repository import (
    bulk_update_synced_acessos,
    get_not_synced_acessos,
    process_turnstile_event,
    update_student_records,
)
from topsoft.secrets import get_api_key
from topsoft.settings import get_bilhetes_path, get_cutoff, get_interval

logger = logging.getLogger(__name__)


def get_reader(filepath):
    return Pygtail(filepath, offset_file=OFFSET_PATH, paranoid=True)


def background_task(stop_event):
    def extract_ticket_records(filepath, cutoff=None, force_read=False):
        """
        Reads new lines from the bilhetes file since the last run (or since force_read),
        parses each record, and returns a list of dicts.

        :param filepath: Path to the log file
        :param cutoff: datetime; if provided, only lines with timestamp >= cutoff are kept
        :param force_read: if True, ignores previous offset and reads full file
        """

        logging.debug(f"Reading bilhetes file: {filepath} (force_read={force_read})")
        tickets = []

        # Initialize Pygtail reader
        reader = get_reader(filepath)

        # If forcing full re-read, delete the offset file
        if force_read:
            try:
                os.remove(OFFSET_PATH)
                reader = get_reader(filepath)
                logging.info("Offset file removed; full file will be re-read.")
            except FileNotFoundError:
                pass

        for n, raw_line in enumerate(reader):
            if stop_event.is_set():
                logger.info("Stopping extraction of bilhetes")
                return

            try:
                if n % 1000 == 0:
                    logger.debug(f"Processing line {n}")

                # Read and parse the line
                parts = raw_line.strip().split()

                if len(parts) < 5:
                    logging.warning(f"Skipping malformed line: {raw_line!r}")
                    continue
                # TODO: Bulk insert no banco de dados

                # Timestamp:
                try:
                    ts = datetime.strptime(f"{parts[1]} {parts[2]}", "%d/%m/%y %H:%M")
                except ValueError:
                    logging.warning(f"Invalid timestamp in line: {raw_line!r}")
                    continue

                # Check if the timestamp is before the cutoff:
                if cutoff and ts < cutoff:
                    continue

                # Bilhete:
                ticket = process_turnstile_event(
                    {
                        "marcacao": parts[0],
                        "date": parts[1],
                        "time": parts[2],
                        "cartao": parts[3],
                        "catraca": parts[4],
                    }
                )
                tickets.append(ticket)
            except IndexError as e:
                logging.warning(f"Error reading line")  # TODO: Melhorar mensagem
                logging.exception(e)
                continue

        logger.debug(f"Bilhetes read: {len(tickets)}")
        return tickets

    def sync_students():
        """
        Update the students in the database by fetching and syncing data from the API.
        """

        def fetch_students_from_api():
            """
            Fetch the list of students from the API.
            """

            # Header
            api_key = get_api_key()
            if not api_key:
                logger.error("API key not found")
                return None

            # TODO: PS: Cada instuição tem uma API Key diferente, logo, vamos ter que fazer sempre uma relação entre cartão -> matrícula -> instituição -> api_key

            headers = {"Authorization": api_key}

            try:
                with httpx.Client(base_url=API_BASE_URL, headers=headers) as client:
                    response = client.get("lista_alunos/")
                    response.raise_for_status()

                    if response.status_code != 200:
                        logger.error(
                            f"Failed to fetch students: {response.status_code}"
                        )
                        return None

                    return response.json()
            except httpx.RequestError as e:
                logger.error(f"Request error while fetching students: {e}")
            except Exception as e:
                logger.error(f"Unexpected error while fetching students: {e}")

            return None

        def parse_students_data(data):
            """
            Parse and sync the students' data into the database.
            """
            try:
                update_student_records(data)
                return True
            except Exception as e:
                logger.error(f"Failed to sync students: {e}")
                return False

        logger.info("Starting student data synchronization")

        students_data = fetch_students_from_api()
        if students_data is None:
            logger.error("Failed to fetch students from the API")
            return False

        if not parse_students_data(students_data):
            logger.error("Failed to sync students to the database")
            return False

        logger.info("Student data synchronization completed successfully")
        return True

    async def push_acessos_api(bilhetes):
        """
        Send data to ActivitySoft.
        """

        logger.debug(f"Sending data to ActivitySoft: {len(bilhetes)} bilhetes")

        # TODO: Necessário saber quais dados já foram enviados pra evitar duplicados no ActSoft ? Sim!

        # Header
        api_key = get_api_key()
        if not api_key:
            logger.error("API key not found")
            return False

        headers = {"Authorization": api_key}

        # Payload and Request
        async with httpx.AsyncClient(base_url=API_BASE_URL, headers=headers) as client:

            async def post_data(acesso):
                try:
                    acesso_dt = datetime.strptime(
                        f"{acesso['date']} {acesso['time']}",
                        "%d/%m/%y %H:%M",
                    )
                    cutoff = datetime.strptime(get_cutoff(), "%d/%m/%Y")

                    # Check if the timestamp is before the cutoff:
                    if acesso_dt < cutoff:
                        logger.debug(f"Skipping data older than cutoff: {acesso}")
                        return None, None
                except Exception as e:
                    logger.error(f"Error parsing date/time for cutoff: {e}")
                    return None, None

                try:
                    response = await client.post(
                        "marcar_frequencia_aluno/",
                        json={
                            "data_hora": f"{acesso['date']}T{acesso['time']}",
                            "tipo_entrada_saidade": (
                                "E" if acesso["marcacao"] == "010" else "S"
                            ),
                            "matricula": acesso.cartao_acesso.aluno.matricula,
                            "id_responsavel_acompanhante": None,
                            "comentario": None,
                        },
                    )
                    response.raise_for_status()  # catch HTTP errors

                    return acesso, response.status_code
                except Exception as e:
                    logger.error(f"Failed to send payload {acesso}")
                    logger.exception(e)

                    return None, None

            results = await aiometer.run_all(
                [partial(post_data, bilhete) for bilhete in bilhetes],
                max_at_once=500,  # TODO: Adjust based on your API/server capacity
                max_per_second=1,  # TODO: Optional: rate-limit
            )

        return results

    def wait_for_interval():
        """
        Wait for the specified interval.
        """

        intervalo = get_interval() * 60

        for i in range(intervalo):
            if stop_event.is_set():
                logger.info("Stopping background task")
                return
            logger.debug(f"Waiting for {intervalo - i} seconds")
            sleep(1)

    # Log the start of the task
    logger.info("Starting background task")

    # Variables
    cnt = 1

    # Main loop
    while not stop_event.is_set():
        logger.info(f"Running background task {cnt}")
        cnt += 1

        try:
            if bilhetes_path := get_bilhetes_path():
                # Sincronizar alunos com a API:
                if not sync_students():
                    logger.error("Failed to update students")
                    continue

                # Ler arquivo de "bilhetes" (acessos):
                extract_ticket_records(bilhetes_path)

                # Retornar bilhetes não sincronizados:
                acessos = get_not_synced_acessos()

                # Envia dados, não sincronizados, para ActivitySoft:
                # results = push_acessos_api(acessos)

                # Atualizar status dos bilhetes:
                # bulk_update_synced_acessos(results)

                # TODO: Atualizar interface gráfica
        except Exception as e:
            logger.warning(f"Error na execução da tarefa")
            logger.exception(e)
        finally:
            wait_for_interval()
