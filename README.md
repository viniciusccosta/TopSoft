# TopSoft 🎓

[![Version](https://img.shields.io/badge/version-0.1.0-blue.svg)](https://github.com/viniciusccosta/TopSoft/releases)
[![Python](https://img.shields.io/badge/python-3.12+-green.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**TopSoft** é uma solução completa de integração entre dispositivos de controle de acesso **TopData** (catracas) e o sistema de gestão escolar **ActivitySoft**. Desenvolvido com arquitetura moderna e interface intuitiva, garante sincronização eficiente e confiável dos dados de acesso.

## 🚀 Características Principais

- **🔄 Integração em Tempo Real**: Processamento automático de eventos das catracas TopData
- **👥 Gestão Completa**: Gerenciamento de alunos, cartões de acesso e registros de entrada/saída  
- **🎛️ Interface Moderna**: GUI clean e intuitiva construída com ttkbootstrap
- **🏗️ Arquitetura Robusta**: Padrão ActiveRecord com SQLModel ORM
- **⚡ Operações em Lote**: Processamento eficiente de grandes volumes de dados
- **🔧 Configuração Simples**: Setup fácil e gerenciamento intuitivo

## 🎯 Funcionalidades

### 🔄 **Processamento de Dados das Catracas**

- Leitura automática do arquivo `bilhetes.txt` com biblioteca **PyGTail**
- Processamento incremental (apenas novas linhas) para máxima eficiência
- Sincronização automática com ActivitySoft a cada intervalo configurável
- Suporte a reprocessamento com data de corte (offset)

### 👥 **Gestão de Estudantes**

- Sincronização automática de registros de alunos do ActivitySoft
- Validação e formatação automática de dados
- Busca por nome, matrícula ou CPF
- Histórico de acessos por estudante

### 🎟️ **Gerenciamento de Cartões de Acesso**

- Vinculação de cartões a estudantes (funcionalidade ausente no ActivitySoft)
- Geração do arquivo `gi5_cartoes.txt` para as catracas TopData
- Formatação automática com zeros à esquerda (16 caracteres)
- Controle de cartões não atribuídos

### 📊 **Monitoramento e Relatórios**

- Interface em tempo real dos eventos de acesso
- Exportação de dados em formato JSON
- Estatísticas de entradas e saídas por data
- Status de sincronização dos registros

### ⚙️ **Configurações Avançadas**

- Intervalo de sincronização configurável
- Caminho personalizado para arquivos das catracas
- Execução em segundo plano (system tray)
- Logs detalhados para troubleshooting

## 📦 Instalação

### Instalação Rápida (Recomendada)

1. Baixe o instalador mais recente: [`topsoft_v0.1.0_win64.exe`](https://github.com/viniciusccosta/TopSoft/releases)
2. Execute o instalador e siga o assistente de setup
3. Inicie o TopSoft pelo menu Iniciar ou atalho na área de trabalho

**Requisitos**: Windows 10/11 (64-bit)

### Desenvolvimento

```bash
# Clone o repositório
git clone https://github.com/viniciusccosta/TopSoft.git
cd TopSoft

# Instale as dependências
poetry install

# Execute em modo desenvolvimento
poetry run python main.py
```

## 🚀 Primeiros Passos

### 1. Configuração Inicial

- **Credenciais do ActivitySoft**: Configure sua API key e URL do servidor
- **Caminho das Catracas**: Aponte para o diretório dos arquivos `bilhetes.txt`
- **Intervalo de Sync**: Defina a frequência de sincronização (padrão: 5 minutos)

### 2. Importação de Dados

- A primeira sincronização importará todos os estudantes do ActivitySoft
- Vincule cartões de acesso aos estudantes na aba "Cartões"
- Gere o arquivo `gi5_cartoes.txt` para upload nas catracas

### 3. Monitoramento

- Acompanhe os eventos de acesso em tempo real na tela principal
- Verifique logs de sincronização na aba "Configurações"
- Exporte dados quando necessário para backup

## 🏗️ Arquitetura Técnica

### **Modelos de Dados**

- **`Aluno`**: Registros de estudantes com métodos de gestão completos
- **`CartaoAcesso`**: Cartões de acesso com vinculação a estudantes
- **`Acesso`**: Eventos de entrada/saída com status de sincronização

### **Componentes Principais**

- **Repository Layer**: Lógica de negócio para operações complexas
- **API Integration**: Cliente HTTP robusto para comunicação com ActivitySoft
- **Background Tasks**: Tarefas automatizadas de sincronização e monitoramento
- **Settings System**: Gerenciamento persistente de configurações

### **Tecnologias Utilizadas**

- **Python 3.12+**: Linguagem principal
- **SQLModel**: ORM type-safe para operações de banco
- **ttkbootstrap**: Interface gráfica moderna
- **httpx**: Cliente HTTP assíncrono
- **Poetry**: Gerenciamento de dependências

## 🔧 Scripts de Build

```bash
# Bump version e build completo
python scripts/build_all.py patch|minor|major

# Apenas sincronizar versões
python scripts/sync_version.py

# Build sem bump de versão
python scripts/build_and_install.py
```

## 📁 Estrutura do Projeto

```text
TopSoft/
├── topsoft/           # Módulos principais da aplicação
│   ├── models.py      # Modelos de dados (Aluno, CartaoAcesso, Acesso)
│   ├── repository.py  # Lógica de negócio cross-model
│   ├── frames.py      # Interface gráfica
│   ├── database.py    # Configuração do banco de dados
│   └── activitysoft/  # Integração com ActivitySoft API
├── scripts/           # Scripts de build e utilitários
├── main.py           # Ponto de entrada da aplicação
├── installer.iss     # Configuração do Inno Setup
└── topsoft.spec      # Configuração do PyInstaller
```

## 📝 Configuração

O TopSoft armazena suas configurações em:

- **Banco de dados**: `topsoft.db` (SQLite)
- **Configurações**: `settings.json` (preferências da aplicação)
- **Logs**: `topsoft.log` (logs da aplicação)

## 🐛 Problemas Conhecidos

- Mudanças nas configurações requerem reinício da aplicação
- Importações grandes podem levar alguns minutos para completar
- O ActivitySoft não possui campo nativo para vínculo cartão-estudante

## 💡 Dicas de Uso

- Execute como Administrador para acesso completo ao sistema de arquivos
- Mantenha backups regulares do arquivo `topsoft.db`
- Monitore o arquivo de log para diagnóstico de problemas de sincronização
- Configure intervalos de sincronização adequados ao volume de dados

## 🤝 Contribuindo

1. Fork o projeto
2. Crie uma branch para sua feature (`git checkout -b feature/MinhaFeature`)
3. Commit suas mudanças (`git commit -m 'Adiciona MinhaFeature'`)
4. Push para a branch (`git push origin feature/MinhaFeature`)
5. Abra um Pull Request

## 📄 Licença

Este projeto está licenciado sob a Licença MIT - veja o arquivo [LICENSE](LICENSE) para detalhes.

## 🛠️ Suporte

- **Issues**: [GitHub Issues](https://github.com/viniciusccosta/TopSoft/issues)

---

Desenvolvido com ❤️ para facilitar a integração entre sistemas de controle de acesso e gestão escolar.
