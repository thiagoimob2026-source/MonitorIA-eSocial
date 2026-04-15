from fpdf import FPDF
import os
from datetime import datetime

class DeepDivePDF(FPDF):
    def header(self):
        if self.page_no() > 1:
            self.set_font('Arial', 'I', 8)
            self.set_text_color(100)
            self.cell(0, 10, 'IA_eSocial - Mergulho Profundo na Programação - Guia do Desenvolvedor', 0, 0, 'R')
            self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(100)
        self.cell(0, 10, f'iaesocial.com.br - Documentação Técnica Interna - Página {self.page_no()}/{{nb}}', 0, 0, 'C')

    def chapter_title(self, title):
        self.set_font('Arial', 'B', 14)
        self.set_text_color(33, 47, 61)
        self.cell(0, 10, title, 0, 1, 'L', fill=False)
        self.draw_line()
        self.ln(2)

    def draw_line(self):
        self.set_draw_color(46, 204, 113) # Green line
        self.line(self.get_x(), self.get_y(), self.get_x() + 190, self.get_y())

    def chapter_body(self, body):
        self.set_font('Arial', '', 10)
        self.set_text_color(0)
        self.multi_cell(0, 6, body)
        self.ln()

    def code_block(self, code):
        self.set_fill_color(240, 240, 240)
        self.set_font('Courier', '', 9)
        self.multi_cell(0, 5, code, fill=True, border=1)
        self.ln(4)

