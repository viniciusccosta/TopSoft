# TopSoft

**TopSoft** é um conector intermediário entre os dispositivos de controle de acesso da **TopData** (catracas) e o sistema de gestão escolar **ActivitySoft**. Seu objetivo é garantir a sincronização eficiente e confiável dos dados de acesso, oferecendo funcionalidades específicas que preenchem as lacunas existentes no fluxo direto entre hardware e software de gestão.

## 📌 Objetivo

Facilitar e automatizar a comunicação entre os arquivos gerados pelas catracas da TopData e o sistema de gestão escolar ActivitySoft, assegurando que todas as informações de acesso sejam processadas, integradas e armazenadas corretamente.

## ⚙️ Funcionalidades

### 1. Leitura periódica do arquivo `bilhetes.txt`

* O TopSoft realiza a leitura do arquivo `bilhetes.txt` a cada **1 minuto**.
* Utiliza a biblioteca **PygTail** para ler apenas as novas linhas adicionadas desde a última leitura, garantindo eficiência mesmo em arquivos de grande volume.
* Os dados são enviados automaticamente para o **ActivitySoft**, mantendo os registros sempre atualizados.
* Na primeira execução, se o arquivo já estiver grande, a leitura inicial poderá levar mais tempo.

### 2. Exportação da tela de "Acessos"

* A tela de acessos oferece uma visão consolidada de todos os registros processados.
* Pode ser exportada em **formato JSON**, incluindo informações úteis como:

  * Registros já enviados ao ActivitySoft.

### 3. Exportação de cartões para a catraca

* A aba **"Cartões"** permite gerar o arquivo `gi5_cartões.txt`, no seguinte formato:

  * **Número do cartão**: 16 caracteres (com zeros à esquerda).
  * **Nome da pessoa**: até 40 caracteres, alinhado à esquerda.
  * **Código fixo**: `"00110"` ao final.
* Esse arquivo é utilizado pelas catracas da TopData para permitir ou negar acessos.

### 4. Vínculo entre cartão e aluno/funcionário

* Diferente de outros gestores disponíveis no mercado, o **ActivitySoft não possui um campo interno** para armazenar o vínculo entre o número do cartão/carteirinha e o aluno ou funcionário.
* Por isso, o próprio **TopSoft** disponibiliza uma aba específica para realizar esse vínculo de forma local.
* Esses dados também podem ser exportados em **formato JSON** para fins de backup ou portabilidade.

### 5. Execução contínua e discreta

* O programa deve estar sempre em execução para garantir o funcionamento da sincronização em tempo real.
* Quando o usuário tenta fechar a aplicação, ela é minimizada para a bandeja do sistema (system tray) por meio da biblioteca **pystray**.
* Para encerrar o programa, é necessário clicar com o botão direito no ícone da bandeja e escolher a opção de sair.

### 6. Reprocessamento com data de offset

* Caso seja necessário reutilizar um arquivo antigo `bilhetes.txt`, o TopSoft permite definir uma **data de offset**.
* O programa continuará lendo o arquivo inteiro, mas irá **ignorar** registros com data anterior ao offset informado, processando apenas os acessos relevantes.

## 💡 Benefícios

* Integração completa entre hardware de controle de acesso e sistema de gestão.
* Eficiência na leitura de grandes arquivos.
* Exportações amigáveis para backup e reinstalação.
* Solução prática para ausência de vínculo nativo entre cartão e aluno no ActivitySoft.
* Interface simples e funcional, com execução discreta.
