# 🧠 Base de Conhecimento: Projeto IA_eSocial

Este documento serve como a "memória central" do projeto, consolidando o que foi feito, a lógica por trás das decisões técnicas e o roteiro para o futuro.

## ✅ Funcionalidades Reais do Programa

1.  **Motor Dinâmico de Eventos**: Gera XMLs de S-1200, S-1202, S-1207 e S-3000 baseados puramente em arquivos JSON. A lógica de "montagem" do XML não está mais fixa no código, mas sim nos metadados.
2.  **Validação XSD em Tempo Real**: Todo XML gerado passa pelo `xml_validator.py` antes de ser salvo, garantindo que o Governo não rejeite por erro de estrutura.
3.  **Processador Massivo com Sinônimos**: Importa milhares de rubricas de CSVs, reconhecendo automaticamente diversas variações de cabeçalhos (ex: `VR_REM`, `Valor`, `vrRubr`).
4.  **Relatório Analítico Executivo**: Gera PDF organizado por CPF, consolidando eventos e exibindo um dashboard de status logo na primeira página.
5.  **Comunicação Nativa**: Utiliza certificados A1 (Windows) para assinar e enviar lotes via Web Service SOAP sem dependências externas pesadas.

---

## ⚠️ Atenção: O que NÃO alterar sem cuidado (Regras Críticas)

Para garantir que o programa não pare de funcionar em atualizações, atente-se a estes pontos:

*   **Identificadores de Trabalhador**: 
    - S-1200 e S-1202 SEMPRE usam a tag `cpfTrab`.
    - S-1207 e S-1210 SEMPRE usam a tag `cpfBenef`. 
    - *Alterar isso impedirá a importação correta desses eventos.*
*   **Ordem das Tags nos JSONs**: O eSocial é extremamente rigoroso com a ordem. A sequência de campos dentro de cada `section` no arquivo `.json` deve seguir exatamente a ordem do manual do eSocial/XSD.
*   **Encapsulamento de Demonstrativos**: O motor dinâmico agrupa automaticamente as rubricas dentro de `dmDev`. Nunca remova a chave `demonstrativos` da estrutura de dados, pois o motor espera essa lista para gerar o XML.
*   **Campo `indApurIR`**: Atualmente é obrigatório '0' para rubricas mensais. O motor está configurado para incluir isso automaticamente; remover este campo causará erro de validação XSD.
*   **Codificação (Encoding)**: O sistema utiliza `utf-8-sig` para ler CSVs (para suportar Excel brasileiro) e `utf-8` para XML. Mudar para `latin-1` ou outros pode corromper caracteres especiais e acentos.

---

## ✅ Conquistas Recentes (Fase de Refatoração e Relatórios)

1.  **Migração Sistemática**: S-1200, S-1202, S-1207 e S-3000 agora são automáticos via JSON.
2.  **Importação de CSV Robusta**: Mapeador de sinônimos corrigido para localizar CPFs de beneficiários (S-1207) e trabalhadores (S-1200).
3.  **Novo Relatório Analítico (PDF)**: Layout por trabalhador e dashboard corrigido.
4.  **Ambiente**: Configurada a biblioteca `fpdf2` e atualizado o `requirements.txt`.

---

## 📅 Próximos Passos (Próximas Alterações)

- [ ] **Migração do S-1210 (Pagamentos)**: Trazer este evento complexo para a sistemática dinâmica de JSON.
- [ ] **S-1000 JSON**: Criar o layout para o cadastro de empregador.
- [ ] **Dashboard de Erros na UI**: Uma aba para visualizar detalhes de rejeição do Governo de forma mais clara.
