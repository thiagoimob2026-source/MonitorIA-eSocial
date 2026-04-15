from fpdf import FPDF
import os
from datetime import datetime

class MasterclassPDF(FPDF):
    def header(self):
        if self.page_no() > 1:
            self.set_font('Arial', 'I', 8)
            self.set_text_color(128)
            self.cell(0, 10, 'IA_eSocial - Masterclass Técnica - Construído por Thiago César Cabral Araujo Gama', 0, 0, 'R')
            self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(128)
        self.cell(0, 10, f'iaesocial.com.br - Página {self.page_no()}/{{nb}}', 0, 0, 'C')

    def chapter_title(self, title):
        self.set_font('Arial', 'B', 16)
        self.set_text_color(44, 62, 80)
        self.cell(0, 10, title, 0, 1, 'L')
        self.ln(4)

    def chapter_body(self, body):
        self.set_font('Arial', '', 11)
        self.set_text_color(0)
        self.multi_cell(0, 7, body)
        self.ln()

    def add_chapter(self, title, body):
        self.add_page()
        self.chapter_title(title)
        self.chapter_body(body)

def generate_masterclass(output_path):
    pdf = MasterclassPDF()
    pdf.alias_nb_pages()

    # COVER PAGE
    pdf.add_page()
    pdf.set_font('Arial', 'B', 24)
    pdf.ln(50)
    pdf.set_text_color(41, 128, 185)
    pdf.cell(0, 20, 'IA_eSocial Masterclass', 0, 1, 'C')
    pdf.set_font('Arial', 'B', 14)
    pdf.set_text_color(0)
    pdf.cell(0, 10, 'Guia Técnico de Arquitetura e Implementação eSocial v1.0', 0, 1, 'C')
    
    pdf.ln(30)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'Construído por:', 0, 1, 'C')
    pdf.set_font('Arial', '', 14)
    pdf.cell(0, 10, 'Thiago César Cabral Araujo Gama', 0, 1, 'C')
    pdf.set_font('Arial', 'I', 12)
    pdf.cell(0, 10, 'Criador de iaesocial.com.br', 0, 1, 'C')
    
    pdf.ln(50)
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 10, f'Data de Publicação: {datetime.now().strftime("%d/%m/%Y")}', 0, 1, 'C')

    # INTRODUCTION
    pdf.add_chapter('1. Visão Geral do Projeto', 
        "O IA_eSocial nasceu com o objetivo de simplificar uma das tarefas mais complexas da folha de pagamento no Brasil: "
        "a transmissão de eventos para o portal eSocial do Governo Federal. \n\n"
        "Desenvolvido como uma aplicação desktop moderna em Python, o sistema combina uma interface amigável "
        "com um motor de transmissão de alta performance que resolve problemas históricos de compatibilidade com certificados A3.")

    # ARCHITECTURE
    pdf.add_chapter('2. Arquitetura do Sistema',
        "O sistema foi construído seguindo uma arquitetura de módulos independentes:\n\n"
        "1. Frontend (Interface): Utiliza a biblioteca CustomTkinter para uma experiência visual 'Premium', com suporte a modo escuro e layout responsivo.\n"
        "2. Camada de Dados: Implementada com SQLite 3, garantindo persistência rápida de históricos sem necessidade de instalar servidores de banco de dados externos.\n"
        "3. Engine de XML: Módulo Python especializado em gerar XMLs baseados nos layouts oficiais (S-1.3.0), convertendo dados simples em estruturas complexas.\n"
        "4. Módulo Nativo (The Bridge): Um componente escrito em C# (.NET) que atua como o 'braço robótico' do sistema para lidar com assinatura digital e segurança MTLS.")

    # THE NATIVE BRIDGE (CRITICAL PART)
    pdf.add_chapter('3. A Ponte Nativa: Python + C#',
        "Um dos grandes diferenciais técnicos deste projeto é a solução para Certificados A3. \n\n"
        "O Python nativamente possui limitações para acessar as chaves privadas de tokens A3 protegidas por hardware (KSP/CSP Windows). "
        "Para superar isso, o sistema utiliza o 'Módulo Nativo' (esocial_client.exe):\n\n"
        "- O Python prepara os dados e chama o binário C# via subprocess.\n"
        "- O C# acessa o Repositório de Certificados do Windows, solicita a assinatura do XML e estabelece o canal seguro (MTLS) com o governo.\n"
        "- Isso garante 100% de compatibilidade com qualquer cartão ou token A3 no mercado brasileiro.")

    # ESOCIAL COMMUNICATION
    pdf.add_chapter('4. Comunicação com a API eSocial',
        "A comunicação com o eSocial não é um simples envio de formulário. Ela segue um protocolo rigoroso:\n\n"
        "1. Assinatura Digital: Cada evento deve ser assinado com o certificado da empresa (X.509).\n"
        "2. Envio de Lote: Os eventos são empacotados em um lote SOAP e enviados.\n"
        "3. Resposta Síncrona: O governo devolve um 'Recibo de Entrega' ou um 'Protocolo de Processamento'.\n"
        "4. Consulta de Lote: O sistema consulta automaticamente o protocolo para obter o resultado final e os totalizadores de tributos.")

    # DISTRIBUTION
    pdf.add_chapter('5. Engenharia de Distribuição',
        "Para que o sistema seja utilizável por qualquer pessoa sem instalar o Python, implementamos um pipeline de build:\n\n"
        "- PyInstaller: Compacta todo o código Python e bibliotecas (CustomTkinter, lxml, fpdf2) em um único executável (.exe).\n"
        "- Inno Setup: Cria o instalador profissional que cria atalhos no menu iniciar e gerencia permissões de pasta em Arquivos de Programas.")

    # PRESENTATION SCRIPT
    pdf.add_chapter('6. Como Apresentar este Projeto',
        "Se você for apresentar o IA_eSocial para um cliente ou platéia, utilize o roteiro abaixo:\n\n"
        "O Problema: Transmitir eSocial é burocrático, lento e os sistemas atuais costumam falhar com tokens A3.\n"
        "A Solução: O IA_eSocial é uma ferramenta leve, portátil e automática que fala diretamente com o governo.\n"
        "O Valor: Mais velocidade no envio de S-1200/S-1210 e total transparência com relatórios em PDF gerados na hora.\n"
        "A Tecnologia: Construído com o que há de mais moderno em Python e integração Windows nativa.")

    pdf.output(output_path)
    return output_path

if __name__ == "__main__":
    path = "c:\\Users\\thiag\\OneDrive\\Área de Trabalho\\IA_eSocial_v1.0_Final\\IA_eSocial_Masterclass.pdf"
    generate_masterclass(path)
    print(f"Masterclass PDF gerada com sucesso em: {path}")
