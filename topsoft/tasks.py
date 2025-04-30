import asyncio
import logging
from functools import partial
from time import sleep

import aiometer
import httpx

from topsoft.constants import API_BASE_URL
from topsoft.repository import (
    bulk_update_synced_acessos,
    get_not_synced_acessos,
    process_turnstile_event,
    update_student_records,
)
from topsoft.secrets import get_api_key
from topsoft.settings import get_bilhetes_path, get_interval
from topsoft.utils import read_in_batches

logger = logging.getLogger(__name__)


def background_task(stop_event):
    def extract_ticket_records(filepath):
        """
        Read the bilhetes file and return a list of dictionaries with the data.
        """

        logging.debug(f"Reading bilhetes file: {filepath}")

        bilhetes = []

        # TODO: Forma mais inteligente de ler o arquivo sem precisar ler TODOS os dados toda vez
        # TODO: Como só registra hora:minuto podemos ler apenas a cada multiplo de 60 segundos (intervalo no frontend)

        for batch in read_in_batches(filepath):
            for tokens in batch:
                try:
                    # TODO: Bulk insert no banco de dados

                    bilhete = process_turnstile_event(
                        {
                            "marcacao": tokens[0],
                            "date": tokens[1],
                            "time": tokens[2],
                            "cartao": tokens[3],
                            "catraca": tokens[4],
                            # "sequencial": tokens[5],
                        }
                    )

                    bilhetes.append(bilhete)
                except IndexError as e:
                    logging.warning(f"Error reading line")  # TODO: Melhorar mensagem
                    logging.exception(e)
                    continue

        return bilhetes

    def sync_students():
        """
        Update the students in the database by fetching and syncing data from the API.
        """

        def fetch_students_from_api():
            """
            Fetch the list of students from the API.
            """

            try:
                with httpx.Client(base_url=API_BASE_URL) as client:
                    response = client.get("lista_alunos/")
                    response.raise_for_status()

                    if response.status_code != 200:
                        logger.error(
                            f"Failed to fetch students: {response.status_code}"
                        )
                        return None

                    return response.json().get("results", [])
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

        # TODO: ActivitySoft espera a matrícula do aluno enquanto a catraca retorna o cartão
        # TODO: PS: Cada instuição tem uma API Key diferente, logo, vamos ter que fazer sempre uma relação entre cartão -> matrícula -> instituição -> api_key

        headers = {"apiKey": api_key}

        # Payload and Request
        async with httpx.AsyncClient(base_url=API_BASE_URL, headers=headers) as client:

            async def post_data(acesso):
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

    def wait_for_interval(stop_event):
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
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    results = loop.run_until_complete(push_acessos_api(acessos))
                finally:
                    loop.close()

                # Atualizar status dos bilhetes:
                bulk_update_synced_acessos(results)

                # TODO: Atualizar interface gráfica
        except Exception as e:
            logger.warning(f"Error na execução da tarefa")
            logger.exception(e)
        finally:
            wait_for_interval(stop_event)
