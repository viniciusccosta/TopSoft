"""
Operações específicas para cartões de acesso com suporte a cancelamento.
"""

import logging
from typing import List, Tuple

from topsoft.cancellable_operations import CancellableOperation, FileProcessor
from topsoft.models import Aluno, CartaoAcesso

logger = logging.getLogger(__name__)


class ImportCartoesOperation(CancellableOperation):
    """
    Operação para importar cartões de acesso de um arquivo.

    Suporta cancelamento e feedback de progresso durante a importação.
    """

    def __init__(self, filepath: str):
        super().__init__(f"Importação de Cartões: {filepath}")
        self.filepath = filepath
        self.imported_count = 0
        self.skipped_count = 0
        self.error_count = 0

    def execute(self) -> dict:
        """
        Executa a importação dos cartões de acesso.

        Returns:
            dict: Estatísticas da importação
        """
        logger.info(f"Starting card import from: {self.filepath}")

        # Resetar contadores
        self.imported_count = 0
        self.skipped_count = 0
        self.error_count = 0

        # Usar FileProcessor para processar o arquivo
        processor = FileProcessor(self, batch_size=50)

        try:
            results = processor.process_file(
                self.filepath,
                self._process_card_line,
                progress_message="Importando cartões de acesso",
            )

            logger.info(
                f"Card import completed. Imported: {self.imported_count}, "
                f"Skipped: {self.skipped_count}, Errors: {self.error_count}"
            )

            return {
                "imported": self.imported_count,
                "skipped": self.skipped_count,
                "errors": self.error_count,
                "total_processed": len(results),
            }

        except Exception as e:
            logger.error(f"Error during card import: {e}")
            raise

    def _process_card_line(self, line: str, line_number: int) -> dict:
        """
        Processa uma linha do arquivo de cartões.

        Args:
            line: Linha do arquivo
            line_number: Número da linha

        Returns:
            dict: Resultado do processamento da linha
        """
        try:
            # Verificar se linha tem tamanho suficiente
            if not line or len(line) < 56:
                if line.strip():  # Só contar como erro se não for linha vazia
                    logger.warning(f"Linha {line_number} muito curta: {len(line)} caracteres")
                    self.error_count += 1
                return None

            # Extrair dados da linha
            numero = line[0:16].strip()
            nome = line[16:56].strip()

            if not numero:
                logger.warning(f"Linha {line_number}: número do cartão vazio")
                self.error_count += 1
                return None

            # Tentar criar ou obter cartão
            cartao, created = CartaoAcesso.get_or_create(numeracao=numero)

            if not created:
                logger.debug(f"Cartão {numero} já existe, pulando...")
                self.skipped_count += 1
                return {"action": "skipped", "numero": numero}

            # Se nome foi fornecido, tentar vincular a aluno
            if nome and nome != "Não vinculado":
                aluno = Aluno.find_by_name(nome)
                if aluno:
                    cartao.aluno = aluno
                    cartao.save()
                    logger.debug(f"Cartão {numero} criado e vinculado a {nome}")
                    result_type = "imported_with_student"
                else:
                    logger.debug(f"Cartão {numero} criado (aluno '{nome}' não encontrado)")
                    result_type = "imported_no_student"
            else:
                logger.debug(f"Cartão {numero} criado sem vinculação")
                result_type = "imported_no_name"

            self.imported_count += 1
            return {
                "action": "imported",
                "type": result_type,
                "numero": numero,
                "nome": nome,
            }

        except Exception as e:
            logger.error(f"Erro processando linha {line_number}: {e}")
            self.error_count += 1
            return {"action": "error", "error": str(e), "line_number": line_number}


