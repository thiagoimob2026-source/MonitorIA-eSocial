# 📊 IA_eSocial Monitor - Módulo de Transmissão Nativa

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![CSharp](https://img.shields.io/badge/C%23-Native_Core-239120?style=for-the-badge&logo=c-sharp&logoColor=white)
![License](https://img.shields.io/badge/License-Proprietary-red?style=for-the-badge)

O **IA_eSocial Monitor** é uma solução robusta e moderna para gerenciamento e transmissão de eventos do eSocial. Construído com uma arquitetura híbrida, ele combina a flexibilidade do Python com a segurança e conformidade do C# para lidar com assinaturas digitais e protocolos governamentais.

---

## 🏗️ Arquitetura do Sistema

O sistema foi desenhado para ser modular e resiliente:

*   **Front-end & Inteligência (Python)**: Utiliza `customtkinter` para uma interface moderna e `lxml` para manipulação dinâmica de dados. É responsável pela lógica de negócios, importação de planilhas e gestão do banco de dados SQLite.
*   **Motor de Comunicação (C# - Native)**: Um componente especializado em .NET que lida com a complexidade de certificados digitais (A1/A3), assinaturas XMLDSig e o envelope SOAP de transmissão mTLS exigido pelo governo.

---

## 🚀 Principais Funcionalidades

### 1. Motor de Metadados (Metadata-Driven)
Diferente de sistemas rígidos, o IA_eSocial utiliza arquivos JSON na pasta `layouts/` para definir a estrutura dos eventos. Isso permite:
- Atualização rápida de layouts (S-1.2, S-1.3, etc.) sem mexer no código-fonte.
- Mapeamento dinâmico de campos CSV com suporte a sinônimos.

### 2. Gerenciamento de Lotes
- Importação massiva de rubricas e pagamentos.
- Painel de conferência individual para validação de dados antes do envio.
- Transmissão em lote com otimização de sessão de certificado (ideal para tokens A3).

### 3. Auditoria e Relatórios (Conferência S-5001)
- **Novo**: Módulo de conferência de INSS que lê arquivos S-5001 (retorno do governo).
- Compara automaticamente o valor calculado pelo eSocial (`vrCpSeg`) com o valor retido pela folha (`vrDescSeg`).
- Relatórios PDF de "Nível Executivo" com sinalização de divergências.

### 4. Dashboard em Tempo Real
- Visão geral de sucessos, erros e pendências diretamente na tela inicial.
- Histórico completo de eventos com busca por CPF.

---

## 📂 Estrutura de Pastas

```bash
├── layouts/           # Definições JSON dos eventos eSocial
├── schemas/           # Arquivos XSD para validação governamental
├── native/            # Binários e fontes do comunicador C#
├── database.py        # Gestor de persistência SQLite
├── report_generator.py # Motor de geração de PDFs
├── main.py            # Interface gráfica e lógica central
└── esocial_native.py  # A "ponte" entre Python e o motor C#
```

---

## 🛠️ Requisitos e Instalação

### Pré-requisitos
- Python 3.10 ou superior.
- Certificado Digital A1 (arquivo) ou A3 (token/cartão) instalado no Windows.
- Dependências Python: `pip install -r requirements.txt`

### Como executar
1. Clone o repositório: `git clone https://github.com/thiagoimob2026-source/MonitorIA-eSocial.git`
2. Configure seu ambiente virtual: `python -m venv .venv`
3. Inicie o sistema: `python main.py`

---

## 📜 Licença e Uso

Este projeto é uma ferramenta profissional de gestão de dados eSocial. Certifique-se de manter os esquemas (`xsd`) sempre atualizados conforme as normas técnicas vigentes da Receita Federal e do Ministério do Trabalho.

---

> [!TIP]
> **Desenvolvedores**: Ao adicionar um novo evento, basta criar o JSON correspondente na pasta `layouts/` e o sistema gerará a interface e o XML automaticamente.
