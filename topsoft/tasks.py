import logging
from time import sleep

from topsoft.database import get_api_key, get_bilhetes_path, get_interval

logger = logging.getLogger(__name__)


def background_task(stop_event):
    def read_bilhetes_file(filepath):
        """
        Read the bilhetes file and return a list of dictionaries with the data.
        """
        logging.debug(f"Reading bilhetes file: {filepath}")

        with open(filepath, "r") as f:
            data = f.readlines()

        # TODO: Process the data as needed ?

        return data

    def send_data_to_activitysoft(data):
        """
        Send data to ActivitySoft.
        """
        logging.debug(f"Sending data to ActivitySoft: {data}")

        api_key = get_api_key()

        return True  # TODO: Simulating success

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
                result = send_data_to_activitysoft(data)
                if result:
                    logger.info("Data sent successfully")
                else:
                    logger.error("Failed to send data")

                # TODO: Atualizar interface gráfica
        except Exception as e:
            logger.error(f"Error na execução da tarefa")
            logger.exception(e)
        finally:
            wait_for_interval(stop_event)