class ExportCartoesOperation(CancellableOperation):
    """
    Operação para exportar cartões de acesso para um arquivo.
    """

    def __init__(self, filepath: str):
        super().__init__(f"Exportação de Cartões: {filepath}")
        self.filepath = filepath
        self.exported_count = 0

    def execute(self) -> dict:
        """
        Executa a exportação dos cartões de acesso.

        Returns:
            dict: Estatísticas da exportação
        """
        logger.info(f"Starting card export to: {self.filepath}")

        # Buscar todos os cartões
        self._update_progress(0, 0, "Buscando cartões de acesso...")
        cartoes = CartaoAcesso.get_all()
        total_cartoes = len(cartoes)

        if total_cartoes == 0:
            logger.warning("No cards found for export")
            return {"exported": 0, "total": 0}

        self._update_progress(0, total_cartoes, f"Exportando {total_cartoes} cartões...")

        # Preparar dados para exportação
        formatted_lines = []

        for i, cartao in enumerate(cartoes):
            # Verificar cancelamento
            self._check_cancellation()

            # Formatar linha
            card_number = str(cartao.numeracao).zfill(16)
            name = f"{cartao.aluno.nome if cartao.aluno else 'Não vinculado':<40}"
            formatted_line = f"{card_number}{name}00110"
            formatted_lines.append(formatted_line)

            # Atualizar progresso
            self._update_progress(i + 1, total_cartoes, f"Processando cartão {i + 1}/{total_cartoes}")

        # Escrever arquivo
        self._update_progress(total_cartoes, total_cartoes, "Salvando arquivo...")

        try:
            with open(self.filepath, "w", encoding="utf-8") as file:
                for line in formatted_lines:
                    file.write(line + "\n")

            self.exported_count = len(formatted_lines)
            logger.info(f"Successfully exported {self.exported_count} cards")

            return {"exported": self.exported_count, "total": total_cartoes}

        except Exception as e:
            logger.error(f"Error writing export file: {e}")
            raise


class BulkProcessOperation(CancellableOperation):
    """
    Operação base para processamento em lote de dados.
    """

    def __init__(self, name: str, items: List, batch_size: int = 100):
        super().__init__(name)
        self.items = items
        self.batch_size = batch_size
        self.processed_count = 0
        self.success_count = 0
        self.error_count = 0

    def execute(self) -> dict:
        """
        Executa o processamento em lote.

        Returns:
            dict: Estatísticas do processamento
        """
        total_items = len(self.items)

        if total_items == 0:
            return {"processed": 0, "success": 0, "errors": 0, "total": 0}

        logger.info(f"Starting bulk processing: {total_items} items")

        # Resetar contadores
        self.processed_count = 0
        self.success_count = 0
        self.error_count = 0

        # Processar em lotes
        for i in range(0, total_items, self.batch_size):
            # Verificar cancelamento
            self._check_cancellation()

            batch = self.items[i : i + self.batch_size]
            batch_number = (i // self.batch_size) + 1
            total_batches = (total_items + self.batch_size - 1) // self.batch_size

            # Atualizar progresso
            self._update_progress(i, total_items, f"Processando lote {batch_number}/{total_batches}")

            # Processar lote
            try:
                batch_results = self.process_batch(batch)

                # Contar resultados
                for result in batch_results:
                    self.processed_count += 1
                    if result.get("success", False):
                        self.success_count += 1
                    else:
                        self.error_count += 1

            except Exception as e:
                logger.error(f"Error processing batch {batch_number}: {e}")
                # Contar todo o lote como erro
                self.error_count += len(batch)
                self.processed_count += len(batch)

        # Progresso final
        self._update_progress(
            total_items,
            total_items,
            f"Processamento concluído: {self.success_count} sucessos, {self.error_count} erros",
        )

        logger.info(
            f"Bulk processing completed. Success: {self.success_count}, " f"Errors: {self.error_count}, Total: {self.processed_count}"
        )

        return {
            "processed": self.processed_count,
            "success": self.success_count,
            "errors": self.error_count,
            "total": total_items,
        }

    def process_batch(self, batch: List) -> List[dict]:
        """
        Processa um lote de itens. Deve ser implementado pelas subclasses.

        Args:
            batch: Lista de itens do lote

        Returns:
            List[dict]: Lista de resultados com chave "success"
        """
        raise NotImplementedError("Subclasses must implement process_batch")


class SyncAcessosOperation(BulkProcessOperation):
    """
    Operação para sincronizar acessos com a API.
    """

    def __init__(self, acessos: List):
        super().__init__("Sincronização de Acessos", acessos, batch_size=50)

    def process_batch(self, batch: List) -> List[dict]:
        """
        Processa um lote de acessos para sincronização.
        """
        import asyncio

        from topsoft.utils import post_acessos_and_update_synced_status

        try:
            # Executar sincronização assíncrona
            results = asyncio.run(post_acessos_and_update_synced_status(batch))

            # Converter resultados
            batch_results = []
            for acesso in batch:
                success = acesso in results if results else False
                batch_results.append({"id": acesso.id, "success": success})

            return batch_results

        except Exception as e:
            logger.error(f"Error in sync batch: {e}")
            # Retornar falha para todo o lote
            return [{"id": acesso.id, "success": False} for acesso in batch]