def generate_deep_dive(output_path):
    pdf = DeepDivePDF()
    pdf.alias_nb_pages()

    # COVER
    pdf.add_page()
    pdf.set_font('Arial', 'B', 22)
    pdf.ln(40)
    pdf.set_text_color(22, 160, 133)
    pdf.cell(0, 15, 'IA_eSocial: Engenharia de Software', 0, 1, 'C')
    pdf.set_font('Arial', 'B', 16)
    pdf.set_text_color(0)
    pdf.cell(0, 10, 'Mergulho Profundo na Arquitetura e Programação', 0, 1, 'C')
    
    pdf.ln(20)
    pdf.set_font('Arial', '', 11)
    pdf.multi_cell(0, 7, 
        "Este guia técnico foi desenhado para ensinar os princípios fundamentais, desafios e soluções "
        "implementadas no IA_eSocial. Ele serve como base de conhecimento para manutenção, "
        "escala e evolução do sistema.", align='C')

    pdf.ln(20)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'Autor & Desenvolvedor:', 0, 1, 'C')
    pdf.set_font('Arial', '', 14)
    pdf.cell(0, 10, 'Thiago César Cabral Araujo Gama', 0, 1, 'C')
    pdf.set_font('Arial', 'I', 11)
    pdf.cell(0, 10, 'Plataforma: iaesocial.com.br', 0, 1, 'C')
    
    pdf.ln(40)
    pdf.set_font('Arial', '', 9)
    pdf.cell(0, 10, f'Documento Gerado em: {datetime.now().strftime("%d/%m/%Y %H:%M")}', 0, 1, 'C')

    # CHAPTER 1: UI ARCHITECTURE
    pdf.add_page()
    pdf.chapter_title('1. Arquitetura de Interface (Frontend)')
    pdf.chapter_body(
        "A interface utiliza CustomTkinter, um wrapper moderno sobre o Tkinter padrão. A principal técnica "
        "utilizada aqui é a 'Orientação a Objetos por Componentes'.\n\n"
        "Cada painel de histórico, por exemplo, é uma instância da classe 'QuickHistoryPanel'. Isso permite "
        "reutilizar o mesmo código para as abas de S-1200, S-1202, etc., apenas mudando o parâmetro de filtro.\n\n"
        "O 'segredo' da responsividade é o grid system:")
    pdf.code_block(
        "self.grid_columnconfigure(1, weight=1)\n"
        "self.grid_rowconfigure(0, weight=1)\n"
        "# O 'weight=1' diz ao Python para expandir o widget quando a janela crescer.")

    # CHAPTER 2: DATABASE & LOGIC
    pdf.chapter_title('2. Camada de Dados (Backend)')
    pdf.chapter_body(
        "Utilizamos SQLite 3 para armazenamento local. Optamos por centralizar a DB na pasta AppData "
        "para garantir persistência mesmo após atualizações do programa. \n\n"
        "Uma técnica avançada usada na database.py é o 'Row Factory':")
    pdf.code_block(
        "conn.row_factory = sqlite3.Row\n"
        "# Isso permite acessar os dados do banco como um dicionário:\n"
        "row['status'] em vez de row[3]")

    # CHAPTER 3: THE NATIVE BRIDGE
    pdf.add_page()
    pdf.chapter_title('3. A Ponte Nativa (O Coração da Transmissão)')
    pdf.chapter_body(
        "Este é o ponto mais complexo do sistema. O Python não consegue lidar bem com Certificados A3 da Windows Store nativamente. "
        "Por isso, usamos uma 'Ponte' (Engine Nativa em C#).\n\n"
        "Fluxo de Programação:\n"
        "1. O Python salva o XML em um arquivo temporário no sistema.\n"
        "2. O Python dispara um subprocess chamado 'esocial_client.exe'.\n"
        "3. O C# lê esse arquivo, assina usando as chaves RSA do Windows e envia via SOAP.\n"
        "4. O C# devolve a resposta do governo na 'Saída de Texto' (stdout).\n"
        "5. O Python captura essa saída e interpreta o resultado.")
    pdf.code_block(
        "subprocess.run([exe_path, xml_path, ...], capture_output=True, text=True)\n"
        "# Aqui capturamos o erro ou o sucesso retornado pelo binário.")

    # CHAPTER 4: CHALLENGES & SOLUTIONS
    pdf.chapter_title('4. Desafios e Debugging (Lições Aprendidas)')
    pdf.chapter_body(
        "Durante a construção, resolvemos 3 grandes 'Gargalos' que todo programador de eSocial enfrenta:\n\n"
        "1. Desafio do Unicode: O Windows usa codificações diferentes (UTF-8 vs CP1252/Latin-1). "
        "Resolvemos forçando o encoding 'latin1' na captura do stdout para evitar que o sistema quebrasse ao ler acentos.\n\n"
        "2. Caminhos Relativos: Ao transformar o script em .exe, caminhos como 'native/client.exe' param de funcionar. "
        "Resolvemos com a função 'get_resource_path()', que detecta se o app está rodando de um script ou de um .exe temporário.\n\n"
        "3. Certificados Modernos: Transmitir via WebRequest padrão falhava em tokens novos. "
        "Migramos o motor para usar 'GetRSAPrivateKey()', garantindo suporte a chaves KSP modernas.")

    # CHAPTER 5: BUILD & PACKAGING
    pdf.add_page()
    pdf.chapter_title('5. Engenharia de Distribuição (Build)')
    pdf.chapter_body(
        "O processo de build via PyInstaller não é manual. Ele é automatizado pelo 'build_exe.py'. \n\n"
        "O comando principal faz o 'Bundling' de tudo:\n"
        "- '--add-data': Inclui os binários C#, os Schemas XSD e os arquivos do CustomTkinter dentro do seu .exe único.\n"
        "- '--hidden-import': Garante que bibliotecas como lxml (que carregam módulos em tempo de execução) não fiquem de fora.\n\n"
        "Resultado: O cliente final recebe um único arquivo que 'descompacta' tudo na memória e roda instantaneamente.")

    pdf.chapter_title('6. Dicas para Futuros Desenvolvedores')
    pdf.chapter_body(
        "Para evoluir o sistema:\n"
        "1. Sempre valide o XML contra o XSD antes de enviar (xml_validator.py).\n"
        "2. Monitore o Log Console (ele é sua caixa preta).\n"
        "3. Mantenha os templates de eventos (event_templates.py) desacoplados da interface.")

    pdf.output(output_path)
    return output_path

if __name__ == "__main__":
    path = "c:\\Users\\thiag\\OneDrive\\Área de Trabalho\\IA_eSocial_v1.0_Final\\IA_eSocial_Mergulho_Profundo.pdf"
    generate_deep_dive(path)
    print(f"Deep Dive PDF gerado com sucesso em: {path}")
