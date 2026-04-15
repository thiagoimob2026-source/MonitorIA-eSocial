# 📘 E-book: Entendendo o Sistema IA_eSocial

Este guia detalhado foi criado para que você compreenda cada engrenagem do sistema, desde a lógica de interface em Python até a complexa transmissão nativa em C#. Este documento serve como o manual definitivo para manutenção, atualização e entendimento do seu software.

---

## 🏗️ 1. Arquitetura Geral: O Casamento entre Python e C#

O sistema `IA_eSocial` é uma solução **híbrida**. Mas por que não usar apenas uma linguagem?

*   **Python (A Inteligência e Interface)**: Responsável pela interface gráfica (`customtkinter`), manipulação de arquivos CSV, lógica de banco de dados (`sqlite`) e a geração dinâmica de XMLs através de arquivos JSON. O Python é excelente para prototipagem rápida e interface amigável.
*   **C# (O Motor de Força e Segurança)**: O eSocial exige comunicações seguras (SSL/TLS com mTLS) e assinaturas digitais complexas (XMLDSig). O Windows lida melhor com certificados A1/A3 através de bibliotecas nativas do .NET. Por isso, criamos um "Cliente Nativo" em C# (`native/esocial_client.exe`) que o Python chama apenas quando precisa assinar ou transmitir.

### O Fluxo de um Evento (Do CSV ao Governo):
1.  **Importação**: O Python lê o CSV e converte em um dicionário (objeto).
2.  **Preparação**: O Motor de Metadados (`LayoutEngine`) usa o arquivo JSON para transformar esse dicionário em um XML "cru".
3.  **Validação**: O `xml_validator.py` confere se o XML está seguindo as regras do Governo (XSD).
4.  **Assinatura**: O Python envia o XML para o `esocial_client.exe` (C#), que acessa seu certificado digital e insere a assinatura `<ds:Signature>`.
5.  **Transmissão**: O `esocial_client.exe` monta o envelope SOAP e envia para os servidores do eSocial.
6.  **Retorno**: O Governo responde com um XML de recibo, que o Python interpreta e salva no banco de dados.

---

## 🌉 2. A Ponte de Comunicação (`esocial_native.py`)

Este arquivo é o "tradutor" que permite ao Python conversar com o motor de envio.

### Linhas Críticas Explicadas:

*   **`class ESocialNativeSender`**: Centraliza todas as configurações de URL do eSocial (Produção vs Homologação).
*   **`sign_and_send_batch` (A função mais comum)**:
    - Ela recebe uma lista de caminhos de arquivos XML.
    - Monta um comando de terminal para o `esocial_client.exe`.
    - O comando `sign-batch-send` é crucial porque abre a sessão do certificado apenas **uma vez** para assinar vários eventos, evitando que o usuário precise digitar o PIN do cartão A3 repetidamente.
*   **`parse_response`**: 
    - Esta função usa `lxml` para vasculhar o XML de retorno do Governo.
    - Ela foca nas tags `cdResposta` (201/202 = Sucesso) e `ocorrencia` (onde vêm as mensagens de erro detalhadas).

---

## ⚙️ 3. O Motor de Metadados (`event_templates.py` + JSON)

Aqui é onde o sistema se diferencia dos softwares tradicionais. No IA_eSocial, o formato do XML não está "escrito em pedra" no código.

### Como funciona o motor:
1.  **`LayoutEngine`**: Carrega os arquivos `.json` da pasta `layouts/`. Cada JSON tem o "DNA" de um evento (ex: S-1200).
2.  **Mapeamentos**: Dentro do JSON, a chave `mappings` diz ao sistema: *"O campo 'valor' que veio do CSV deve ser colocado dentro da tag XML <vrRubr>"*.
3.  **Geração Dinâmica (`generate_xml_from_metadata`)**: Esta função percorre o JSON e vai construindo o XML tag por tag. Se o eSocial mudar uma tag de nome amanhã, você só precisa mudar o JSON, sem precisar programar uma linha sequer.

---

## 🐍 4. Deep Dive: Desvendando o `main.py`

O `main.py` é o coração da experiência do usuário. Ele gerencia as janelas, as abas e os processos de lote.

### Blocos Funcionais Importantes:

#### A Classe `LayoutEngine` (Início do arquivo)
```python
def build_form(self, parent, evt_type, entries_dict):
```
> [!NOTE]
> Esta função varre o JSON e cria automaticamente os campos de entrada (Entries) na sua tela. É por isso que as abas S-1200, S-1202 e S-1207 parecem padronizadas: elas são "desenhadas" pelo mesmo código.

#### O Processador de Planilhas (`_generic_rubric_batch_processor`)
```python
def get_val(row_lower, target_tag):
    synonyms = { ... }
```
> [!IMPORTANT]
> Aqui reside o segredo da flexibilidade do CSV. O dicionário de sinônimos permite que o programa encontre o CPF mesmo que ele esteja escrito como "identificador" ou "cpfbeneficiario". Ele limpa pontos e traços automaticamente usando Regex (`re.sub`).

#### O Distribuidor de Envios (`process_send_list`)
Esta função é chamada quando você clica em "Enviar Selecionados".
1.  Ela busca os XMLs no banco de dados.
2.  Cria arquivos temporários no seu Windows.
3.  Chama a `native_sender` (Capítulo 2) para fazer o envio real.
4.  Lê o recibo e atualiza o banco de dados.

---

## 📜 5. Conformidade Técnica eSocial (vS-1.3)

Para que o eSocial aceite seus envios, seguimos regras rígidas documentadas no **MOS (Manual de Orientação do eSocial)**:

*   **Identificadores (ID)**: Cada evento tem um ID único que começa com `ID1` followed por CNPJ + Timestamp. Nós geramos isso seguindo a regra `ID1{CNPJ/CPF}{Timestamp}{Seral}`.
*   **Namespace**: O uso correto de `xmlns="http://www.esocial.gov.br/..."` é vital. O `lxml` garante que as tags de namespace sejam inseridas corretamente.
*   **Assinatura Digital**: O Governo exige `XMLDSig` com o algoritmo `sha256`. Nosso motor C# lida com essa complexidade garantindo que a assinatura seja válida juridicamente.

---

## 🛠️ 6. Guia de Manutenção: Como Atualizar o Sistema

Se o Governo lançar o layout **S-1.4**, você não precisa entrar em pânico:

1.  **Atualizar JSON de Layout**: Abra o arquivo `.json` correspondente na pasta `layouts/`. Adicione, remova ou renomeie as tags conforme o novo manual.
2.  **Atualizar Tabelas SQL (Se necessário)**: O `database.py` raramente muda, pois ele salva o XML bruto.
3.  **Adicionar Sinônimos**: Se seus clientes começarem a enviar planilhas com nomes de colunas novos, basta adicionar esses nomes no dicionário `synonyms` dentro do `main.py`.

---

> [!TIP]
> **Dica de Ouro**: Sempre mantenha a pasta `schemas/` atualizada. É nela que o sistema lê os arquivos `.xsd` oficiais que validam se o seu XML está perfeito antes do envio.

Este sistema foi construído para ser **modular**. Se uma peça (como o envio) falhar, a inteligência (Python) permanece intacta. Você tem agora em mãos uma estrutura escalável e de nível profissional.
