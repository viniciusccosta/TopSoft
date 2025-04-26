import asyncio
import logging
from functools import partial
from time import sleep

import aiometer
import httpx
from decouple import config

from topsoft.constants import ACTIVITY_URL
from topsoft.database import get_api_key, get_bilhetes_path, get_interval
from topsoft.utils import read_in_batches

logger = logging.getLogger(__name__)


def background_task(stop_event):
    def read_bilhetes_file(filepath):
        """
        Read the bilhetes file and return a list of dictionaries with the data.
        """

        logging.debug(f"Reading bilhetes file: {filepath}")

        bilhetes = []

        # TODO: TALVEZ será necessário um Banco de Dados
        # TODO: Forma mais inteligente de ler o arquivo sem precisar ler TODOS os dados toda vez
        # TODO: Como só registra hora:minuto podemos ler apenas a cada multiplo de 60 segundos (intervalo no frontend)

        for batch in read_in_batches(filepath):
            for tokens in batch:
                try:
                    bilhetes.append(
                        {
                            "marcação": tokens[
                                0
                            ],  # str(3) = 010 (Entrada) | 011 (Saída)
                            "date": tokens[1],  # dd/mm/yy ou dd/mm/yyyy
                            "time": tokens[2],  # hh:mm
                            "cartao": tokens[3],  # str(5) ou str(16)
                            "catraca": tokens[4],  # str(2) = 01, 02, 03, ..., 99
                            # "sequencial": tokens[5],  # str(10)
                        }
                    )
                except IndexError as e:
                    logging.warning(f"Error reading line")  # TODO: Melhorar mensagem
                    logging.exception(e)
                    continue

        return bilhetes

    async def send_data_to_activitysoft(bilhetes):
        """
        Send data to ActivitySoft.
        """

        logger.debug(f"Sending data to ActivitySoft: {len(bilhetes)} bilhetes")

        # TODO: Necessário saber quais dados já foram enviados pra evitar duplicados no ActSoft ?

        # Header
        api_key = get_api_key()
        if not api_key:
            logger.error("API key not found")
            return False

        # TODO: ActivitySoft espera a matrícula do aluno enquanto a catraca retorna o cartão
        # TODO: PS: Cada instuição tem uma API Key diferente, logo, vamos ter que fazer sempre uma relação entre cartão -> matrícula -> instituição -> api_key

        headers = {"apiKey": api_key}

        # Payload and Request
        async with httpx.AsyncClient(headers=headers) as client:

            async def post_data(payload):
                try:
                    response = await client.post(ACTIVITY_URL, json=payload)
                    response.raise_for_status()  # catch HTTP errors

                    return response.status_code, response.json()
                except Exception as e:
                    logger.error(f"Failed to send payload {payload}")
                    logger.exception(e)

                    return None, None

            results = await aiometer.run_all(
                [partial(post_data, bilhete) for bilhete in bilhetes[:50]],
                max_at_once=500,  # TODO: Adjust based on your API/server capacity
                max_per_second=1,  # TODO: Optional: rate-limit
            )

        for status, data in results:
            logger.info(f"Status: {status}, Response: {data}")

        return True

    def wait_for_interval(stop_event):
        """
        Wait for the specified interval.
        """

        intervalo = get_interval()

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
            # Ler arquivo:
            if bilhetes_path := get_bilhetes_path():
                data = read_bilhetes_file(bilhetes_path)

                # Enviar dados para ActivitySoft:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(send_data_to_activitysoft(data))
                finally:
                    loop.close()

                # TODO: Atualizar interface gráfica
        except Exception as e:
            logger.warning(f"Error na execução da tarefa")
            logger.exception(e)
        finally:
            wait_for_interval(stop_event)
